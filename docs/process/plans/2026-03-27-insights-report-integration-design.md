# Design: Claude Code Insights Report Integration

## Problem

The Claude Code `/insights` report is a useful input for sprint notes and quarterly
progress briefs, but there is no place for it in the current data organization. The
report also mixes work and personal project content, so it needs a cleaning step
before it can be used in work-facing outputs.

A broader question — whether all collected data should be reorganized into a shared
cache layer (like the jira-analysis repo's per-project issue cache) — was considered
and rejected. The existing per-process collection pattern works well: each process
queries different data for different reasons, the API calls are cheap, and
self-contained sprint directories have real value for reproducibility. The only
genuine cross-process input today is the insights report.

## Approach: Shared inputs directory

Add `work/shared/` for artifacts that span processes. The insights report is the
first occupant. No changes to how Jira, GitHub, git, or Claude Code activity
collection works.

## Directory structure

```text
work/shared/
  insights/
    raw/              # Manual copy of HTML from /insights command
      2026-03-A.html
    parsed/           # Output of Python parsing script
      2026-03-A.json
    cleaned/          # Output of skill cleaning step
      2026-03-A.md
```

Files use the sprint identifier (`YYYY-MM-[A|B]`) across all three subdirectories.
The user renames the raw HTML to match when copying it in.

## Two-stage cleaning pipeline

### Stage 1: Python script (`src/work_journal/clean_insights.py`)

Deterministic parsing and keyword-based classification. Takes a sprint ID argument.

1. Reads `work/shared/insights/raw/{sprint}.html`
2. Uses BeautifulSoup to extract content blocks by CSS class:
   - `project-area` items -> `{name, session_count, description}`
   - `big-win` items -> `{title, description}`
   - `friction-category` items -> `{title, description, examples[]}`
   - `narrative` block (How You Use Claude Code) -> full text
   - `at-a-glance` sections -> `{whats_working, whats_hindering, quick_wins, ambitious_workflows}`
   - Aggregate chart data -> extracted label/value pairs
3. Drops these sections entirely:
   - "Existing CC Features to Try"
   - "New Ways to Use Claude Code"
   - "On the Horizon"
   - Feedback and fun-ending sections
4. Classifies each extractable item:
   - **`keep`** — matches work keywords
   - **`drop`** — matches personal keywords
   - **`review`** — no confident match or mixed content
5. Tags at-a-glance and narrative blocks as `review` (always mix domains)
6. Tags aggregate stats as `stats`
7. Writes `work/shared/insights/parsed/{sprint}.json`

Keyword lists live in `config/shared.yaml` under a new `insights` key:

```yaml
insights:
  work_keywords:
    - compliance
    - disbursement
    - jira workflow
    - standup
    - sprint notes
    - redesignation
    - netSuite
  personal_keywords:
    - company evaluation
    - product category
    - audience profile
    - conversation strategy
```

### Stage 2: Claude Code skill (`/clean-insights`)

LLM-assisted judgment on flagged content. Reads the parsed JSON, writes the final
cleaned markdown.

For each tagged item:

- **`keep`** — converts to markdown as-is
- **`drop`** — excluded entirely
- **`review`** — the skill decides:
  - **Drop** if entirely personal with no transferable takeaway
  - **Keep as-is** if actually work-relevant
  - **Reframe** if there is a useful technique or learning in personal project
    context. Extracts the takeaway and frames it in terms of the skill or tool,
    not the personal domain. Example: "Built a reliable multi-phase research
    pipeline with structured output" rather than "Evaluated 12 companies using
    the evaluation skill"
- **`stats`** — include only if the metric represents something exceptional or
  trend-worthy. "Top tool was Read" gets dropped. Unusually high throughput or a
  notable shift in usage patterns gets a one-sentence callout.

At-a-glance and narrative blocks (tagged `review`) get rewritten to remove personal
project references while preserving work-relevant observations.

Output format:

```markdown
# Claude Code Insights: 2026-03-A

## Work Areas
- **Compliance & Financial Automation Tooling** (~8 sessions) -- ...

## Accomplishments
- ...

## Friction Points
- ...

## Usage Notes
(only if something exceptional surfaced from stats)
```

### Invocation

Two manual steps:

```bash
uv run python3 src/work_journal/clean_insights.py 2026-03-A
# then in Claude Code:
/clean-insights 2026-03-A
```

## Integration with existing processes

### Sprint notes (collect.py)

- Before running collection steps, checks for
  `work/shared/insights/cleaned/{sprint}.md`
- If missing, prints instructions and exits non-zero:

  ```text
  Missing insights report for 2026-03-A.
    1. Run /insights for the sprint date range
    2. Copy the HTML to work/shared/insights/raw/2026-03-A.html
    3. Run: uv run python3 src/work_journal/clean_insights.py 2026-03-A
    4. Run: /clean-insights 2026-03-A
  Then re-run collect.py.
  ```

- The draft-sprint-notes skill reads the cleaned file directly from
  `work/shared/insights/cleaned/{sprint}.md` (no symlinks)

### Progress briefs (/draft-progress-brief)

- Globs `work/shared/insights/cleaned/*.md`
- Selects the six sprint IDs within the quarter
- Synthesizes patterns across the quarter: recurring friction resolved,
  productivity trends, skill growth
- Missing files are noted but do not block the brief (earlier sprints may
  predate this feature)

### What doesn't change

- Standup process — no insights input
- Project status process — no insights input
- All existing Jira/GitHub/git/Claude Code collection — untouched
- Per-process data storage in `work/sprint-notes/` and `work/project-status/`
