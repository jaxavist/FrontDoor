"""
Confluence Usage Audit — FrontDoor
Site: ftdr-sandbox-438.atlassian.net (override with CLOUD_SANDBOX_URL)

Produces a site activity map to inform space consolidation:
  - All spaces by type (global / collaboration / personal / archived)
  - Space last-activity (most recent page update)
  - Page count and distinct contributors ("users in space" proxy) per space
  - Total views + distinct viewers per space (Analytics API)
  - Never-visited / rarely-visited pages
  - Stale spaces (no updates in 1yr / 2yr)
  - Pages never updated since creation
  - Personal / archived / empty spaces (cleanup candidates)

Env vars required:
  FTDR_CLOUD_PAT     - API token
  CLOUD_ADMIN_USER   - admin email for Basic auth
  CLOUD_SANDBOX_URL  - site base URL (optional, defaults to sandbox)

NOTE ON ANALYTICS: The Analytics API (/wiki/rest/api/analytics/...) returns real
view/viewer counts on Premium+ plans. Sandbox copies often have NO analytics
history, so counts may all be 0. Run against production for real visit data.
Set COLLECT_ANALYTICS = False to skip analytics and run much faster.
"""

import os
import sys
import json
import time
import csv
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from base64 import b64encode
from collections import defaultdict
from datetime import datetime, timezone

SITE = os.environ.get("CLOUD_SANDBOX_URL", "https://ftdr-sandbox-438.atlassian.net").rstrip("/")
EMAIL = os.environ.get("CLOUD_ADMIN_USER")
PAT = os.environ.get("FTDR_CLOUD_PAT")

COLLECT_ANALYTICS = True   # set False to skip view/viewer counts (much faster)
PAGE_LIMIT_PER_SPACE = 0   # 0 = all pages; set e.g. 200 to cap per space

if not PAT or not EMAIL:
    print("ERROR: Set both CLOUD_ADMIN_USER and FTDR_CLOUD_PAT environment variables.")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")
DATA_OUT = os.path.join(PROJECT_ROOT, "data", datetime.now().strftime("%Y%m%d") + "_confluence")
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(DATA_OUT, exist_ok=True)

credentials = b64encode(f"{EMAIL}:{PAT}".encode()).decode()
HEADERS = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}

NOW = datetime.now(timezone.utc)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def api_get(endpoint):
    url = f"{SITE}{endpoint}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode() if e.readable() else ""
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": e.reason, "body": body[:200]}
    except URLError as e:
        return 0, {"error": str(e.reason)}


