# Plan: Improve Progress Brief Pipeline

## Context

The quarterly progress brief currently starts from raw Jira CSV exports and loose documents, requiring heavy manual synthesis to translate technical work into business-value narrative. Meanwhile, sprint notes already contain the best evidence — categorized accomplishments with quantified impact, organized by project theme. The enrichment pipeline (email, calendar, docs, Jira comments) adds rich context but is only used for sprint note color, never rolled up for the brief.

This plan connects the sprint-level pipeline to the progress brief through four changes: making sprint notes the primary brief input, adding business value annotations during sprint note drafting, building a quarterly rollup collection script, and tracking impact metrics as they emerge.

## Changes

### 1. Quarter utilities (`src/work_journal/quarters.py`) — NEW, ~25 lines

Pure utility functions for sprint-quarter mapping:

- `quarter_sprints(quarter: str) -> list[str]` — returns 6 sprint dir names for a quarter (e.g., `2026-Q1` -> `["2026-01-A", "2026-01-B", ..., "2026-03-B"]`)
- `sprint_to_quarter(sprint: str) -> str` — maps `2026-03-B` -> `2026-Q1`

No dependencies beyond stdlib. Used by the rollup script and the sprint notes skill (for impact metrics file location).

### 2. Value categories in shared config (`config/shared.yaml`) — EDIT, +10 lines

Add a `value_categories` key with the vocabulary used by annotations:

- `cost_savings` — Reduced spend or projected savings
- `risk_reduction` — Compliance, security, operational continuity
- `process_efficiency` — Automation, time savings, reduced manual work
- `stakeholder_enablement` — Tools, docs, or processes that help others
- `knowledge_capture` — Documentation, analysis, audit reports
- `compliance` — Regulatory requirements, legal obligations
- `revenue_enablement` — Features or changes that support revenue
- `technical_debt` — Code quality, CI/CD, maintainability

### 3. Business value annotations — sprint notes skill update (`.claude/skills/draft-sprint-notes/SKILL.md`) — EDIT, +40 lines

Add a Phase 5 to the existing skill: after writing the narrative draft, produce an `annotations.yaml` file alongside it in the sprint directory. Separate file (not inline in draft.md) keeps the draft readable and the structured data cleanly parseable.

File location: `work/sprint-notes/{sprint}/annotations.yaml`

Format:

```yaml
sprint: "2026-03-B"
accomplishments:
  - headline: "Automated the GG-driven redesignation workflow end-to-end"
    project: Compliance
    value_categories: [process_efficiency, risk_reduction]
    summary: >
      Built complete automation pipeline for monthly redesignation,
      eliminating manual work across Google Sheets, Salesforce, and database.
    jira_keys: [COMPLY-697, COMPLY-698]

  - headline: "Produced Jira Future State executive summary"
    project: Agile
    value_categories: [stakeholder_enablement, process_efficiency]
    summary: >
      Data-driven analysis of 5 Jira problems with effort-value matrix
      and 10-week implementation plan.
    jira_keys: []
```

Each entry corresponds to an H3 accomplishment in the draft. The skill references the value category vocabulary from `config/shared.yaml`.

### 4. Impact metrics extraction — sprint notes skill update (same file) — included in the +40 lines above

Also in the new Phase 5: scan the draft for quantified outcomes (percentages, dollar amounts, time savings, counts) and append entries to the quarter's impact metrics file.

File location: `work/progress-briefs/{YEAR}-{QUARTER}/impact-metrics.yaml`

Format:

```yaml
metrics:
  - sprint: "2026-03-B"
    project: Compliance
    headline: "Automated the GG-driven redesignation workflow end-to-end"
    metric: "13 commits across 5 Claude Code sessions (~2h 10m thinking time)"
    type: count

  - sprint: "2026-03-B"
    project: Upkeep
    headline: "GGSP shared drive audit: 98,165 files, 183.5 GB"
    metric: "76% of files haven't been modified since 2022"
    type: percentage
    value: "76%"
```

Metric types: `percentage`, `dollar_amount`, `time_savings`, `count`, `data_point`.

The skill determines the quarter from the sprint name using the `sprint_to_quarter` mapping (months 1-3 = Q1, 4-6 = Q2, 7-9 = Q3, 10-12 = Q4). Creates the file if it doesn't exist; appends if it does.

### 5. Progress brief scaffold template (`templates/progress-brief.yaml`) — EDIT, +3 lines

Add `impact-metrics.yaml` seed file to the template:

```yaml
base_dir: work/progress-briefs
naming: "{name}"
subdirs:
  - jira-issues
  - docs
files:
  impact-metrics.yaml: |
    metrics: []
required_vars: []
```

### 6. Quarterly rollup collection script (`src/work_journal/collect_progress_brief.py`) — NEW, ~200 lines

Follows the pattern of `collect.py` and `collect_project_status.py`. Takes a quarter identifier as argument.

Usage:

```bash
uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1
uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1 --dry-run
```

Process:

