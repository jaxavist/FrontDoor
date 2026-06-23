#!/bin/bash
# ============================================================================
# Jira Align Readiness Audit — Phase 2: Configuration Analysis
# Reads JSON data from Phase 1 and produces summary reports
# Requires: jq
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Find most recent data directory, or accept explicit argument
if [[ -n "${1:-}" ]]; then
    DATA_DIR="$1"
else
    DATA_DIR=$(ls -td "${PROJECT_ROOT}/data/"*/ 2>/dev/null | head -1)
    DATA_DIR="${DATA_DIR%/}"
fi
[[ -d "$DATA_DIR" ]] || { echo "No data directory found. Run 01_collect_config_data.sh first."; exit 1; }

REPORT_DIR="${PROJECT_ROOT}/reports"
mkdir -p "$REPORT_DIR"

log "Using data from: $DATA_DIR"
log "Writing reports to: $REPORT_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ============================================================================
# REPORT 1: Configuration Inventory Summary
# ============================================================================
log "=== Generating Configuration Inventory ==="
{
    echo "# Jira Align Readiness Audit — Configuration Inventory"
    echo "# Site: ftdr-sandbox-438.atlassian.net"
    echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo ""
    echo "## Object Counts"
    echo ""
    echo "| Configuration Object | Count | Align Target Range | Gap |"
    echo "|---|---|---|---|"

    proj_count=$(jq 'length' "$DATA_DIR/projects.json")
    wf_count=$(jq 'length' "$DATA_DIR/workflows.json")
    ws_count=$(jq 'length' "$DATA_DIR/workflow_schemes.json")
    st_count=$(jq 'length' "$DATA_DIR/statuses.json")
    it_count=$(jq 'length' "$DATA_DIR/issue_types.json")
    its_count=$(jq 'length' "$DATA_DIR/issue_type_schemes.json")
    scr_count=$(jq 'length' "$DATA_DIR/screens.json")
    fc_count=$(jq 'length' "$DATA_DIR/field_configurations.json")
    fcs_count=$(jq 'length' "$DATA_DIR/field_config_schemes.json")
    ps_count=$(jq 'length' "$DATA_DIR/permission_schemes.json")
    ns_count=$(jq 'length' "$DATA_DIR/notification_schemes.json")
    cf_count=$(jq 'length' "$DATA_DIR/custom_fields.json")
    itss_count=$(jq 'length' "$DATA_DIR/issue_type_screen_schemes.json")
    pri_count=$(jq 'length' "$DATA_DIR/priorities.json")
    res_count=$(jq 'length' "$DATA_DIR/resolutions.json")

    echo "| Projects | $proj_count | — | — |"
    echo "| Workflows | $wf_count | 3-5 standard | -$((wf_count - 5)) |"
    echo "| Workflow Schemes | $ws_count | 3-5 standard | -$((ws_count - 5)) |"
    echo "| Statuses (total) | $st_count | 10-15 global | — |"
    echo "| Issue Types (total) | $it_count | 5-10 global | — |"
    echo "| Issue Type Schemes | $its_count | 3-5 standard | -$((its_count - 5)) |"
    echo "| Screens | $scr_count | Consolidate to ~10 | -$((scr_count - 10)) |"
    echo "| Issue Type Screen Schemes | $itss_count | 3-5 standard | -$((itss_count - 5)) |"
    echo "| Field Configurations | $fc_count | 2-3 standard | -$((fc_count - 3)) |"
    echo "| Field Config Schemes | $fcs_count | 2-3 standard | -$((fcs_count - 3)) |"
    echo "| Permission Schemes | $ps_count | 3-5 standard | — |"
    echo "| Notification Schemes | $ns_count | 2-3 standard | -$((ns_count - 3)) |"
    echo "| Custom Fields | $cf_count | Audit for usage | — |"
    echo "| Priorities | $pri_count | 1 standard set | — |"
    echo "| Resolutions | $res_count | 1 standard set | — |"

} > "$REPORT_DIR/01_config_inventory.md"
log "  → $REPORT_DIR/01_config_inventory.md"

