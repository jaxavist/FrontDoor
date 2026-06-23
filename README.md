# FTDR Jira Align Readiness Audit

Audit scripts for assessing Jira Cloud configuration at `ftdr-sandbox-438.atlassian.net`
in preparation for Jira Align onboarding.

## Prerequisites

- `curl` and `jq` installed (`brew install jq` if needed)
- `FTDR_CLOUD_PAT` environment variable set with your API token

## Usage

```bash
export FTDR_CLOUD_PAT="your-api-token"

# Step 1: Collect all configuration data (~5-10 min)
./scripts/01_collect_config_data.sh

# Step 2: Analyze and generate reports (~1 min)
./scripts/02_analyze_and_report.sh

# Step 3 (optional): Deep custom field usage analysis (~30-60 min)
./scripts/03_field_usage_analysis.sh
```

All scripts auto-detect paths relative to the project root. No arguments needed
(though you can pass an explicit data directory path if you have multiple runs).

## Project Structure

```
ftdr-jira-align-audit/
├── scripts/              # Audit scripts (committed)
├── reports/              # Generated markdown reports + CSVs (committed)
├── data/                 # Raw API JSON (gitignored — large)
└── docs/                 # Engagement notes and specs
```

## Reports

| File | Contents |
|---|---|
| `00_executive_summary.md` | Readiness scorecard, key metrics, phased roadmap |
| `01_config_inventory.md` | Object counts vs Align target ranges |
| `02_project_types.md` | Classic vs team-managed breakdown |
| `03_workflow_analysis.md` | Unused workflows, age distribution |
| `04_status_analysis.md` | Duplicate statuses, category mismatches |
| `05_issue_type_analysis.md` | Sprawl metrics, Align hierarchy check |
| `06_custom_field_analysis.md` | Field types, Align field gap check |
| `07_scheme_consolidation.md` | Scheme reduction targets + effort |
| `08_priority_resolution.md` | Priority/resolution standardization |
| `09_field_usage.md` | (Phase 3) Usage-based field cleanup list |
| `*.csv` | Spreadsheet-ready exports for stakeholder analysis |
