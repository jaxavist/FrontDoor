"""
Jira Align Readiness Audit — Label Audit
Site: ftdr-sandbox-438.atlassian.net

Produces detailed metrics on:
  - All labels in the instance
  - Usage counts per label (via issue sampling)
  - Labels by project spread
  - Unused / low-usage labels
  - Label naming patterns and duplicates (case variants)

Requires: FTDR_CLOUD_PAT environment variable
Uses project data already collected in data/ directory
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


def api_post(endpoint, body):
    url = f"{SITE}{endpoint}"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        body_resp = e.read().decode() if e.readable() else ""
        try:
            return e.code, json.loads(body_resp)
        except Exception:
            return e.code, {"error": e.reason, "body": body_resp[:200]}
    except URLError as e:
        return 0, {"error": str(e.reason)}


def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return []


def main():
    log("=" * 60)
    log("  Label Audit")
    log(f"  Data source: {DATA_DIR}")
    log(f"  Reports: {REPORT_DIR}")
    log("=" * 60)

    projects = load_json("projects.json")
    log(f"  {len(projects)} projects loaded")

    # ================================================================
    # 1. Fetch all labels from the instance
    # ================================================================
    log("")
    log("=== Phase 1: Collecting All Labels ===")

    all_labels = []
    start = 0
    page_size = 1000
    while True:
        # Try the label endpoint with explicit accept header
        status, data = api_get(f"/rest/api/3/label?startAt={start}&maxResults={page_size}")
        if status == 200:
            page = data.get("values", [])
            all_labels.extend(page)
            total = data.get("total", 0)
            start += page_size
            log(f"  Fetched {len(all_labels)} / {total} labels...")
            if not page or start >= total:
                break
        else:
            log(f"  Label list endpoint returned {status} — will discover labels from issue sampling instead")
            break

    log(f"  Labels from API: {len(all_labels)}")

    # ================================================================
    # 2. Sample issues to get label usage by project
    # ================================================================
    log("")
    log("=== Phase 2: Label Usage via Issue Sampling ===")
    log(f"Sampling issues from {len(projects)} projects...")

    SAMPLE_SIZE = 50

    # label_name → {count, projects, issues_with_label}
    label_usage = defaultdict(lambda: {
        "count": 0,
        "projects": defaultdict(int),
        "project_names": {},
    })

    total_issues_sampled = 0
    total_issues_with_labels = 0
    total_issues_in_instance = 0
    project_label_summary = {}  # project_key → {total_sampled, with_labels, unique_labels}

    for pi, project in enumerate(projects, 1):
        pkey = project["key"]
        pname = project["name"]
        if pi % 10 == 0 or pi == 1:
            log(f"  [{pi}/{len(projects)}] Sampling {pkey} ({pname})...")

        status, data = api_post("/rest/api/3/search/jql", {
            "jql": f"project = {pkey} ORDER BY updated DESC",
            "maxResults": SAMPLE_SIZE,
            "fields": ["*all"],
        })

        if status != 200:
            from urllib.parse import quote
            jql_encoded = quote(f"project = {pkey} ORDER BY updated DESC")
            status, data = api_get(
                f"/rest/api/3/search/jql?jql={jql_encoded}&maxResults={SAMPLE_SIZE}&fields=*all"
            )

        if status != 200:
            continue

        project_total = data.get("total", 0) or len(data.get("issues", []))
        total_issues_in_instance += project_total
        issues = data.get("issues", [])
        total_issues_sampled += len(issues)

        project_labels_seen = set()
        project_issues_with_labels = 0

        for issue in issues:
            labels = issue.get("fields", {}).get("labels", [])
            if labels:
                total_issues_with_labels += 1
                project_issues_with_labels += 1
                for label in labels:
                    label_usage[label]["count"] += 1
                    label_usage[label]["projects"][pkey] += 1
                    label_usage[label]["project_names"][pkey] = pname
                    project_labels_seen.add(label)

        project_label_summary[pkey] = {
            "name": pname,
            "sampled": len(issues),
            "with_labels": project_issues_with_labels,
            "unique_labels": len(project_labels_seen),
            "project_total": project_total,
        }

        time.sleep(0.3)

    log(f"  Sampled {total_issues_sampled:,} issues across {len(projects)} projects")
    log(f"  Issues with labels: {total_issues_with_labels:,} ({round(total_issues_with_labels/max(total_issues_sampled,1)*100,1)}%)")
    log(f"  Unique labels found in sample: {len(label_usage)}")

    # ================================================================
    # 3. Analysis
    # ================================================================
    log("")
    log("=== Phase 3: Analysis ===")

    # Labels from the API that weren't found in any sampled issues
    labels_from_api = set(all_labels)
    labels_from_sample = set(label_usage.keys())
    unused_labels = labels_from_api - labels_from_sample
    sample_only_labels = labels_from_sample - labels_from_api  # found in issues but not in label list (rare)

    # Case-variant detection
    case_groups = defaultdict(list)
    all_known_labels = labels_from_api | labels_from_sample
    for label in all_known_labels:
        case_groups[label.lower()].append(label)
    case_duplicates = {k: v for k, v in case_groups.items() if len(v) > 1}

    # Single-project labels
    single_project = {k: v for k, v in label_usage.items() if len(v["projects"]) == 1}

    # High-spread labels (used across many projects)
    multi_project = sorted(
        [(k, v) for k, v in label_usage.items() if len(v["projects"]) > 1],
        key=lambda x: len(x[1]["projects"]), reverse=True
    )

    log(f"  Labels from API: {len(labels_from_api)}")
    log(f"  Labels from sample: {len(labels_from_sample)}")
    log(f"  Unused (in API, not in sample): {len(unused_labels)}")
    log(f"  Case-variant groups: {len(case_duplicates)}")
    log(f"  Single-project labels: {len(single_project)}")

    # ================================================================
    # 4. Generate Report
    # ================================================================
    log("")
    log("=== Generating Report ===")

    report_path = os.path.join(REPORT_DIR, "11_label_audit.md")
    with open(report_path, "w") as f:
        f.write("# Label Audit\n")
        f.write(f"# Site: ftdr-sandbox-438.atlassian.net\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|---|---|\n")
        f.write(f"| Labels registered in instance | {len(all_labels)} |\n")
        f.write(f"| Labels found with data (in sample) | {len(label_usage)} |\n")
        f.write(f"| Unused labels (no data in sample) | {len(unused_labels)} |\n")
        f.write(f"| Issues sampled | {total_issues_sampled:,} |\n")
        f.write(f"| Issues with at least one label | {total_issues_with_labels:,} ({round(total_issues_with_labels/max(total_issues_sampled,1)*100,1)}%) |\n")
        f.write(f"| Single-project labels | {len(single_project)} |\n")
        f.write(f"| Case-variant duplicates | {len(case_duplicates)} groups |\n")
        f.write(f"| **Cleanup candidates** | **{len(unused_labels) + len(single_project) + len(case_duplicates)}** |\n\n")
        f.write(f"_Based on sampling {SAMPLE_SIZE} recent issues per project across {len(projects)} projects._\n\n")

        # Top labels by usage
        f.write("## Top 50 Most Used Labels\n\n")
        f.write("| Rank | Label | Hits (sampled) | Projects Using |\n")
        f.write("|---|---|---|---|\n")
        sorted_labels = sorted(label_usage.items(), key=lambda x: x[1]["count"], reverse=True)
        for rank, (label, data) in enumerate(sorted_labels[:50], 1):
            f.write(f"| {rank} | {label} | {data['count']:,} | {len(data['projects'])} |\n")

        # Complete label usage list
        f.write(f"\n## Complete Label Usage ({len(label_usage)} labels with data)\n\n")
        f.write("| # | Label | Hits | Projects | Project List | Status |\n")
        f.write("|---|---|---|---|---|---|\n")
        for rank, (label, data) in enumerate(sorted_labels, 1):
            proj_list = ", ".join(sorted(data["projects"].keys()))
            if len(data["projects"]) == 1:
                status = "Single-Project"
            elif data["count"] <= 2:
                status = "Low"
            else:
                status = "Active"
            # Check if it's a case variant
            if label.lower() in case_duplicates:
                status += " / Case-Variant"
            f.write(f"| {rank} | {label} | {data['count']:,} | {len(data['projects'])} | {proj_list} | {status} |\n")

        # Labels by project spread
        f.write("\n## Labels by Project Spread (cross-project labels)\n\n")
        f.write("Labels used across many projects may be good candidates for Align categories.\n\n")
        f.write("| Label | Projects Using | Total Hits | Top Projects |\n")
        f.write("|---|---|---|---|\n")
        for label, data in multi_project[:40]:
            top_projs = sorted(data["projects"].items(), key=lambda x: x[1], reverse=True)[:5]
            top_str = ", ".join(f"{k}({v})" for k, v in top_projs)
            f.write(f"| {label} | {len(data['projects'])} | {data['count']:,} | {top_str} |\n")

        # Single-project labels
        f.write(f"\n## Single-Project Labels ({len(single_project)} labels)\n\n")
        f.write("Labels used in only one project — may indicate local conventions ")
        f.write("that should be standardized or removed.\n\n")
        f.write("| Label | Project | Hits |\n")
        f.write("|---|---|---|\n")
        for label, data in sorted(single_project.items(), key=lambda x: x[0].lower()):
            proj = list(data["projects"].keys())[0]
            proj_name = data["project_names"].get(proj, proj)
            f.write(f"| {label} | {proj} ({proj_name}) | {data['count']} |\n")

        # Case-variant duplicates
        if case_duplicates:
            f.write(f"\n## Case-Variant Duplicates ({len(case_duplicates)} groups)\n\n")
            f.write("Labels that differ only by case — should be consolidated.\n\n")
            f.write("| Normalized | Variants | Usage |\n")
            f.write("|---|---|---|\n")
            for norm, variants in sorted(case_duplicates.items()):
                variant_info = []
                for v in variants:
                    count = label_usage[v]["count"] if v in label_usage else 0
                    variant_info.append(f"{v} ({count})")
                f.write(f"| {norm} | {', '.join(variant_info)} | {sum(label_usage.get(v, {}).get('count', 0) for v in variants)} |\n")

        # Unused labels
        if unused_labels:
            f.write(f"\n## Unused Labels ({len(unused_labels)} — deletion candidates)\n\n")
            f.write("Labels registered in the instance but not found on any sampled issues.\n\n")
            f.write("| Label |\n")
            f.write("|---|\n")
            for label in sorted(unused_labels, key=str.lower):
                f.write(f"| {label} |\n")

        # Project label adoption
        f.write("\n## Label Adoption by Project\n\n")
        f.write("| Project | Key | Sampled | With Labels | % Labeled | Unique Labels |\n")
        f.write("|---|---|---|---|---|---|\n")
        for pkey, pdata in sorted(project_label_summary.items(),
                                   key=lambda x: x[1]["with_labels"], reverse=True):
            pct = round(pdata["with_labels"] / max(pdata["sampled"], 1) * 100, 1)
            f.write(f"| {pdata['name']} | {pkey} | {pdata['sampled']} | {pdata['with_labels']} | {pct}% | {pdata['unique_labels']} |\n")

        # Recommendations
        f.write("\n## Align Readiness Recommendations\n\n")
        f.write("### Cleanup\n")
        f.write(f"1. **Remove {len(unused_labels)} unused labels** — no data found in sample\n")
        if case_duplicates:
            f.write(f"2. **Merge {len(case_duplicates)} case-variant groups** — standardize casing\n")
        f.write(f"3. **Review {len(single_project)} single-project labels** — standardize or remove\n")
        f.write("\n### Standardization for Align\n")
        f.write("4. Define a controlled label taxonomy before Align onboarding\n")
        f.write("5. Cross-project labels with high adoption are candidates for Align categories/themes\n")
        f.write("6. Consider replacing label-based workflows with proper custom fields where appropriate\n")

    log(f"  → {report_path}")

    # ================================================================
    # CSV Export
    # ================================================================
    csv_path = os.path.join(REPORT_DIR, "label_usage_detail.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Label", "Hits (Sampled)", "Projects Using", "Project List", "Status"])
        for label, data in sorted_labels:
            proj_list = ", ".join(sorted(data["projects"].keys()))
            if len(data["projects"]) == 1:
                status = "Single-Project"
            elif data["count"] <= 2:
                status = "Low"
            else:
                status = "Active"
            writer.writerow([label, data["count"], len(data["projects"]), proj_list, status])
        for label in sorted(unused_labels, key=str.lower):
            writer.writerow([label, 0, 0, "", "Unused"])

    log(f"  → {csv_path}")

    # ================================================================
    # Save raw label data for reuse
    # ================================================================
    label_data_path = os.path.join(DATA_DIR, "labels.json")
    with open(label_data_path, "w") as f:
        json.dump(all_labels, f, indent=2)
    log(f"  → {label_data_path}")

    # ================================================================
    log("")
    log("=" * 60)
    log("  LABEL AUDIT COMPLETE")
    log("=" * 60)
    log(f"  Labels in instance:    {len(all_labels)}")
    log(f"  Labels with data:      {len(label_usage)}")
    log(f"  Unused labels:         {len(unused_labels)}")
    log(f"  Single-project labels: {len(single_project)}")
    log(f"  Case-variant groups:   {len(case_duplicates)}")
    log(f"  Label adoption rate:   {round(total_issues_with_labels/max(total_issues_sampled,1)*100,1)}%")
    log("")


if __name__ == "__main__":
    main()