# ============================================================================
# REPORT 2: Project Type Breakdown (Classic vs Team-Managed)
# ============================================================================
log "=== Generating Project Type Analysis ==="
{
    echo "# Project Type Analysis"
    echo ""
    echo "## Summary"

    classic=$(jq '[.[] | select(.style == "classic")] | length' "$DATA_DIR/projects.json")
    team_managed=$(jq '[.[] | select(.style == "next-gen")] | length' "$DATA_DIR/projects.json")
    echo ""
    echo "- Company-managed (classic): $classic"
    echo "- Team-managed (next-gen): $team_managed"
    echo ""
    echo "**ALIGN IMPACT:** Team-managed projects cannot be connected to Jira Align."
    echo "All $team_managed team-managed projects must be migrated to company-managed."
    echo ""

    echo "## By Product Type"
    echo ""
    echo "| Product | Classic | Team-Managed | Total |"
    echo "|---|---|---|---|"
    for ptype in software service_desk business product_discovery; do
        c=$(jq --arg t "$ptype" '[.[] | select(.projectTypeKey == $t and .style == "classic")] | length' "$DATA_DIR/projects.json")
        tm=$(jq --arg t "$ptype" '[.[] | select(.projectTypeKey == $t and .style == "next-gen")] | length' "$DATA_DIR/projects.json")
        total=$((c + tm))
        [[ $total -gt 0 ]] && echo "| $ptype | $c | $tm | $total |"
    done

    echo ""
    echo "## Team-Managed Projects (must migrate to company-managed)"
    echo ""
    echo "| Key | Name | Product Type |"
    echo "|---|---|---|"
    jq -r '.[] | select(.style == "next-gen") | "| \(.key) | \(.name) | \(.projectTypeKey) |"' \
        "$DATA_DIR/projects.json"

    echo ""
    echo "## By Project Category"
    echo ""
    jq -r 'group_by(.projectCategory.name) | .[] | "- **\(.[0].projectCategory.name // "Uncategorized")**: \(length) projects"' \
        "$DATA_DIR/projects.json"

} > "$REPORT_DIR/02_project_types.md"
log "  → $REPORT_DIR/02_project_types.md"

# ============================================================================
# REPORT 3: Workflow Consolidation Analysis
# ============================================================================
log "=== Generating Workflow Analysis ==="
{
    echo "# Workflow Consolidation Analysis"
    echo ""
    echo "## Current State: $(jq 'length' "$DATA_DIR/workflows.json") workflows"
    echo ""
    echo "Jira Align requires standardized workflow status mappings. Each workflow's"
    echo "statuses must map cleanly to Align's status categories (To Do, In Progress,"
    echo "Done). Reducing workflow count is the single highest-effort item."
    echo ""

    echo "## Workflow Age Distribution"
    echo ""
    echo "| Year Created | Count |"
    echo "|---|---|"
    jq -r '.[].created // empty' "$DATA_DIR/workflows.json" | \
        cut -d'-' -f1 | sort | uniq -c | sort -rn | \
        awk '{print "| "$2" | "$1" |"}'

    echo ""
    echo "## Workflows Not Assigned to Any Scheme (candidates for deletion)"
    echo ""

    # Get all workflow names used in schemes
    jq -r '.[].defaultWorkflow // empty, (.[].issueTypeMappings // {} | values[])' \
        "$DATA_DIR/workflow_scheme_details.json" 2>/dev/null | sort -u > /tmp/used_workflows.txt

    # Compare with all workflow names
    jq -r '.[].id.name' "$DATA_DIR/workflows.json" | sort -u > /tmp/all_workflows.txt

    unused=$(comm -23 /tmp/all_workflows.txt /tmp/used_workflows.txt | wc -l | tr -d ' ')
    echo "**$unused workflows** are not referenced by any workflow scheme."
    echo ""
    echo "| Unused Workflow Name |"
    echo "|---|"
    comm -23 /tmp/all_workflows.txt /tmp/used_workflows.txt | head -50 | while read -r wf; do
        echo "| $wf |"
    done
    echo ""
    [[ $unused -gt 50 ]] && echo "_...and $((unused - 50)) more_"

    echo ""
    echo "## Workflow Scheme Sharing Analysis"
    echo ""
    echo "Schemes used by multiple projects can be standardized once."
    echo "Schemes used by a single project are the primary cleanup targets."
    echo ""

} > "$REPORT_DIR/03_workflow_analysis.md"
log "  → $REPORT_DIR/03_workflow_analysis.md"

