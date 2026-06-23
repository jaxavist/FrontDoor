#!/bin/bash
# ============================================================================
# Jira Align Readiness Audit — Phase 1: Configuration Data Collection
# Target: ftdr-sandbox-438.atlassian.net
# Auth: Basic (email + API token via FTDR_CLOUD_PAT)
# Requires: curl, jq
# ============================================================================

set -euo pipefail

SITE="https://ftdr-sandbox-438.atlassian.net"
EMAIL="jax.kane@frontdoor.com"
PAT="${FTDR_CLOUD_PAT:?Set FTDR_CLOUD_PAT before running}"
AUTH_HEADER="Authorization: Basic $(printf '%s:%s' "$EMAIL" "$PAT" | base64)"
OUTPUT_DIR="./audit_data/$(date +%Y%m%d)"

mkdir -p "$OUTPUT_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Generic paginated fetch — handles both offset-based and cursor-based pagination
fetch_paginated() {
    local endpoint="$1"
    local output_file="$2"
    local page_size="${3:-50}"
    local values_key="${4:-values}"

    local start=0
    local all_results="[]"

    while true; do
        local sep="?"
        [[ "$endpoint" == *"?"* ]] && sep="&"

        local url="${SITE}${endpoint}${sep}startAt=${start}&maxResults=${page_size}"
        log "  Fetching: $url"

        local response
        response=$(curl -s -H "$AUTH_HEADER" -H "Content-Type: application/json" "$url")

        local page_results
        page_results=$(echo "$response" | jq -r ".$values_key // []")
        local count
        count=$(echo "$page_results" | jq 'length')

        all_results=$(echo "$all_results $page_results" | jq -s '.[0] + .[1]')

        local total
        total=$(echo "$response" | jq -r '.total // 0')
        start=$((start + page_size))

        if [[ $count -eq 0 ]] || [[ $start -ge $total ]]; then
            break
        fi
    done

    echo "$all_results" | jq '.' > "$output_file"
    local final_count
    final_count=$(jq 'length' "$output_file")
    log "  → Saved $final_count records to $output_file"
}

# Simple array endpoint fetch (no pagination wrapper)
fetch_array() {
    local endpoint="$1"
    local output_file="$2"

    log "  Fetching: ${SITE}${endpoint}"
    curl -s -H "$AUTH_HEADER" -H "Content-Type: application/json" \
        "${SITE}${endpoint}" | jq '.' > "$output_file"

    local count
    count=$(jq 'length' "$output_file")
    log "  → Saved $count records to $output_file"
}

# ============================================================================
# 1. PROJECTS
# ============================================================================
log "=== Collecting Projects ==="
fetch_paginated "/rest/api/3/project/search?expand=lead" \
    "$OUTPUT_DIR/projects.json" 50

# ============================================================================
# 2. WORKFLOWS
# ============================================================================
log "=== Collecting Workflows ==="
fetch_paginated "/rest/api/3/workflow/search?expand=statuses,transitions" \
    "$OUTPUT_DIR/workflows.json" 50

# ============================================================================
# 3. WORKFLOW SCHEMES (with project mappings)
# ============================================================================
log "=== Collecting Workflow Schemes ==="
fetch_paginated "/rest/api/3/workflowscheme" \
    "$OUTPUT_DIR/workflow_schemes.json" 50

# ============================================================================
# 4. STATUSES
# ============================================================================
log "=== Collecting Statuses ==="
fetch_array "/rest/api/3/status" "$OUTPUT_DIR/statuses.json"

# ============================================================================
# 5. ISSUE TYPES
# ============================================================================
log "=== Collecting Issue Types ==="
fetch_array "/rest/api/3/issuetype" "$OUTPUT_DIR/issue_types.json"

# ============================================================================
# 6. ISSUE TYPE SCHEMES (+ mappings)
# ============================================================================
log "=== Collecting Issue Type Schemes ==="
fetch_paginated "/rest/api/3/issuetypescheme" \
    "$OUTPUT_DIR/issue_type_schemes.json" 50

log "=== Collecting Issue Type Scheme Mappings ==="
# For each scheme, get the issue type mappings
jq -r '.[].id' "$OUTPUT_DIR/issue_type_schemes.json" | while read -r scheme_id; do
    fetch_paginated "/rest/api/3/issuetypescheme/mapping?issueTypeSchemeId=${scheme_id}" \
        "$OUTPUT_DIR/its_mapping_${scheme_id}.json" 50
done 2>/dev/null || true

# ============================================================================
# 7. CUSTOM FIELDS
# ============================================================================
log "=== Collecting Fields (System + Custom) ==="
fetch_array "/rest/api/3/field" "$OUTPUT_DIR/fields.json"