1. Compute the 6 sprint dir names for the quarter via `quarter_sprints()`
2. Check which exist under `work/sprint-notes/`; warn about missing ones
3. For each existing sprint dir:
   a. Read `final.md` (preferred) or `draft.md`
   b. Read `annotations.yaml` (if present — graceful fallback to parsing H3 headlines from markdown)
   c. Read Jira JSON files to count issues by project and category (planned-completed, added-completed, etc.)
   d. Read `github/prs.md` for PR counts
   e. Read `claude-code/sessions.md` for activity stats
   f. Read enrichment files if present (email/highlights.md, google-docs/doc-summaries.md)
4. Read `impact-metrics.yaml` from the progress brief directory
5. Aggregate and write `work/progress-briefs/{YEAR}-{QUARTER}/rollup.md`

Rollup output structure:

```markdown
# Quarterly Rollup: 2026-Q1

**Generated:** 2026-04-10
**Sprints covered:** 2026-02-A, 2026-02-B, 2026-03-A, 2026-03-B
**Sprints missing:** 2026-01-A, 2026-01-B

## Accomplishments by Project

### Compliance
- **2026-03-B:** Automated the GG-driven redesignation workflow end-to-end [process_efficiency, risk_reduction]
- **2026-03-B:** Completed China country labeling investigation with 80+ findings [knowledge_capture, compliance]
...

## Impact Metrics

| Sprint | Project | Metric | Type |
| --- | --- | --- | --- |
| 2026-03-B | Compliance | 13 commits, ~2h 10m thinking time | count |
...

## Summary Statistics

| Metric | Value |
| --- | --- |
| Sprints covered | 4 |
| Jira issues closed | N |
| PRs merged | N |
| Claude Code sessions | N |
| Claude Code thinking time | Xh Ym |

### Issues by Project
| Project | Closed | Incomplete |
| --- | --- | --- |
...

## Key Documents Produced
(from google-docs enrichment across sprints)

## Value Category Distribution
| Category | Count |
| --- | --- |
| process_efficiency | N |
...
```

Key implementation details:
- Use `paths.py` constants (SPRINT_NOTES_DIR, PROGRESS_BRIEFS_DIR)
- Load shared config for project name mapping
- Parse annotations.yaml with `yaml.safe_load`; fall back to regex H3 extraction
- Count Jira issues by loading JSON files and counting entries
- Parse Claude Code stats from sessions.md header lines (regex for "N sessions, Xh Ym thinking")
- Parse PR counts from prs.md section headers

### 7. Updated progress brief skill (`.claude/skills/draft-progress-brief/SKILL.md`) — EDIT, rewrite ~40 of 67 lines

New evidence reading order:

1. **`rollup.md`** — Primary input. Accomplishments organized by project with annotations and metrics pre-extracted.
2. **`impact-metrics.yaml`** — Direct access to quantified outcomes.
3. **`format/`** — Form questions (unchanged).
4. **Individual sprint notes** — `work/sprint-notes/{sprint}/draft.md` or `final.md` for verbatim narrative when rollup is too compressed.
5. **`work/shared/insights/cleaned/{sprint}.md`** — Claude Code insights (unchanged).
6. **`docs/`** — Supplementary documents (unchanged, but less critical now).

Jira CSV exports are no longer the primary source. They stay in the directory for reference.

New drafting instructions:
- Use value category annotations to organize "What is working" by business value theme rather than just listing accomplishments
- Lead with impact metrics for each theme
- Use the rollup's project-by-sprint view to show sustained effort and momentum
- Reference enrichment highlights (stakeholder coordination, documents produced) as leadership evidence

### 8. Paths update (`src/work_journal/paths.py`) — EDIT, +0 lines

No changes needed. PROGRESS_BRIEFS_DIR already exists and is the right constant for the rollup script to use.

## Implementation Order

1. `src/work_journal/quarters.py` — foundational utility, no dependencies
2. `config/shared.yaml` — add value categories vocabulary
3. `templates/progress-brief.yaml` — add impact-metrics.yaml seed
4. `.claude/skills/draft-sprint-notes/SKILL.md` — add Phase 5 (annotations + metrics)
5. `src/work_journal/collect_progress_brief.py` — rollup collection script
6. `.claude/skills/draft-progress-brief/SKILL.md` — rewrite to use rollup
7. Update `CLAUDE.md` with the new workflow step

## Updated Progress Brief Workflow

After implementation, the workflow becomes:

1. Scaffold: `uv run python3 src/work_journal/scaffold.py progress-brief 2026-Q1`
2. (Sprint notes already exist from the sprint workflow — annotations and metrics were captured during drafting)
3. Collect rollup: `uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1`
4. Copy form PDFs to `format/` (unchanged)
5. Optionally add supplementary docs to `docs/`
6. Draft: `/draft-progress-brief 2026-Q1`
7. Edit and finalize

## Verification

- Run `uv run python3 src/work_journal/quarters.py` with a test (or add to pytest)
- Run `uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1 --dry-run` to verify sprint discovery
- Run the full collection and inspect `rollup.md` output
- Run `uv run ruff check .` and `uv run mypy src/` after all Python changes
- Draft sprint notes for a sprint and verify annotations.yaml and impact-metrics.yaml are produced correctly (manual test via `/draft-sprint-notes`)
