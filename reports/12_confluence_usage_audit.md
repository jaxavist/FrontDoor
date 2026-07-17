# Confluence Usage Audit — FrontDoor

**Prepared for:** Tina | **Site:** ftdr-sandbox-438.atlassian.net | **Updated:** 2026-07-17

## Purpose

Baseline of the current Confluence footprint to inform space consolidation and
restructuring. Identifies where content lives, what's active vs. abandoned, and
which spaces are candidates for archival or merge.

Full per-space and per-page detail lives in the data files listed below. This
document is the summary; the spreadsheets are the working data.

## Headline Findings

- **1,980 total spaces**, but **1,834 (93%) are personal spaces**. The real
  restructuring surface is the **146 regular (team/project) spaces**.
- **53,033 pages** across all spaces.
- **1,489 spaces (75%) not updated in over a year**; 1,272 (64%) idle over two years.
- **621 spaces are empty** (homepage only) — immediate archival candidates.
- **979 spaces have a single contributor** — likely individual or orphaned.

The practical story: this is not a 1,980-space problem. It's ~146 team spaces to
organize, plus a large tail of personal and abandoned spaces to clean up.

## Metrics Summary

| Metric | Value |
|---|---|
| Total spaces | 1,980 |
| — Personal spaces | 1,834 |
| — Regular (team/project) spaces | 146 |
| Total pages | 53,033 |
| Stale spaces (idle >1yr) | 1,489 |
| Stale spaces (idle >2yr) | 1,272 |
| Empty spaces (≤1 page) | 621 |
| Single-contributor spaces | 979 |
| Space consolidation candidates | 1,879 |

## Recommended Consolidation Path

1. **Personal spaces (1,834):** archive stale ones, migrate any valuable content
   into team spaces. Largest volume, lowest restructuring value.
2. **Empty spaces (621):** safe to archive/delete — no real content.
3. **Stale team spaces (idle >1yr):** evaluate for merge into active spaces.
4. **Focus restructuring on the ~146 regular spaces** — that's the footprint that
   matters for the go-forward information architecture.

## Data Files

Detailed tables were moved out of this document to the files below so this
summary renders in full on GitHub (large embedded tables get truncated).

| File | Contents |
|---|---|
| `confluence_spaces.xlsx` | Consolidated space metrics workbook (primary deliverable) |
| `confluence_spaces.csv` | Every space: pages, contributors, last activity, days idle |
| `confluence_pages.csv` | Every page: last updated, version |
| `space_keys_regular.csv` | The 146 regular / communal space keys |
| `space_keys_personal.csv` | The 1,834 personal space keys |

To rank spaces by consolidation priority, sort `confluence_spaces.csv` (or the
xlsx) by **Days Idle** descending, then filter out personal spaces to focus on
the team footprint.

## Caveat on Page Views

Page **view/visit counts are not reliable in this dataset**. This audit ran against
the sandbox, which carries no analytics history — nearly all pages show zero views
regardless of real usage. Last-modified dates, page counts, and contributor counts
are accurate. **For genuine visit data, re-run against the production Confluence
instance.**
