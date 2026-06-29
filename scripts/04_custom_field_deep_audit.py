"""
Jira Align Readiness Audit — Custom Field Deep Audit
Site: ftdr-sandbox-438.atlassian.net

Produces detailed metrics on:
  - Overall usage (populated vs empty across issues)
  - Usage by field type
  - Unused / low-usage fields (cleanup candidates)
  - Field → Field Configuration Scheme → Project associations
  - Align-relevant field analysis
  - Duplicate/similar field detection

Requires: FTDR_CLOUD_PAT environment variable
Uses data already collected in data/ directory
"""

import os
import sys
import json
import time
import csv
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from base64 import b64encode
from collections import defaultdict
from datetime import datetime

SITE = "https://ftdr-sandbox-438.atlassian.net"
EMAIL = "jax.kane@frontdoor.com"
PAT = os.environ.get("FTDR_CLOUD_PAT")

if not PAT:
    print("ERROR: Set FTDR_CLOUD_PAT environment variable first.")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# Find most recent data directory
DATA_DIR = None
data_root = os.path.join(PROJECT_ROOT, "data")
if os.path.isdir(data_root):
    dates = sorted([d for d in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, d))], reverse=True)
    if dates:
        DATA_DIR = os.path.join(data_root, dates[0])

if not DATA_DIR:
    print("ERROR: No data directory found. Run 01_collect_config_data.sh first.")
    sys.exit(1)

credentials = b64encode(f"{EMAIL}:{PAT}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
}


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


def api_get_paginated(endpoint, values_key="values", page_size=50):
    results = []
    start = 0
    while True:
        sep = "&" if "?" in endpoint else "?"
        status, data = api_get(f"{endpoint}{sep}startAt={start}&maxResults={page_size}")
        if status != 200:
            break
        page = data.get(values_key, [])
        results.extend(page)
        total = data.get("total", 0)
        start += page_size
        if not page or start >= total:
            break
    return results


def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return []


def get_field_usage_count(field_key):
    """Use JQL to count issues where a custom field is populated."""
    field_id = field_key.replace("customfield_", "cf[") + "]"
    jql = f"{field_id}+is+not+EMPTY"
    status, data = api_get(f"/rest/api/3/search/jql?jql={jql}&maxResults=0")
    if status == 200:
        return data.get("total", 0)
    return -1  # -1 means query failed (field may not be searchable)