def days_since(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (NOW - dt).days
    except Exception:
        return None


def main():
    log("=" * 60)
    log("  Confluence Usage Audit — FrontDoor")
    log(f"  Site: {SITE}")
    log(f"  Analytics: {'ON' if COLLECT_ANALYTICS else 'OFF'}")
    log("=" * 60)

    # ================================================================
    # 1. Collect all spaces (v2 API — created date, owner, type)
    # ================================================================
    log("")
    log("=== Phase 1: Collecting Spaces ===")

    spaces = []
    cursor = None
    while True:
        ep = "/wiki/api/v2/spaces?limit=100" + (f"&cursor={quote(cursor)}" if cursor else "")
        status, data = api_get(ep)
        if status != 200:
            log(f"  v2 spaces returned {status}: {data}")
            break
        spaces.extend(data.get("results", []))
        links = data.get("_links", {})
        next_link = links.get("next", "")
        if not next_link or "cursor=" not in next_link:
            break
        cursor = next_link.split("cursor=")[1].split("&")[0]
        from urllib.parse import unquote
        cursor = unquote(cursor)
        log(f"  Collected {len(spaces)} spaces...")

    log(f"  Total spaces: {len(spaces)}")

    with open(os.path.join(DATA_OUT, "spaces.json"), "w") as f:
        json.dump(spaces, f, indent=2)

    # ================================================================
    # 2. Per-space: pages, contributors, last activity
    # ================================================================
    log("")
    log("=== Phase 2: Collecting Pages per Space ===")

    space_stats = {}
    all_pages = []  # for page-level report

    for si, space in enumerate(spaces, 1):
        skey = space["key"]
        sname = space.get("name", skey)
        stype = space.get("type", "unknown")
        if si % 10 == 0 or si == 1:
            log(f"  [{si}/{len(spaces)}] {skey} ({sname})...")

        pages = []
        start = 0
        limit = 100
        while True:
            ep = (f"/wiki/rest/api/content?spaceKey={quote(skey)}&type=page"
                  f"&limit={limit}&start={start}&expand=history.lastUpdated,version,history")
            status, data = api_get(ep)
            if status != 200:
                break
            results = data.get("results", [])
            pages.extend(results)
            start += limit
            if PAGE_LIMIT_PER_SPACE and len(pages) >= PAGE_LIMIT_PER_SPACE:
                break
            if len(results) < limit:
                break
            time.sleep(0.1)

        # Analyze pages
        contributors = set()
        last_activity = None
        created_dates = []
        never_updated = 0  # pages where version == 1 (never edited after creation)

        for p in pages:
            hist = p.get("history", {})
            last_up = hist.get("lastUpdated", {})
            when = last_up.get("when")
            if when and (last_activity is None or when > last_activity):
                last_activity = when

            # contributors
            cb = hist.get("createdBy", {})
            if cb.get("accountId"):
                contributors.add(cb["accountId"])
            vby = p.get("version", {}).get("by", {})
            if vby.get("accountId"):
                contributors.add(vby["accountId"])

            created = hist.get("createdDate")
            if created:
                created_dates.append(created)

            if p.get("version", {}).get("number", 0) <= 1:
                never_updated += 1

            all_pages.append({
                "space_key": skey,
                "space_name": sname,
                "page_id": p["id"],
                "title": p.get("title", ""),
                "last_updated": when,
                "created": created,
                "version": p.get("version", {}).get("number", 0),
                "views": None,
                "viewers": None,
            })

        space_stats[skey] = {
            "key": skey,
            "name": sname,
            "type": stype,
            "status": space.get("status", ""),
            "created": space.get("createdAt"),
            "owner_id": space.get("spaceOwnerId") or space.get("authorId"),
            "page_count": len(pages),
            "contributor_count": len(contributors),
            "contributors": list(contributors),
            "last_activity": last_activity,
            "last_activity_days": days_since(last_activity),
            "never_updated_pages": never_updated,
            "total_views": 0,
            "total_viewers": 0,
        }
        time.sleep(0.15)

    log(f"  Collected pages for {len(space_stats)} spaces ({len(all_pages)} total pages)")

    # Checkpoint the expensive collection immediately, BEFORE analytics.
    # This ensures an interrupted analytics phase never loses Phase 1/2 work.
    with open(os.path.join(DATA_OUT, "space_stats.json"), "w") as f:
        json.dump(space_stats, f, indent=2)
    with open(os.path.join(DATA_OUT, "pages.json"), "w") as f:
        json.dump(all_pages, f, indent=2)
    log(f"  Checkpoint saved: space_stats.json + pages.json ({DATA_OUT})")

    # ================================================================
    # 3. Analytics: views + viewers per page
    # ================================================================
    if COLLECT_ANALYTICS:
        log("")
        log("=== Phase 3: Analytics (Views + Viewers) ===")
        log(f"  Querying analytics for {len(all_pages)} pages (2 calls each)...")
        log("  This is the slow phase. Set COLLECT_ANALYTICS=False to skip.")

        total_views_all = 0
        for i, page in enumerate(all_pages, 1):
            if i % 100 == 0:
                log(f"  [{i}/{len(all_pages)}] analytics...")
            pid = page["page_id"]

            status, data = api_get(f"/wiki/rest/api/analytics/content/{pid}/views")
            views = data.get("count", 0) if status == 200 else 0

            status2, data2 = api_get(f"/wiki/rest/api/analytics/content/{pid}/viewers")
            viewers = data2.get("count", 0) if status2 == 200 else 0

            page["views"] = views
            page["viewers"] = viewers
            total_views_all += views

            sk = page["space_key"]
            if sk in space_stats:
                space_stats[sk]["total_views"] += views
                space_stats[sk]["total_viewers"] += viewers

            time.sleep(0.1)

        log(f"  Total views across all pages: {total_views_all:,}")
        if total_views_all == 0:
            log("  ⚠️  All view counts are 0 — this sandbox likely has no analytics")
            log("     history. Run against PRODUCTION for real visit data.")
    else:
        log("")
        log("=== Phase 3: Analytics SKIPPED (COLLECT_ANALYTICS=False) ===")

    # ================================================================
    # 4. Analysis
    # ================================================================
    log("")
    log("=== Phase 4: Analysis ===")

    spaces_list = list(space_stats.values())
    type_counts = defaultdict(int)
    for s in spaces_list:
        type_counts[s["type"]] += 1

    stale_1yr = [s for s in spaces_list if s["last_activity_days"] is not None and s["last_activity_days"] > 365]
    stale_2yr = [s for s in spaces_list if s["last_activity_days"] is not None and s["last_activity_days"] > 730]
    empty_spaces = [s for s in spaces_list if s["page_count"] <= 1]
    personal_spaces = [s for s in spaces_list if s["type"] == "personal"]
    single_contributor = [s for s in spaces_list if s["contributor_count"] <= 1 and s["page_count"] > 1]

    never_viewed_pages = [p for p in all_pages if p["views"] == 0] if COLLECT_ANALYTICS else []
    rarely_viewed_pages = [p for p in all_pages if p["views"] is not None and 0 < p["views"] <= 5] if COLLECT_ANALYTICS else []

    analytics_has_data = COLLECT_ANALYTICS and any((p["views"] or 0) > 0 for p in all_pages)

    log(f"  Spaces: {len(spaces_list)}")
    log(f"  Stale >1yr: {len(stale_1yr)}, >2yr: {len(stale_2yr)}")
    log(f"  Empty (<=1 page): {len(empty_spaces)}")
    log(f"  Personal: {len(personal_spaces)}")

    # ================================================================
    # 5. Report
    # ================================================================
    log("")
    log("=== Phase 5: Report ===")

    report_path = os.path.join(REPORT_DIR, "12_confluence_usage_audit.md")
    with open(report_path, "w") as f:
        f.write("# Confluence Usage Audit — FrontDoor\n")
        f.write(f"# Site: {SITE}\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        if COLLECT_ANALYTICS and not analytics_has_data:
            f.write("> **⚠️ Analytics caveat:** All page view counts returned 0. This instance\n")
            f.write("> has no analytics history (common for sandbox copies). View-based metrics\n")
            f.write("> below are unreliable — re-run against the production site for real visit data.\n")
            f.write("> Modified-date, page-count, and contributor metrics are accurate.\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|---|---|\n")
        f.write(f"| Total spaces | {len(spaces_list)} |\n")
        for stype, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            f.write(f"| — {stype} spaces | {cnt} |\n")
        f.write(f"| Total pages | {len(all_pages):,} |\n")
        f.write(f"| Stale spaces (no update >1yr) | {len(stale_1yr)} |\n")
        f.write(f"| Stale spaces (no update >2yr) | {len(stale_2yr)} |\n")
        f.write(f"| Empty spaces (<=1 page) | {len(empty_spaces)} |\n")
        f.write(f"| Personal spaces | {len(personal_spaces)} |\n")
        f.write(f"| Single-contributor spaces | {len(single_contributor)} |\n")
        if COLLECT_ANALYTICS:
            f.write(f"| Never-viewed pages | {len(never_viewed_pages):,} |\n")
            f.write(f"| Rarely-viewed pages (1-5 views) | {len(rarely_viewed_pages):,} |\n")
        f.write(f"| **Space consolidation candidates** | **{len(set(s['key'] for s in stale_1yr + empty_spaces + personal_spaces))}** |\n\n")

        # Space activity map — the core deliverable
        f.write("## Space Activity Map\n\n")
        f.write("All spaces ranked by last activity. Older = stronger consolidation candidate.\n\n")
        f.write("| Space | Key | Type | Pages | Contributors | Last Activity | Days Idle | Views |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for s in sorted(spaces_list, key=lambda x: (x["last_activity_days"] is None, -(x["last_activity_days"] or 0))):
            la = (s["last_activity"] or "")[:10] or "never"
            idle = s["last_activity_days"] if s["last_activity_days"] is not None else "—"
            views = f"{s['total_views']:,}" if COLLECT_ANALYTICS else "n/a"
            f.write(f"| {s['name']} | {s['key']} | {s['type']} | {s['page_count']} | {s['contributor_count']} | {la} | {idle} | {views} |\n")

        # Stale spaces
        f.write(f"\n## Stale Spaces — No Updates in Over 1 Year ({len(stale_1yr)})\n\n")
        f.write("| Space | Key | Type | Pages | Last Activity | Days Idle |\n")
        f.write("|---|---|---|---|---|---|\n")
        for s in sorted(stale_1yr, key=lambda x: -(x["last_activity_days"] or 0)):
            f.write(f"| {s['name']} | {s['key']} | {s['type']} | {s['page_count']} | {(s['last_activity'] or '')[:10]} | {s['last_activity_days']} |\n")

        # Empty spaces
        f.write(f"\n## Empty / Near-Empty Spaces ({len(empty_spaces)})\n\n")
        f.write("Spaces with only a homepage (or no pages) — prime deletion candidates.\n\n")
        f.write("| Space | Key | Type | Pages |\n")
        f.write("|---|---|---|---|\n")
        for s in sorted(empty_spaces, key=lambda x: x["name"].lower()):
            f.write(f"| {s['name']} | {s['key']} | {s['type']} | {s['page_count']} |\n")

        # Personal spaces
        f.write(f"\n## Personal Spaces ({len(personal_spaces)})\n\n")
        f.write("Personal spaces often accumulate as orphaned content. Review for archival.\n\n")
        f.write("| Space Name | Key | Pages | Last Activity | Days Idle |\n")
        f.write("|---|---|---|---|---|\n")
        for s in sorted(personal_spaces, key=lambda x: (x["last_activity_days"] is None, -(x["last_activity_days"] or 0))):
            f.write(f"| {s['name']} | {s['key']} | {s['page_count']} | {(s['last_activity'] or '')[:10] or 'never'} | {s['last_activity_days'] if s['last_activity_days'] is not None else '—'} |\n")

        # Never/rarely viewed pages
        if COLLECT_ANALYTICS and analytics_has_data:
            f.write(f"\n## Never-Viewed Pages ({len(never_viewed_pages):,})\n\n")
            f.write("Pages with zero recorded views. Top 100 shown; full list in CSV.\n\n")
            f.write("| Page | Space | Last Updated | Version |\n")
            f.write("|---|---|---|---|\n")
            for p in sorted(never_viewed_pages, key=lambda x: x["space_key"])[:100]:
                f.write(f"| {p['title']} | {p['space_key']} | {(p['last_updated'] or '')[:10]} | {p['version']} |\n")

            f.write(f"\n## Rarely-Viewed Pages — 1 to 5 Views ({len(rarely_viewed_pages):,})\n\n")
            f.write("| Page | Space | Views | Last Updated |\n")
            f.write("|---|---|---|---|\n")
            for p in sorted(rarely_viewed_pages, key=lambda x: x["views"])[:100]:
                f.write(f"| {p['title']} | {p['space_key']} | {p['views']} | {(p['last_updated'] or '')[:10]} |\n")

        # Recommendations
        f.write("\n## Consolidation Recommendations\n\n")
        f.write("### Immediate cleanup\n")
        f.write(f"1. **Archive/delete {len(empty_spaces)} empty spaces** — homepage-only, no real content\n")
        f.write(f"2. **Review {len(stale_2yr)} spaces idle >2 years** — likely abandoned\n")
        f.write(f"3. **Consolidate {len(personal_spaces)} personal spaces** — migrate valuable content, archive the rest\n")
        f.write("\n### Restructuring guidance\n")
        f.write(f"4. **{len(stale_1yr)} spaces idle >1yr** should be evaluated for merge into active spaces\n")
        f.write(f"5. **{len(single_contributor)} single-contributor spaces** may belong to individuals who left or should merge\n")
        if COLLECT_ANALYTICS and analytics_has_data:
            f.write("6. Use view data to identify which spaces to keep as canonical vs. archive\n")
        else:
            f.write("6. **Re-run against production** to layer real view/visit data onto this activity map\n")

    log(f"  → {report_path}")

    # ================================================================
    # CSV exports
    # ================================================================
    space_csv = os.path.join(REPORT_DIR, "confluence_spaces.csv")
    with open(space_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Space Name", "Key", "Type", "Status", "Pages", "Contributors",
                    "Last Activity", "Days Idle", "Never-Updated Pages",
                    "Total Views", "Total Viewers", "Created"])
        for s in sorted(spaces_list, key=lambda x: (x["last_activity_days"] is None, -(x["last_activity_days"] or 0))):
            w.writerow([s["name"], s["key"], s["type"], s["status"], s["page_count"],
                        s["contributor_count"], (s["last_activity"] or "")[:10],
                        s["last_activity_days"] if s["last_activity_days"] is not None else "",
                        s["never_updated_pages"], s["total_views"], s["total_viewers"],
                        (s["created"] or "")[:10]])
    log(f"  → {space_csv}")

    page_csv = os.path.join(REPORT_DIR, "confluence_pages.csv")
    with open(page_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Page Title", "Space Key", "Space Name", "Page ID",
                    "Last Updated", "Created", "Version", "Views", "Viewers"])
        for p in all_pages:
            w.writerow([p["title"], p["space_key"], p["space_name"], p["page_id"],
                        (p["last_updated"] or "")[:10], (p["created"] or "")[:10],
                        p["version"],
                        p["views"] if p["views"] is not None else "n/a",
                        p["viewers"] if p["viewers"] is not None else "n/a"])
    log(f"  → {page_csv}")

    # Save raw data
    with open(os.path.join(DATA_OUT, "space_stats.json"), "w") as f:
        json.dump(space_stats, f, indent=2)
    with open(os.path.join(DATA_OUT, "pages.json"), "w") as f:
        json.dump(all_pages, f, indent=2)

    # ================================================================
    log("")
    log("=" * 60)
    log("  CONFLUENCE USAGE AUDIT COMPLETE")
    log("=" * 60)
    log(f"  Total spaces:          {len(spaces_list)}")
    log(f"  Total pages:           {len(all_pages):,}")
    log(f"  Stale >1yr:            {len(stale_1yr)}")
    log(f"  Empty spaces:          {len(empty_spaces)}")
    log(f"  Personal spaces:       {len(personal_spaces)}")
    if COLLECT_ANALYTICS:
        log(f"  Never-viewed pages:    {len(never_viewed_pages):,}")
        log(f"  Analytics has data:    {analytics_has_data}")
    log("")


if __name__ == "__main__":
    main()
