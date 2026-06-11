# Plan: Enrichment error/failure surfacing

## Context

The `/enrich-sprint-data` skill makes many MCP calls across four sources (Gmail, Calendar, Google Docs, Jira). When calls fail -- like the 5 calendar `get_event` calls that returned "Not Found" in the latest run -- there's no consistent way to surface those failures. The current skill just says "note it in the output file and move on," which leads to ad-hoc reporting (an undocumented "Notes" section in email, nothing at all for calendar failures). The terminal summary isn't persisted, so the overview disappears when the conversation ends.

## Changes

### 1. Add "Data quality" footer to each enrichment output file

Each of the four output files gets a mandatory final section with a table logging every MCP call and its status (`ok`, `no results`, `error`, `partial`).

### 2. Save enrichment summary to `enrichment-summary.md`

Replace the terminal-only summary with a persistent file at `work/sprint-notes/{sprint}/enrichment-summary.md` containing Results table, Warnings section, and Coverage assessment (high/medium/low/none ratings).

### 3. Wire enrichment quality into draft-sprint-notes

- Phase 2: Read `enrichment-summary.md` first (item 0). If a source has `low` or `none` coverage, track it for TODO markers.
- Writing guidelines: Add bullet about enrichment gaps and TODO markers.
- Directory structure: Add `enrichment-summary.md` line.

### 4. Update the tip about failures

Replace the vague "note it in the output file" tip with a reference to the Data Quality table format.

## Files modified

1. `.claude/skills/enrich-sprint-data/SKILL.md`
2. `.claude/skills/draft-sprint-notes/SKILL.md`
