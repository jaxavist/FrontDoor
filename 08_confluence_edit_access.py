"""
Confluence Edit-Access Audit + Grant — FrontDoor
Companion to the Confluence usage audit.

PURPOSE
  Ensure the API user has edit rights on every EDIT-RESTRICTED page, so future
  macro-edit and usage scripts can run. Additive only.

RULES (per engagement requirements)
  - Only touches pages that ALREADY have an edit ("update") restriction.
  - If a page has NO restriction, it is left completely alone (nothing created).
  - NEVER removes any existing user/group restriction.
  - In WRITE mode, ADDS the current API user to the existing update restriction.

MODES (set MODE below)
  MODE = "audit"  -> read-only. Reports which restricted pages you lack edit on.
  MODE = "write"  -> adds you to restricted pages. Requires CONFIRM_WRITE = True.

SCOPE
  Reuses pages.json from the most recent *_confluence data run (all 53K pages).
  Falls back to enumerating via API if not found.
  SKIP_PERSONAL controls whether personal (~) spaces are included.

Env: FTDR_CLOUD_PAT, CLOUD_ADMIN_USER, CLOUD_SANDBOX_URL
Resumable: caches per-page restriction results; safe to re-run to continue.
"""

import os
import sys
import json
import time
import csv
import socket
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from base64 import b64encode
from collections import defaultdict
from datetime import datetime

# ---- Run configuration ----
MODE = "write"            # "audit" (read-only) or "write" (grants access)
CONFIRM_WRITE = True     # MUST be True for MODE="write" to actually modify anything
SKIP_PERSONAL = False     # True = skip personal (~) spaces
CHECKPOINT_EVERY = 500
REQUEST_TIMEOUT = 15
# ---------------------------

SITE = os.environ.get("CLOUD_SANDBOX_URL", "https://ftdr-sandbox-438.atlassian.net").rstrip("/")
EMAIL = os.environ.get("CLOUD_ADMIN_USER")
PAT = os.environ.get("FTDR_CLOUD_PAT")

if not PAT or not EMAIL:
    print("ERROR: Set CLOUD_ADMIN_USER and FTDR_CLOUD_PAT.")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")
data_root = os.path.join(PROJECT_ROOT, "data")
os.makedirs(REPORT_DIR, exist_ok=True)