def main():
    log("=" * 60)
    log("  Custom Field Deep Audit")
    log(f"  Data source: {DATA_DIR}")
    log(f"  Reports: {REPORT_DIR}")
    log("=" * 60)

    # ================================================================
    # Load existing data
    # ================================================================
    log("Loading collected data...")
    all_fields = load_json("fields.json")
    custom_fields = load_json("custom_fields.json")
    field_configs = load_json("field_configurations.json")
    field_config_schemes = load_json("field_config_schemes.json")
    projects = load_json("projects.json")

    log(f"  {len(custom_fields)} custom fields")
    log(f"  {len(field_configs)} field configurations")
    log(f"  {len(field_config_schemes)} field config schemes")
    log(f"  {len(projects)} projects")

    # ================================================================
    # 1. Get field usage counts via JQL
    # ================================================================
    log("")
    log("=== Phase 1: Field Usage Counts (JQL) ===")
    log(f"Querying usage for {len(custom_fields)} custom fields...")
    log("(This will take several minutes — one API call per field)")
    log("")

    field_usage = {}
    total = len(custom_fields)
    for i, field in enumerate(custom_fields, 1):
        key = field["key"]
        name = field["name"]
        if i % 25 == 0 or i == 1:
            log(f"  [{i}/{total}] Processing {name}...")

        count = get_field_usage_count(key)
        field_usage[key] = {
            "name": name,
            "key": key,
            "type": field.get("schema", {}).get("type", "unknown"),
            "custom_type": field.get("schema", {}).get("custom", ""),
            "issue_count": count,
            "searchable": count >= 0,
        }
        time.sleep(0.2)  # rate limiting

    log(f"  Done. {sum(1 for v in field_usage.values() if v['issue_count'] > 0)} fields have data.")

    # ================================================================
    # 2. Get Field Configuration Scheme → Project mappings
    # ================================================================
    log("")
    log("=== Phase 2: Field Config Scheme → Project Mappings ===")

    fcs_project_map = defaultdict(list)  # scheme_id → [project_keys]
    fcs_projects = api_get_paginated("/rest/api/3/fieldconfigurationscheme/project")
    for mapping in fcs_projects:
        scheme_id = mapping.get("fieldConfigurationScheme", {}).get("id", "")
        scheme_name = mapping.get("fieldConfigurationScheme", {}).get("name", "")
        proj_ids = [p.get("id") for p in mapping.get("projectIds", [])] if "projectIds" in mapping else []
        # Sometimes the API nests differently
        if not proj_ids and "projectId" in mapping:
            proj_ids = [mapping["projectId"]]
        fcs_project_map[str(scheme_id)] = {
            "name": scheme_name,
            "project_ids": proj_ids,
        }

    log(f"  {len(fcs_project_map)} scheme-to-project mappings found")

    # ================================================================
    # 3. Get Field Configuration → Field mappings (which fields are in each config)
    # ================================================================
    log("")
    log("=== Phase 3: Field Configuration → Field Items ===")

    fc_field_map = {}  # config_id → [field_keys]
    for fc in field_configs:
        fc_id = fc.get("id", "")
        log(f"  Loading fields for config: {fc.get('name', fc_id)}...")
        items = api_get_paginated(f"/rest/api/3/fieldconfiguration/{fc_id}/fields")
        fc_field_map[str(fc_id)] = {
            "name": fc.get("name", ""),
            "fields": [item.get("id", "") for item in items],
            "field_count": len(items),
        }
        time.sleep(0.2)

    log(f"  {len(fc_field_map)} field configurations mapped")

    # ================================================================
    # 4. Get custom field contexts (project/issue type scope)
    # ================================================================
    log("")
    log("=== Phase 4: Custom Field Contexts (Scope) ===")

    field_contexts = {}
    for i, field in enumerate(custom_fields, 1):
        key = field["key"]
        field_id = key.replace("customfield_", "")
        if i % 50 == 0:
            log(f"  [{i}/{total}] Fetching contexts...")

        status, data = api_get(f"/rest/api/3/field/{key}/context?maxResults=100")
        if status == 200:
            contexts = data.get("values", [])
            field_contexts[key] = {
                "context_count": len(contexts),
                "is_global": any(c.get("isGlobalContext", False) for c in contexts),
                "project_count": sum(
                    len(c.get("projectIds", [])) for c in contexts
                    if not c.get("isGlobalContext", False)
                ),
            }
        else:
            field_contexts[key] = {"context_count": 0, "is_global": True, "project_count": 0}
        time.sleep(0.15)

    log(f"  Contexts fetched for {len(field_contexts)} fields")

    # ================================================================
    # 5. Get total issue count for percentage calculations
    # ================================================================
    log("")
    log("=== Phase 5: Total Issue Count ===")
    status, data = api_get("/rest/api/3/search/jql?jql=created+is+not+EMPTY&maxResults=0")
    total_issues = data.get("total", 0) if status == 200 else 0
    log(f"  Total issues in instance: {total_issues}")

    # ================================================================
    # Generate Reports
    # ================================================================
    log("")
    log("=== Generating Reports ===")

    # Categorize fields
    used_fields = []
    unused_fields = []
    low_usage_fields = []  # < 1% of total issues
    unsearchable_fields = []

    for key, usage in field_usage.items():
        if not usage["searchable"]:
            unsearchable_fields.append(usage)
        elif usage["issue_count"] == 0:
            unused_fields.append(usage)
        elif total_issues > 0 and (usage["issue_count"] / total_issues) < 0.01:
            low_usage_fields.append(usage)
            used_fields.append(usage)
        else:
            used_fields.append(usage)

    # Usage by type
    type_stats = defaultdict(lambda: {"count": 0, "used": 0, "unused": 0, "total_usage": 0})
    for key, usage in field_usage.items():
        ftype = usage["type"]
        type_stats[ftype]["count"] += 1
        if usage["issue_count"] > 0:
            type_stats[ftype]["used"] += 1
            type_stats[ftype]["total_usage"] += usage["issue_count"]
        elif usage["searchable"]:
            type_stats[ftype]["unused"] += 1

    # Align-relevant fields
    align_keywords = [
        "story point", "sprint", "epic link", "epic name", "rank",
        "team", "program", "portfolio", "pi", "iteration",
        "feature", "capability", "theme", "align",
        "acceptance criteria", "definition of done",
    ]

    align_relevant = []
    for key, usage in field_usage.items():
        name_lower = usage["name"].lower()
        for kw in align_keywords:
            if kw in name_lower:
                align_relevant.append({**usage, "match": kw})
                break

    # Duplicate detection (similar names)
    from difflib import SequenceMatcher
    name_groups = defaultdict(list)
    field_names = [(f["key"], f["name"]) for f in custom_fields]
    duplicates = []
    seen_pairs = set()
    for i, (key1, name1) in enumerate(field_names):
        for key2, name2 in field_names[i+1:]:
            pair = tuple(sorted([key1, key2]))
            if pair in seen_pairs:
                continue
            ratio = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
            if ratio > 0.85 and name1.lower() != name2.lower():
                seen_pairs.add(pair)
                duplicates.append({
                    "field1_key": key1, "field1_name": name1,
                    "field2_key": key2, "field2_name": name2,
                    "similarity": round(ratio * 100, 1),
                })

    # ================================================================
    # Write Markdown Report
    # ================================================================
    report_path = os.path.join(REPORT_DIR, "10_custom_field_deep_audit.md")
    with open(report_path, "w") as f:
        f.write("# Custom Field Deep Audit\n")
        f.write(f"# Site: ftdr-sandbox-438.atlassian.net\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|---|---|\n")
        f.write(f"| Total custom fields | {len(custom_fields)} |\n")
        f.write(f"| Fields with data (populated) | {len(used_fields)} |\n")
        f.write(f"| Fields with ZERO usage | {len(unused_fields)} |\n")
        f.write(f"| Fields with <1% usage | {len(low_usage_fields)} |\n")
        f.write(f"| Fields not searchable (JQL) | {len(unsearchable_fields)} |\n")
        f.write(f"| Total issues in instance | {total_issues:,} |\n")
        f.write(f"| **Cleanup candidates (unused + low)** | **{len(unused_fields) + len(low_usage_fields)}** |\n\n")

        # Usage by type
        f.write("## Usage by Field Type\n\n")
        f.write("| Field Type | Total | Used | Unused | Avg Usage (issues) |\n")
        f.write("|---|---|---|---|---|\n")
        for ftype, stats in sorted(type_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            avg = round(stats["total_usage"] / stats["used"]) if stats["used"] > 0 else 0
            f.write(f"| {ftype} | {stats['count']} | {stats['used']} | {stats['unused']} | {avg:,} |\n")

        # Top used fields
        f.write("\n## Top 50 Most Used Custom Fields\n\n")
        f.write("| Rank | Field Name | Key | Type | Issues | % of Total |\n")
        f.write("|---|---|---|---|---|---|\n")
        top_used = sorted(
            [u for u in field_usage.values() if u["issue_count"] > 0],
            key=lambda x: x["issue_count"], reverse=True
        )[:50]
        for rank, u in enumerate(top_used, 1):
            pct = round(u["issue_count"] / total_issues * 100, 1) if total_issues > 0 else 0
            f.write(f"| {rank} | {u['name']} | {u['key']} | {u['type']} | {u['issue_count']:,} | {pct}% |\n")

        # Unused fields
        f.write(f"\n## Unused Custom Fields ({len(unused_fields)} fields — deletion candidates)\n\n")
        f.write("| Field Name | Key | Type | Custom Type |\n")
        f.write("|---|---|---|---|\n")
        for u in sorted(unused_fields, key=lambda x: x["name"]):
            f.write(f"| {u['name']} | {u['key']} | {u['type']} | {u['custom_type']} |\n")

        # Low usage fields
        f.write(f"\n## Low Usage Fields (<1% population — {len(low_usage_fields)} fields)\n\n")
        f.write("| Field Name | Key | Type | Issues | % of Total |\n")
        f.write("|---|---|---|---|---|\n")
        for u in sorted(low_usage_fields, key=lambda x: x["issue_count"]):
            pct = round(u["issue_count"] / total_issues * 100, 2) if total_issues > 0 else 0
            f.write(f"| {u['name']} | {u['key']} | {u['type']} | {u['issue_count']:,} | {pct}% |\n")

        # Unsearchable fields
        if unsearchable_fields:
            f.write(f"\n## Unsearchable Fields ({len(unsearchable_fields)} — cannot query via JQL)\n\n")
            f.write("These fields could not be queried for usage. They may be deprecated, ")
            f.write("restricted, or use types that don't support JQL search.\n\n")
            f.write("| Field Name | Key | Type |\n")
            f.write("|---|---|---|\n")
            for u in sorted(unsearchable_fields, key=lambda x: x["name"]):
                f.write(f"| {u['name']} | {u['key']} | {u['type']} |\n")

        # Field context/scope analysis
        f.write("\n## Field Scope Analysis\n\n")
        global_fields = sum(1 for v in field_contexts.values() if v.get("is_global"))
        scoped_fields = sum(1 for v in field_contexts.values() if not v.get("is_global"))
        f.write(f"| Scope | Count |\n")
        f.write(f"|---|---|\n")
        f.write(f"| Global (all projects) | {global_fields} |\n")
        f.write(f"| Project-scoped | {scoped_fields} |\n\n")

        # Field Configuration Scheme associations
        f.write("## Field Configuration Schemes\n\n")
        f.write("| Config Name | Fields in Config | ID |\n")
        f.write("|---|---|---|\n")
        for fc_id, fc_data in sorted(fc_field_map.items(), key=lambda x: x[1]["field_count"], reverse=True):
            f.write(f"| {fc_data['name']} | {fc_data['field_count']} | {fc_id} |\n")

        # Align-relevant fields
        f.write(f"\n## Align-Relevant Fields ({len(align_relevant)} found)\n\n")
        f.write("Fields matching Align integration keywords (story points, sprint, epic, team, etc.)\n\n")
        f.write("| Field Name | Key | Type | Matched Keyword | Issues |\n")
        f.write("|---|---|---|---|---|\n")
        for u in sorted(align_relevant, key=lambda x: x["issue_count"], reverse=True):
            f.write(f"| {u['name']} | {u['key']} | {u['type']} | {u['match']} | {u['issue_count']:,} |\n")

        # Duplicate detection
        if duplicates:
            f.write(f"\n## Potential Duplicate Fields ({len(duplicates)} pairs)\n\n")
            f.write("Fields with >85% name similarity — candidates for consolidation.\n\n")
            f.write("| Field 1 | Field 2 | Similarity |\n")
            f.write("|---|---|---|\n")
            for d in sorted(duplicates, key=lambda x: x["similarity"], reverse=True)[:40]:
                f.write(f"| {d['field1_name']} ({d['field1_key']}) | {d['field2_name']} ({d['field2_key']}) | {d['similarity']}% |\n")

        # Recommendations
        f.write("\n## Align Readiness Recommendations\n\n")
        f.write("### Immediate Actions\n")
        f.write(f"1. **Delete {len(unused_fields)} unused fields** — zero data, safe to remove after stakeholder confirmation\n")
        f.write(f"2. **Review {len(low_usage_fields)} low-usage fields** — likely candidates for retirement or consolidation\n")
        f.write(f"3. **Audit {len(unsearchable_fields)} unsearchable fields** — may indicate deprecated or broken configurations\n")
        if duplicates:
            f.write(f"4. **Consolidate {len(duplicates)} potential duplicate pairs** — merge data before Align onboarding\n")
        f.write("\n### Align Integration Prep\n")
        f.write("5. Confirm which existing fields map to Align concepts (Story Points → Align Points, etc.)\n")
        f.write("6. Create missing Align-specific custom fields (see Report 06)\n")
        f.write("7. Standardize field contexts — Align works best with globally-scoped fields\n")
        f.write(f"8. Reduce global field count from {global_fields} to minimize Align sync complexity\n")

    log(f"  → {report_path}")

    # ================================================================
    # Write detailed CSV
    # ================================================================
    csv_path = os.path.join(REPORT_DIR, "custom_field_usage_detail.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Field Name", "Field Key", "Type", "Custom Type",
            "Issue Count", "% of Total", "Searchable",
            "Is Global", "Context Count", "Status"
        ])
        for key, usage in sorted(field_usage.items(), key=lambda x: x[1]["issue_count"], reverse=True):
            ctx = field_contexts.get(key, {})
            pct = round(usage["issue_count"] / total_issues * 100, 2) if total_issues > 0 and usage["issue_count"] > 0 else 0
            if not usage["searchable"]:
                status = "Unsearchable"
            elif usage["issue_count"] == 0:
                status = "Unused"
            elif total_issues > 0 and (usage["issue_count"] / total_issues) < 0.01:
                status = "Low Usage"
            else:
                status = "Active"
            writer.writerow([
                usage["name"], key, usage["type"], usage["custom_type"],
                usage["issue_count"], pct, usage["searchable"],
                ctx.get("is_global", ""), ctx.get("context_count", ""), status
            ])

    log(f"  → {csv_path}")

    # ================================================================
    # Summary
    # ================================================================
    log("")
    log("=" * 60)
    log("  CUSTOM FIELD DEEP AUDIT COMPLETE")
    log("=" * 60)
    log(f"  Total fields:      {len(custom_fields)}")
    log(f"  Active:            {len(used_fields) - len(low_usage_fields)}")
    log(f"  Low usage (<1%):   {len(low_usage_fields)}")
    log(f"  Unused (0 issues): {len(unused_fields)}")
    log(f"  Unsearchable:      {len(unsearchable_fields)}")
    log(f"  Align-relevant:    {len(align_relevant)}")
    log(f"  Duplicate pairs:   {len(duplicates)}")
    log("")


if __name__ == "__main__":
    main()
