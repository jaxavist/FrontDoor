#!/bin/bash
# ============================================================================
# Jira Align Readiness Audit — Phase 3: Custom Field Usage Analysis
# Checks which custom fields are actually populated on issues
# WARNING: This script makes many API calls and may take 30-60 minutes
# ============================================================================

set -euo pipefail

SITE="https://ftdr-sandbox-438.atlassian.net"
EMAIL="jax.kane@frontdoor.com"
PAT="${FTDR_CLOUD_PAT:?Set FTDR_CLOUD_PAT before running}"
AUTH_HEADER="Authorization: Basic $(printf '%s:%s' "$EMAIL" "$PAT" | base64)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -n "${1:-}" ]]; then
    DATA_DIR="$1"
else
    DATA_DIR=$(ls -td "${PROJECT_ROOT}/data/"*/ 2>/dev/null | head -1)
    DATA_DIR="${DATA_DIR%/}"
fi
[[ -d "$DATA_DIR" ]] || { echo "No data directory found. Run 01_collect_config_data.sh first."; exit 1; }

REPORT_DIR="${PROJECT_ROOT}/reports"
mkdir -p "$REPORT_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ============================================================================
# Custom Field Usage: Sample issues to see which fields are populated
# ============================================================================
log "=== Custom Field Usage Analysis ==="
log "This checks a sample of issues per project to identify unused fields."
log ""

SAMPLE_SIZE=20
USAGE_FILE="$DATA_DIR/field_usage.json"
echo "{}" > "$USAGE_FILE"

# Get active project keys
active_projects=$(jq -r '.[].key' "$DATA_DIR/projects.json")
total_projects=$(echo "$active_projects" | wc -l | tr -d ' ')
current=0

for project_key in $active_projects; do
    current=$((current + 1))
    log "  [$current/$total_projects] Sampling $project_key..."

    # Get a sample of recent issues with all fields
    response=$(curl -s -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        "${SITE}/rest/api/3/search?jql=project=${project_key}+ORDER+BY+updated+DESC&maxResults=${SAMPLE_SIZE}&fields=*all" 2>/dev/null || echo '{"issues":[]}')

    issue_count=$(echo "$response" | jq '.issues | length')

    if [[ $issue_count -gt 0 ]]; then
        # For each issue, record which custom fields have non-null values
        echo "$response" | jq -r '
            .issues[].fields | to_entries[] |
            select(.key | startswith("customfield_")) |
            select(.value != null and .value != "" and .value != []) |
            .key
        ' | sort | uniq -c | sort -rn | while read -r count field; do
            # Accumulate usage counts
            existing=$(jq -r --arg f "$field" '.[$f] // 0' "$USAGE_FILE")
            new_count=$((existing + count))
            tmp=$(mktemp)
            jq --arg f "$field" --argjson c "$new_count" '.[$f] = $c' "$USAGE_FILE" > "$tmp"
            mv "$tmp" "$USAGE_FILE"
        done
    fi

    # Rate limiting - be nice to the API
    sleep 0.5
done

# ============================================================================
# Generate Field Usage Report
# ============================================================================
log "=== Generating Field Usage Report ==="
{
    echo "# Custom Field Usage Report"
    echo ""
    echo "## Methodology"
    echo ""
    echo "Sampled up to $SAMPLE_SIZE recent issues from each of $total_projects projects"
    echo "to determine which custom fields are actively populated."
    echo ""

    total_cf=$(jq 'length' "$DATA_DIR/custom_fields.json")
    used_cf=$(jq 'keys | length' "$USAGE_FILE")
    unused_cf=$((total_cf - used_cf))

    echo "## Summary"
    echo ""
    echo "- Total custom fields defined: $total_cf"
    echo "- Fields with data in sample: $used_cf"
    echo "- Fields with NO data in sample: $unused_cf"
    echo "- **Potential cleanup candidates: $unused_cf fields**"
    echo ""

    echo "## Most Used Custom Fields (by issue count in sample)"
    echo ""
    echo "| Rank | Field Key | Field Name | Issues with Data |"
    echo "|---|---|---|---|"

    rank=0
    jq -r 'to_entries | sort_by(-.value) | .[] | "\(.key)\t\(.value)"' "$USAGE_FILE" | head -50 | while read -r line; do
        rank=$((rank + 1))
        field_key=$(echo "$line" | cut -f1)
        usage=$(echo "$line" | cut -f2)
        field_name=$(jq -r --arg k "$field_key" '.[] | select(.key == $k) | .name // "Unknown"' "$DATA_DIR/fields.json")
        echo "| $rank | $field_key | $field_name | $usage |"
    done

    echo ""
    echo "## Unused Custom Fields (candidates for removal)"
    echo ""
    echo "| Field Key | Field Name | Type |"
    echo "|---|---|---|"

    jq -r '.[] | .key' "$DATA_DIR/custom_fields.json" | while read -r cf_key; do
        in_use=$(jq --arg k "$cf_key" 'has($k)' "$USAGE_FILE")
        if [[ "$in_use" == "false" ]]; then
            jq -r --arg k "$cf_key" '.[] | select(.key == $k) | "| \(.key) | \(.name) | \(.schema.type // "unknown") |"' "$DATA_DIR/custom_fields.json"
        fi
    done

} > "$REPORT_DIR/09_field_usage.md"
log "  → $REPORT_DIR/09_field_usage.md"

log ""
log "============================================"
log "  FIELD USAGE ANALYSIS COMPLETE"
log "============================================"
