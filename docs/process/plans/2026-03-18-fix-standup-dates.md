# Fix standup data accuracy: dates, open PRs, Claude output

## Context

The standup script (`src/work_journal/standup.py`) has three data accuracy problems:

1. Git log and GitHub CLI queries use bare dates (`2026-03-17`) which git interprets as "that date at the current wall-clock time," not midnight. A standup run at 5pm captures from yesterday 5pm to today 5pm, misattributing today's commits to yesterday.
2. Open PRs are fetched with no date filter, showing every open PR regardless of relevance.
3. The Claude Code section includes a tool category breakdown that isn't useful for standup.

## Changes

### 1. New date utility -- `src/work_journal/dates.py`

Create `midnight_iso(date_str: str) -> str` that converts `YYYY-MM-DD` to `YYYY-MM-DDT00:00:00{offset}` using the system's local timezone.

### 2. Apply `midnight_iso` to git log -- `query_git_log.py`

In `get_commits()`, convert `since` and `until` via `midnight_iso` before passing to `--after`/`--before`.

### 3. Apply `midnight_iso` to GitHub queries -- `query_github_prs.py`

Convert date params in all four search functions plus add optional `since` to `search_open_prs`.

### 4. Filter and subdivide open PRs -- `standup.py`

Pass `since` as 7 days before yesterday. Split open PRs into "Active yesterday" and "Other recent" groups.

### 5. Remove tool categories from Claude output -- `standup.py`

Delete tool category block in `format_claude_summary` and `agg_categories` accumulation in `collect_claude_activity`.

### 6. Tests -- `tests/test_dates.py`

Unit tests for `midnight_iso`.

## Files to modify

| File | Changes |
| --- | --- |
| `src/work_journal/dates.py` | New -- `midnight_iso` utility |
| `src/work_journal/git/query_git_log.py` | Apply `midnight_iso` in `get_commits` |
| `src/work_journal/github/query_github_prs.py` | Apply `midnight_iso` in all search functions; add `since` to `search_open_prs` |
| `src/work_journal/standup.py` | Pass recent window to `search_open_prs`; subdivide open PR display; remove tool categories |
| `tests/test_dates.py` | New -- unit tests for `midnight_iso` |