credentials = b64encode(f"{EMAIL}:{PAT}".encode()).decode()
HEADERS = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def api_call(method, endpoint, retries=4):
    url = f"{SITE}{endpoint}"
    for attempt in range(retries):
        req = Request(url, headers=HEADERS, method=method)
        try:
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = resp.read()
                data = json.loads(body) if body else {}
                return resp.status, data
        except HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 5))
                log(f"    Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            return e.code, {}
        except (URLError, socket.timeout, TimeoutError):
            time.sleep(2 * (attempt + 1))
            continue
    return 0, {}


def get_current_user():
    status, data = api_call("GET", "/wiki/rest/api/user/current")
    if status != 200:
        log(f"ERROR: could not identify current user (HTTP {status})")
        sys.exit(1)
    return data["accountId"], data.get("displayName", "?"), data.get("email", "")


def load_pages():
    """Reuse pages.json from the latest confluence data run."""
    conf_dirs = sorted([d for d in os.listdir(data_root) if d.endswith("_confluence")], reverse=True)
    for d in conf_dirs:
        pj = os.path.join(data_root, d, "pages.json")
        if os.path.exists(pj):
            with open(pj) as f:
                pages = json.load(f)
            log(f"  Loaded {len(pages)} pages from {d}/pages.json")
            return pages, os.path.join(data_root, d)
    log("  No cached pages.json found — enumerate with 06_confluence_audit.py first.")
    sys.exit(1)


def get_update_restriction(page_id):
    """Return (is_restricted, user_account_ids, group_names)."""
    status, data = api_call("GET", f"/wiki/rest/api/content/{page_id}/restriction/byOperation/update")
    if status != 200:
        return None, [], []  # None = could not read
    users = [u["accountId"] for u in data.get("restrictions", {}).get("user", {}).get("results", [])]
    groups = [g.get("name", g.get("id", "")) for g in data.get("restrictions", {}).get("group", {}).get("results", [])]
    is_restricted = bool(users or groups)
    return is_restricted, users, groups


def add_user_to_update(page_id, account_id):
    """Additive: add user to existing update restriction. Does not remove anything.

    Confluence Cloud expects accountId as a query parameter, not a path segment.
    """
    acct = quote(account_id, safe="")
    ep = f"/wiki/rest/api/content/{page_id}/restriction/byOperation/update/user?accountId={acct}"
    status, _ = api_call("PUT", ep)
    if 200 <= status < 300:
        return True, status
    # Fallback: some instances accept the path form
    ep2 = f"/wiki/rest/api/content/{page_id}/restriction/byOperation/update/user/accountId/{acct}"
    status2, _ = api_call("PUT", ep2)
    return (200 <= status2 < 300), (status2 if status2 else status)


def main():
    log("=" * 60)
    log("  Confluence Edit-Access Audit + Grant — FrontDoor")
    log(f"  Site: {SITE}")
    log(f"  MODE: {MODE}  (CONFIRM_WRITE={CONFIRM_WRITE})")
    log(f"  SKIP_PERSONAL: {SKIP_PERSONAL}")
    log("=" * 60)

    if MODE == "write" and not CONFIRM_WRITE:
        log("")
        log("  ⚠️  MODE=write but CONFIRM_WRITE=False.")
        log("  Running as a DRY RUN — no changes will be made.")
        log("  Set CONFIRM_WRITE=True to actually grant access.")
        log("")

    account_id, display_name, user_email = get_current_user()
    log(f"  API user: {display_name} ({user_email})")
    log(f"  accountId: {account_id}")

    pages, conf_dir = load_pages()

    # Restriction cache for resumability
    cache_path = os.path.join(conf_dir, "edit_restrictions_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            cache = json.load(f)
        log(f"  Resuming — {len(cache)} pages already scanned")

    # ================================================================
    # Phase 1: Scan restrictions
    # ================================================================
    log("")
    log("=== Phase 1: Scanning edit restrictions ===")

    scanned = 0
    for i, p in enumerate(pages, 1):
        pid = str(p["page_id"])
        skey = p["space_key"]

        if SKIP_PERSONAL and skey.startswith("~"):
            continue
        if pid in cache:
            continue

        is_restricted, users, groups = get_update_restriction(pid)
        cache[pid] = {
            "space_key": skey,
            "title": p.get("title", ""),
            "restricted": is_restricted,
            "user_has_edit": account_id in users if is_restricted else None,
            "user_count": len(users),
            "groups": groups,
            "read_error": is_restricted is None,
        }
        scanned += 1

        if scanned % 100 == 0:
            log(f"  Scanned {scanned} new pages (cache: {len(cache)})...")
        if scanned % CHECKPOINT_EVERY == 0:
            with open(cache_path, "w") as f:
                json.dump(cache, f)
        time.sleep(0.08)

    with open(cache_path, "w") as f:
        json.dump(cache, f)
    log(f"  Scan complete. {len(cache)} pages in cache.")

    # ================================================================
    # Analyze
    # ================================================================
    considered = [v for v in cache.values()
                  if not (SKIP_PERSONAL and v["space_key"].startswith("~"))]
    restricted = [v for v in considered if v.get("restricted")]
    have_access = [v for v in restricted if v.get("user_has_edit")]
    need_access = [v for v in restricted if v.get("restricted") and not v.get("user_has_edit")]
    read_errors = [v for v in considered if v.get("read_error")]

    by_space = defaultdict(lambda: {"restricted": 0, "need": 0})
    for v in restricted:
        by_space[v["space_key"]]["restricted"] += 1
        if not v.get("user_has_edit"):
            by_space[v["space_key"]]["need"] += 1

    log("")
    log("=== Summary ===")
    log(f"  Pages considered:        {len(considered):,}")
    log(f"  Edit-restricted pages:   {len(restricted):,}")
    log(f"  Already have edit:       {len(have_access):,}")
    log(f"  Missing edit access:     {len(need_access):,}")
    log(f"  Unreadable (perm):       {len(read_errors):,}")

    # ================================================================
    # Phase 2: WRITE (only if MODE=write AND CONFIRM_WRITE)
    # ================================================================
    granted = 0
    grant_failed = 0
    if MODE == "write" and CONFIRM_WRITE:
        log("")
        log(f"=== Phase 2: Granting edit access to {len(need_access):,} pages ===")
        log("  (Additive only — no existing restriction is removed)")
        # Rebuild list of page_ids needing access
        need_ids = [pid for pid, v in cache.items()
                    if v.get("restricted") and not v.get("user_has_edit")
                    and not (SKIP_PERSONAL and v["space_key"].startswith("~"))]
        for n, pid in enumerate(need_ids, 1):
            ok, status = add_user_to_update(pid, account_id)
            if ok:
                granted += 1
                cache[pid]["user_has_edit"] = True
            else:
                grant_failed += 1
                log(f"    Failed page {pid}: HTTP {status}")
            if n % 50 == 0:
                log(f"    Granted {granted}/{len(need_ids)}...")
                with open(cache_path, "w") as f:
                    json.dump(cache, f)
            time.sleep(0.12)
        with open(cache_path, "w") as f:
            json.dump(cache, f)
        log(f"  Grant complete: {granted} succeeded, {grant_failed} failed")

    # ================================================================
    # Report
    # ================================================================
    report_path = os.path.join(REPORT_DIR, "13_confluence_edit_access.md")
    with open(report_path, "w") as f:
        f.write("# Confluence Edit-Access Audit — FrontDoor\n")
        f.write(f"# Site: {SITE}\n")
        f.write(f"# User: {display_name} ({user_email})\n")
        f.write(f"# Mode: {MODE}{' (DRY RUN)' if MODE=='write' and not CONFIRM_WRITE else ''}\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write("## Summary\n\n")
        f.write("| Metric | Value |\n|---|---|\n")
        f.write(f"| Pages considered | {len(considered):,} |\n")
        f.write(f"| Edit-restricted pages | {len(restricted):,} |\n")
        f.write(f"| Already have edit access | {len(have_access):,} |\n")
        f.write(f"| **Missing edit access** | **{len(need_access):,}** |\n")
        f.write(f"| Unreadable (no permission) | {len(read_errors):,} |\n")
        if MODE == "write" and CONFIRM_WRITE:
            f.write(f"| Access granted this run | {granted:,} |\n")
            f.write(f"| Grants failed | {grant_failed:,} |\n")
        f.write(f"| Personal spaces included | {'No' if SKIP_PERSONAL else 'Yes'} |\n\n")

        f.write("_Only pages with an existing edit restriction are counted. Unrestricted "
                "pages are left untouched — nothing is created or removed._\n\n")

        f.write("## Restricted Pages Missing Your Edit Access, by Space\n\n")
        f.write("| Space | Restricted Pages | You Lack Edit |\n|---|---|---|\n")
        for skey, counts in sorted(by_space.items(), key=lambda x: -x[1]["need"]):
            if counts["need"] > 0:
                f.write(f"| {skey} | {counts['restricted']} | {counts['need']} |\n")

        f.write(f"\n## Pages Missing Edit Access (top 200 of {len(need_access):,})\n\n")
        f.write("| Space | Page | Allowed Users | Groups |\n|---|---|---|---|\n")
        for v in sorted(need_access, key=lambda x: x["space_key"])[:200]:
            groups = ", ".join(v["groups"]) if v["groups"] else "—"
            f.write(f"| {v['space_key']} | {v['title']} | {v['user_count']} | {groups} |\n")

        if read_errors:
            f.write(f"\n## Unreadable Pages ({len(read_errors):,})\n\n")
            f.write("Pages whose restrictions couldn't be read (you may lack even view access). "
                    "These can't be self-granted via this script.\n\n")

        f.write("\n## Notes\n\n")
        f.write("- Grants are **additive**: your account is added to the existing update "
                "restriction; no other user or group is removed.\n")
        f.write("- Pages with **no** restriction are intentionally skipped — full site edit "
                "access there comes from space permissions, not page restrictions.\n")
        f.write("- **Read restrictions** are separate; this audit covers edit (update) only. "
                "Pages you can't view show under 'Unreadable'.\n")

    log(f"  → {report_path}")

    # CSV
    csv_path = os.path.join(REPORT_DIR, "confluence_edit_access.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Space", "Page ID", "Title", "Restricted", "You Have Edit",
                    "Allowed User Count", "Groups", "Read Error"])
        for pid, v in cache.items():
            if SKIP_PERSONAL and v["space_key"].startswith("~"):
                continue
            w.writerow([v["space_key"], pid, v["title"], v.get("restricted"),
                        v.get("user_has_edit"), v.get("user_count"),
                        "; ".join(v.get("groups", [])), v.get("read_error")])
    log(f"  → {csv_path}")

    log("")
    log("=" * 60)
    log("  DONE")
    log("=" * 60)
    if MODE == "audit":
        log(f"  {len(need_access):,} restricted pages where you lack edit access.")
        log("  To grant: set MODE='write' AND CONFIRM_WRITE=True, then re-run.")
    elif not CONFIRM_WRITE:
        log(f"  DRY RUN: would grant access to {len(need_access):,} pages.")
        log("  Set CONFIRM_WRITE=True to apply.")
    else:
        log(f"  Granted edit access to {granted:,} pages.")
    log("")


if __name__ == "__main__":
    main()