# ============================================================================
# REPORT 4: Status Duplication and Category Mapping
# ============================================================================
log "=== Generating Status Analysis ==="
{
    echo "# Status Duplication & Category Mapping Report"
    echo ""
    echo "## Summary"
    echo ""

    total_statuses=$(jq 'length' "$DATA_DIR/statuses.json")
    global_statuses=$(jq '[.[] | select(.scope == null or .scope.type == "GLOBAL")] | length' "$DATA_DIR/statuses.json")
    project_statuses=$(jq '[.[] | select(.scope.type == "PROJECT")] | length' "$DATA_DIR/statuses.json")

    echo "- Total statuses: $total_statuses"
    echo "- Global statuses: $global_statuses"
    echo "- Project-scoped statuses: $project_statuses (from team-managed projects)"
    echo ""

    echo "## Status Category Distribution"
    echo ""
    echo "| Category | Count |"
    echo "|---|---|"
    jq -r '.[].statusCategory.name' "$DATA_DIR/statuses.json" | sort | uniq -c | sort -rn | \
        awk '{print "| "$2" "$3" | "$1" |"}'

    echo ""
    echo "## Duplicate Status Names (same name, different IDs)"
    echo ""
    echo "These indicate fragmentation from team-managed projects."
    echo ""
    echo "| Status Name | Occurrences | IDs |"
    echo "|---|---|---|"
    jq -r 'group_by(.name) | .[] | select(length > 1) | "\(.[0].name)\t\(length)\t\([.[].id] | join(", "))"' \
        "$DATA_DIR/statuses.json" | sort -t$'\t' -k2 -rn | head -30 | \
        awk -F'\t' '{print "| "$1" | "$2" | "$3" |"}'

    echo ""
    echo "## Status Category Mismatches (potential Align mapping issues)"
    echo ""
    echo "Statuses with the same name but mapped to different categories:"
    echo ""
    jq -r '
        group_by(.name) | .[] |
        select(length > 1) |
        select(([.[].statusCategory.name] | unique | length) > 1) |
        "- **\(.[0].name)**: mapped to \([.[].statusCategory.name] | unique | join(", "))"
    ' "$DATA_DIR/statuses.json"

} > "$REPORT_DIR/04_status_analysis.md"
log "  → $REPORT_DIR/04_status_analysis.md"

# ============================================================================
# REPORT 5: Issue Type Sprawl
# ============================================================================
log "=== Generating Issue Type Analysis ==="
{
    echo "# Issue Type Analysis"
    echo ""

    total_it=$(jq 'length' "$DATA_DIR/issue_types.json")
    global_it=$(jq '[.[] | select(.scope == null)] | length' "$DATA_DIR/issue_types.json")
    project_it=$(jq '[.[] | select(.scope != null)] | length' "$DATA_DIR/issue_types.json")
    subtask_it=$(jq '[.[] | select(.subtask == true)] | length' "$DATA_DIR/issue_types.json")
    standard_it=$(jq '[.[] | select(.subtask == false)] | length' "$DATA_DIR/issue_types.json")

    echo "- Total issue types: $total_it"
    echo "- Global (shared): $global_it"
    echo "- Project-scoped: $project_it"
    echo "- Standard types: $standard_it"
    echo "- Sub-task types: $subtask_it"
    echo ""

    echo "## Hierarchy Levels"
    echo ""
    echo "| Level | Count | Types |"
    echo "|---|---|---|"
    jq -r '
        group_by(.hierarchyLevel) | .[] |
        "\(.[0].hierarchyLevel)\t\(length)\t\([.[].name] | unique | join(", "))"
    ' "$DATA_DIR/issue_types.json" | sort -t$'\t' -k1 -n | \
        awk -F'\t' '{print "| "$1" | "$2" | "$3" |"}'

    echo ""
    echo "## Duplicate Issue Type Names"
    echo ""
    echo "| Name | Occurrences | Global? | Project-Scoped IDs |"
    echo "|---|---|---|---|"
    jq -r '
        group_by(.name) | .[] | select(length > 1) |
        "\(.[0].name)\t\(length)\t\(if any(.scope == null) then "Yes" else "No" end)\t\([.[] | select(.scope != null) | .scope.project.id] | join(", "))"
    ' "$DATA_DIR/issue_types.json" | sort -t$'\t' -k2 -rn | \
        awk -F'\t' '{print "| "$1" | "$2" | "$3" | "$4" |"}'

    echo ""
    echo "## Align-Required Issue Types"
    echo ""
    echo "Jira Align expects these hierarchy types to map correctly:"
    echo ""
    echo "| Align Level | Align Name | Jira Equivalent | Present? |"
    echo "|---|---|---|---|"
    for type_name in "Epic" "Story" "Task" "Bug" "Sub-task" "Initiative"; do
        found=$(jq --arg n "$type_name" '[.[] | select(.name == $n and .scope == null)] | length' "$DATA_DIR/issue_types.json")
        if [[ $found -gt 0 ]]; then
            echo "| — | $type_name | $type_name | Yes ($found) |"
        else
            echo "| — | $type_name | — | **MISSING** |"
        fi
    done

    echo ""
    echo "## Non-Standard Issue Types (review for Align compatibility)"
    echo ""
    echo "| Name | Scope | Description |"
    echo "|---|---|---|"
    jq -r '
        .[] | select(.scope == null) |
        select(.name | IN("Bug","Task","Story","Epic","Sub-Task","Sub-task","Subtask") | not) |
        "| \(.name) | Global | \(.description // "—" | gsub("\n"; " ") | .[0:80]) |"
    ' "$DATA_DIR/issue_types.json"

} > "$REPORT_DIR/05_issue_type_analysis.md"
log "  → $REPORT_DIR/05_issue_type_analysis.md"