# Extract custom fields separately
jq '[.[] | select(.custom == true)]' "$OUTPUT_DIR/fields.json" > "$OUTPUT_DIR/custom_fields.json"
log "  → Custom fields: $(jq 'length' "$OUTPUT_DIR/custom_fields.json")"

# ============================================================================
# 8. SCREENS
# ============================================================================
log "=== Collecting Screens ==="
fetch_paginated "/rest/api/3/screens" "$OUTPUT_DIR/screens.json" 100

# ============================================================================
# 9. SCREEN SCHEMES
# ============================================================================
log "=== Collecting Screen Schemes ==="
fetch_paginated "/rest/api/3/screenscheme" "$OUTPUT_DIR/screen_schemes.json" 50

# ============================================================================
# 10. ISSUE TYPE SCREEN SCHEMES
# ============================================================================
log "=== Collecting Issue Type Screen Schemes ==="
fetch_paginated "/rest/api/3/issuetypescreenscheme" \
    "$OUTPUT_DIR/issue_type_screen_schemes.json" 50

# ============================================================================
# 11. FIELD CONFIGURATIONS
# ============================================================================
log "=== Collecting Field Configurations ==="
fetch_paginated "/rest/api/3/fieldconfiguration" \
    "$OUTPUT_DIR/field_configurations.json" 50

# ============================================================================
# 12. FIELD CONFIGURATION SCHEMES
# ============================================================================
log "=== Collecting Field Configuration Schemes ==="
fetch_paginated "/rest/api/3/fieldconfigurationscheme" \
    "$OUTPUT_DIR/field_config_schemes.json" 50

# ============================================================================
# 13. PERMISSION SCHEMES
# ============================================================================
log "=== Collecting Permission Schemes ==="
curl -s -H "$AUTH_HEADER" -H "Content-Type: application/json" \
    "${SITE}/rest/api/3/permissionscheme" | jq '.permissionSchemes' > "$OUTPUT_DIR/permission_schemes.json"
log "  → Saved $(jq 'length' "$OUTPUT_DIR/permission_schemes.json") permission schemes"

# ============================================================================
# 14. NOTIFICATION SCHEMES
# ============================================================================
log "=== Collecting Notification Schemes ==="
fetch_paginated "/rest/api/3/notificationscheme" \
    "$OUTPUT_DIR/notification_schemes.json" 50

# ============================================================================
# 15. PRIORITIES
# ============================================================================
log "=== Collecting Priorities ==="
fetch_array "/rest/api/3/priority" "$OUTPUT_DIR/priorities.json"

# ============================================================================
# 16. RESOLUTIONS
# ============================================================================
log "=== Collecting Resolutions ==="
fetch_array "/rest/api/3/resolution" "$OUTPUT_DIR/resolutions.json"

# ============================================================================
# 17. PROJECT-TO-SCHEME MAPPINGS
# ============================================================================
log "=== Collecting Workflow Scheme → Project Mappings ==="
jq -r '.[].id' "$OUTPUT_DIR/workflow_schemes.json" | while read -r ws_id; do
    curl -s -H "$AUTH_HEADER" \
        "${SITE}/rest/api/3/workflowscheme/${ws_id}" | \
        jq "{id: .id, name: .name, defaultWorkflow: .defaultWorkflow, issueTypeMappings: .issueTypeMappings}" \
        >> "$OUTPUT_DIR/workflow_scheme_details_tmp.json"
done
# Consolidate
jq -s '.' "$OUTPUT_DIR/workflow_scheme_details_tmp.json" > "$OUTPUT_DIR/workflow_scheme_details.json" 2>/dev/null || echo "[]" > "$OUTPUT_DIR/workflow_scheme_details.json"
rm -f "$OUTPUT_DIR/workflow_scheme_details_tmp.json"

# ============================================================================
# 18. ISSUE TYPE SCHEME → PROJECT MAPPING
# ============================================================================
log "=== Collecting Issue Type Scheme → Project Mappings ==="
fetch_paginated "/rest/api/3/issuetypescheme/project" \
    "$OUTPUT_DIR/its_project_mapping.json" 50

# ============================================================================
# 19. BOARDS (for sprint/Align team mapping)
# ============================================================================
log "=== Collecting Boards ==="
fetch_paginated "/rest/agile/1.0/board" "$OUTPUT_DIR/boards.json" 50

# ============================================================================
# SUMMARY
# ============================================================================
log ""
log "============================================"
log "  COLLECTION COMPLETE"
log "  Output directory: $OUTPUT_DIR"
log "============================================"
log ""
log "File manifest:"
ls -la "$OUTPUT_DIR"/*.json | awk '{print $NF, $5}' | while read -r f s; do
    echo "  $(basename "$f"): $(numfmt --to=iec "$s" 2>/dev/null || echo "${s}B")"
done
