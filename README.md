# Jira Align Readiness Audit — Script Suite

## Prerequisites
- `curl` and `jq` installed (`brew install jq` if needed)
- `FTDR_CLOUD_PAT` environment variable set with your API token
- Run from a directory where you want the output

## Quick Start

```bash
export FTDR_CLOUD_PAT="your-api-token"

# Step 1: Collect all configuration data (~5-10 min)
chmod +x 01_collect_config_data.sh
./01_collect_config_data.sh

# Step 2: Analyze and generate reports (~1 min)
chmod +x 02_analyze_and_report.sh
./02_analyze_and_report.sh ./audit_data/YYYYMMDD

# Step 3 (optional): Deep custom field usage analysis (~30-60 min)
chmod +x 03_field_usage_analysis.sh
./03_field_usage_analysis.sh ./audit_data/YYYYMMDD
```

## Output Structure

```
audit_data/YYYYMMDD/
├── *.json                          # Raw API data
├── reports/
│   ├── 00_executive_summary.md     # Readiness scorecard + roadmap
│   ├── 01_config_inventory.md      # Object counts vs targets
│   ├── 02_project_types.md         # Classic vs team-managed breakdown
│   ├── 03_workflow_analysis.md     # Consolidation opportunities
│   ├── 04_status_analysis.md       # Duplication + category mapping
│   ├── 05_issue_type_analysis.md   # Sprawl + Align hierarchy check
│   ├── 06_custom_field_analysis.md # Field audit + Align field gaps
│   ├── 07_scheme_consolidation.md  # Scheme sharing analysis
│   ├── 08_priority_resolution.md   # Priority/resolution cleanup
│   ├── 09_field_usage.md           # (Phase 3) Usage-based cleanup list
│   ├── projects.csv                # For spreadsheet analysis
│   ├── workflows.csv
│   ├── custom_fields.csv
│   ├── statuses.csv
│   └── issue_types.csv
```

## Reports for the Project Lead

The executive summary (00) gives the roadmap metrics. The CSVs let
stakeholders filter and sort in Excel/Sheets for their own analysis.