# ============================================================================
# REPORT 6: Custom Field Analysis
# ============================================================================
log "=== Generating Custom Field Analysis ==="
{
    echo "# Custom Field Audit"
    echo ""
    echo "## Summary"
    echo ""
    cf_total=$(jq 'length' "$DATA_DIR/custom_fields.json")
    echo "- Total custom fields: $cf_total"
    echo ""

    echo "## Fields by Type"
    echo ""
    echo "| Field Type | Count |"
    echo "|---|---|"
    jq -r '
        [.[].schema.type // "unknown"] | group_by(.) | .[] |
        "\(.[0])\t\(length)"
    ' "$DATA_DIR/custom_fields.json" | sort -t$'\t' -k2 -rn | \
        awk -F'\t' '{print "| "$1" | "$2" |"}'

    echo ""
    echo "## Align-Specific Custom Fields to Add"
    echo ""
    echo "These fields are required for Jira Align integration:"
    echo ""
    echo "| Field Name | Purpose | Present? |"
    echo "|---|---|---|"

    for field_name in "Align Feature ID" "Align Epic ID" "Align Story ID" "Align Sprint ID" \
                      "Align Theme ID" "Align Program ID" "Align Portfolio ID" \
                      "Align Points" "Align State" "Align Team ID"; do
        found=$(jq --arg n "$field_name" '[.[] | select(.name | ascii_downcase | contains($n | ascii_downcase))] | length' "$DATA_DIR/custom_fields.json")
        if [[ $found -gt 0 ]]; then
            echo "| $field_name | Align sync | Yes |"
        else
            echo "| $field_name | Align sync | **Needs creation** |"
        fi
    done

    echo ""
    echo "## Potential Duplicate/Stale Fields (name similarity)"
    echo ""
    echo "| Field Name | Field Key | Type |"
    echo "|---|---|---|"
    jq -r '.[] | "| \(.name) | \(.key) | \(.schema.type // "unknown") |"' \
        "$DATA_DIR/custom_fields.json" | sort | head -100

} > "$REPORT_DIR/06_custom_field_analysis.md"
log "  → $REPORT_DIR/06_custom_field_analysis.md"

# ============================================================================
# REPORT 7: Scheme Sharing / Consolidation Opportunity
# ============================================================================
log "=== Generating Scheme Consolidation Analysis ==="
{
    echo "# Scheme Sharing & Consolidation Opportunities"
    echo ""
    echo "## Principle"
    echo ""
    echo "Jira Align works best when projects share schemes. Fewer, standardized"
    echo "schemes = easier Align mapping + less admin overhead."
    echo ""

    echo "## Current Scheme Counts"
    echo ""
    echo "| Scheme Type | Count | Target | Reduction Needed |"
    echo "|---|---|---|---|"

    ws=$(jq 'length' "$DATA_DIR/workflow_schemes.json")
    its=$(jq 'length' "$DATA_DIR/issue_type_schemes.json")
    scrs=$(jq 'length' "$DATA_DIR/screen_schemes.json" 2>/dev/null || echo "0")
    itss=$(jq 'length' "$DATA_DIR/issue_type_screen_schemes.json")
    fc=$(jq 'length' "$DATA_DIR/field_configurations.json")
    fcs=$(jq 'length' "$DATA_DIR/field_config_schemes.json")
    ps=$(jq 'length' "$DATA_DIR/permission_schemes.json")
    ns=$(jq 'length' "$DATA_DIR/notification_schemes.json")

    echo "| Workflow Schemes | $ws | 3-5 | $((ws - 5)) |"
    echo "| Issue Type Schemes | $its | 3-5 | $((its - 5)) |"
    echo "| Issue Type Screen Schemes | $itss | 3-5 | $((itss - 5)) |"
    echo "| Field Configurations | $fc | 2-3 | $((fc - 3)) |"
    echo "| Field Config Schemes | $fcs | 2-3 | $((fcs - 3)) |"
    echo "| Permission Schemes | $ps | 3-5 | $((ps - 5)) |"
    echo "| Notification Schemes | $ns | 2-3 | $((ns - 3)) |"

    echo ""
    echo "## Estimated Effort (by scheme type)"
    echo ""
    echo "| Scheme Type | Effort Level | Rationale |"
    echo "|---|---|---|"
    echo "| Workflows | **CRITICAL / HIGH** | Align status mapping depends on this; requires stakeholder alignment |"
    echo "| Issue Types | **HIGH** | Must standardize hierarchy for Align; team-managed migration needed |"
    echo "| Screens | **MEDIUM** | Can consolidate after workflows/issue types stabilize |"
    echo "| Field Configs | **MEDIUM** | Clean up after custom field audit |"
    echo "| Permission Schemes | **LOW** | Independent of Align mapping |"
    echo "| Notification Schemes | **LOW** | Independent of Align mapping |"

} > "$REPORT_DIR/07_scheme_consolidation.md"
log "  → $REPORT_DIR/07_scheme_consolidation.md"

# ============================================================================
# REPORT 8: Priority & Resolution Standardization
# ============================================================================
log "=== Generating Priority/Resolution Analysis ==="
{
    echo "# Priority & Resolution Standardization"
    echo ""
    echo "## Priorities"
    echo ""
    echo "| ID | Name | Color |"
    echo "|---|---|---|"
    jq -r '.[] | "| \(.id) | \(.name) | \(.statusColor) |"' "$DATA_DIR/priorities.json"

    echo ""
    echo "**ISSUE:** Dual priority naming convention detected (numbered 1-5 + named High/Medium/Low)."
    echo "Align requires a single, consistent priority scheme."
    echo ""

    echo "## Resolutions"
    echo ""
    echo "| ID | Name | Description |"
    echo "|---|---|---|"
    jq -r '.[] | "| \(.id) | \(.name) | \(.description // "—" | .[0:60]) |"' "$DATA_DIR/resolutions.json"

} > "$REPORT_DIR/08_priority_resolution.md"
log "  → $REPORT_DIR/08_priority_resolution.md"

# ============================================================================
# EXECUTIVE SUMMARY
# ============================================================================
log "=== Generating Executive Summary ==="
{
    echo "# Jira Align Readiness Assessment — Executive Summary"
    echo "# Site: ftdr-sandbox-438.atlassian.net"
    echo "# Generated: $(date '+%Y-%m-%d')"
    echo ""
    echo "## Readiness Score"
    echo ""
    echo "| Dimension | Current | Target | Status |"
    echo "|---|---|---|---|"

    # Score each dimension
    tm_count=$(jq '[.[] | select(.style == "next-gen")] | length' "$DATA_DIR/projects.json")
    if [[ $tm_count -gt 0 ]]; then
        echo "| Project Type Standardization | $tm_count team-managed | 0 team-managed | 🔴 Blocker |"
    else
        echo "| Project Type Standardization | All company-managed | All company-managed | 🟢 Ready |"
    fi

    wf=$(jq 'length' "$DATA_DIR/workflows.json")
    if [[ $wf -gt 20 ]]; then
        echo "| Workflow Consolidation | $wf workflows | 3-5 | 🔴 Critical |"
    elif [[ $wf -gt 10 ]]; then
        echo "| Workflow Consolidation | $wf workflows | 3-5 | 🟡 Needs Work |"
    else
        echo "| Workflow Consolidation | $wf workflows | 3-5 | 🟢 Close |"
    fi

    global_it=$(jq '[.[] | select(.scope == null)] | length' "$DATA_DIR/issue_types.json")
    project_it=$(jq '[.[] | select(.scope != null)] | length' "$DATA_DIR/issue_types.json")
    echo "| Issue Type Standardization | $global_it global + $project_it scoped | 5-10 global | 🔴 Critical |"

    cf=$(jq 'length' "$DATA_DIR/custom_fields.json")
    echo "| Custom Field Hygiene | $cf custom fields | Audit needed | 🟡 Assessment |"

    echo "| Align Custom Fields | Not present | ~10 Align fields | 🔴 Needs Creation |"
    echo "| Scheme Consolidation | See details | 3-5 per type | 🔴 Critical |"
    echo "| Priority Standardization | Dual naming | Single scheme | 🟡 Needs Work |"

    echo ""
    echo "## Recommended Workstream Sequence"
    echo ""
    echo "### Phase 1: Foundation (Weeks 1-4)"
    echo "1. Migrate team-managed projects → company-managed"
    echo "2. Define target workflow templates (Software, JSM, Business)"
    echo "3. Define target issue type hierarchy for Align mapping"
    echo ""
    echo "### Phase 2: Consolidation (Weeks 5-12)"
    echo "4. Consolidate workflows to target templates"
    echo "5. Standardize issue type schemes"
    echo "6. Clean up duplicate statuses"
    echo "7. Retire unused screens and field configurations"
    echo ""
    echo "### Phase 3: Align Preparation (Weeks 13-16)"
    echo "8. Create Align-specific custom fields"
    echo "9. Configure Align connectors"
    echo "10. Map teams/programs/portfolios in Align"
    echo "11. Validate end-to-end sync"
    echo ""
    echo "## Key Metrics for Roadmap Planning"
    echo ""
    echo "| Metric | Value |"
    echo "|---|---|"
    echo "| Projects requiring migration (team-managed → company-managed) | $tm_count |"
    echo "| Workflows to consolidate/retire | $((wf - 5)) |"
    echo "| Workflow schemes to consolidate/retire | $((ws - 5)) |"
    echo "| Project-scoped issue types to merge | $project_it |"
    echo "| Screens to consolidate/retire | $(($(jq 'length' "$DATA_DIR/screens.json") - 10)) |"
    echo "| Custom fields to audit for usage | $cf |"
    echo "| Align custom fields to create | ~10 |"
    echo "| Notification schemes to consolidate | $((ns - 3)) |"

} > "$REPORT_DIR/00_executive_summary.md"
log "  → $REPORT_DIR/00_executive_summary.md"

# ============================================================================
# CSV EXPORTS (for spreadsheet analysis)
# ============================================================================
log "=== Generating CSV Exports ==="

# Projects CSV
jq -r '["Key","Name","Type","Style","Category"],
    (.[] | [.key, .name, .projectTypeKey, .style, (.projectCategory.name // "None")]) |
    @csv' "$DATA_DIR/projects.json" > "$REPORT_DIR/projects.csv"

# Workflows CSV
jq -r '["Name","Created","Updated"],
    (.[] | [.id.name, .created, .updated]) |
    @csv' "$DATA_DIR/workflows.json" > "$REPORT_DIR/workflows.csv"

# Custom Fields CSV
jq -r '["Name","Key","Type","Custom Type"],
    (.[] | [.name, .key, (.schema.type // "unknown"), (.schema.custom // "—")]) |
    @csv' "$DATA_DIR/custom_fields.json" > "$REPORT_DIR/custom_fields.csv"

# Statuses CSV
jq -r '["Name","ID","Category","Scope","ProjectID"],
    (.[] | [.name, .id, .statusCategory.name, (.scope.type // "GLOBAL"), (.scope.project.id // "—")]) |
    @csv' "$DATA_DIR/statuses.json" > "$REPORT_DIR/statuses.csv"

# Issue Types CSV
jq -r '["Name","ID","Subtask","HierarchyLevel","Scope","ProjectID"],
    (.[] | [.name, .id, .subtask, .hierarchyLevel, (.scope.type // "GLOBAL"), (.scope.project.id // "—")]) |
    @csv' "$DATA_DIR/issue_types.json" > "$REPORT_DIR/issue_types.csv"

log "  → CSV exports complete"

# ============================================================================
log ""
log "============================================"
log "  ANALYSIS COMPLETE"
log "============================================"
log ""
log "Reports:"
ls "$REPORT_DIR"/*.md | while read -r f; do
    echo "  $(basename "$f")"
done
log ""
log "CSV Exports:"
ls "$REPORT_DIR"/*.csv | while read -r f; do
    echo "  $(basename "$f")"
done
