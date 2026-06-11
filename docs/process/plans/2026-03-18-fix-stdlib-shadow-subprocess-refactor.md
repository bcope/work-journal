# Refactor: Fix stdlib shadow, eliminate subprocess antipattern, expand GitHub module

## Context

`standup.py` crashes because `src/work_journal/calendar/` shadows Python's stdlib
`calendar` module. While investigating, we found two other problems worth fixing
together: orchestrator scripts shell out to sibling Python modules via subprocess
instead of importing them, and `standup.py` runs raw `gh` commands instead of
using the GitHub module.

## Task 1: Rename `calendar` to `gcalendar`

Rename the package directory and update all references.

### Files to change

- `git mv src/work_journal/calendar/ src/work_journal/gcalendar/`
- `git mv tests/calendar/ tests/gcalendar/`
- `tests/gcalendar/test_query_events.py` -- update import from `work_journal.calendar` to `work_journal.gcalendar`
- `src/work_journal/collect_project_status.py:160` -- update subprocess path (will be removed entirely in Task 2, but fix it now so Task 1 is self-contained)
- `src/work_journal/gcalendar/query_events.py` -- update docstring path
- `CLAUDE.md` -- update project structure reference

Note: `docs/plans/` files reference `src/calendar/` but those are historical. Skip them.
Output data paths like `calendar/events.json` are data directories, not Python packages -- leave them.

### Verify

`uv run ruff check . && uv run pytest tests/gcalendar/`

## Task 2: Replace subprocess-to-self calls with direct imports

Each query module already exposes importable functions. Replace subprocess calls
with direct function calls.

### Error handling prerequisite: fix `_run_gh()` in `query_github_prs.py`

`_run_gh()` calls `sys.exit(1)` on error, which is fatal when imported. Change
it to raise a `GhError` exception. Update `main()` to catch it and exit.

### 2A: `collect.py` -- replace 4 of 5 subprocess calls

| Call | Import | Notes |
| --- | --- | --- |
| `jira/query_sprint_info.py` | `find_sprint_by_name()` | Needs a session; use `_make_session()` from that module |
| `jira/query_issues.py` | `search_issues(jql)` | Returns `list[dict]`; write JSON to file ourselves |
| `github/query_github_prs.py` | `search_authored_prs()`, `search_reviewed_prs()`, `_format_markdown()` | Replicate dedup logic from CLI's `main()` |
| `git/query_git_log.py` | `find_git_repos()`, `get_commits()`, `format_markdown()` | Loop repos ourselves, same as CLI's `main()` |

Keep `claude_code/collect_activity.py` as subprocess -- its CLI does stats
caching, raw file copying, and document extraction not exposed as functions.

Keep `run_helper()` for that one remaining call (rename to clarify scope if needed).

### 2B: `collect_project_status.py` -- replace 2 subprocess calls

| Call | Import | Notes |
| --- | --- | --- |
| `jira/query_issues.py` | `search_issues(jql)` | Same pattern as 2A |
| `calendar/query_events.py` | `query_events()`, `filter_events_by_keywords()`, `format_event()` | Use `gcalendar` package name from Task 1 |

GitHub is already imported directly -- no change needed. Remove `subprocess`
import after.

### 2C: `standup.py` -- replace 2 subprocess calls

| Call | Import | Notes |
| --- | --- | --- |
| `jira/query_issues.py` | `search_issues(jql)` | Wrap in try/except, return `[]` on failure |
| `git/query_git_log.py` | `find_git_repos()`, `get_commits()`, `format_markdown()` | Same loop pattern |

Remove `run_helper()` and `SRC_DIR` import after. Keep `run_command()` removal
for Task 3 (it's used for `gh` calls that Task 3 replaces).

## Task 3: Expand the GitHub module

### 3A: Add two functions to `query_github_prs.py`

- `search_merged_prs(since, until, org, author=None)` -- `--merged-at` filter
- `search_open_prs(org, author=None)` -- `--state=open`, no date filter

Both follow the `search_repo_prs()` error pattern: use `subprocess.run` directly
(not `_run_gh`), return empty list on error.

### 3B: Update `standup.py` to use new functions

- Import `search_merged_prs`, `search_open_prs` from the module
- Change `data["completed"]["prs"]` and `data["in_progress"]["prs"]` from raw
  JSON strings to `list[dict]`
- Update `format_github_prs()` to accept `list[dict]` instead of parsing JSON
- Remove `query_github_prs()`, `run_command()`, and `subprocess` import

## Implementation order

1. Task 1 (rename calendar to gcalendar)
2. Task 2 prerequisite (fix `_run_gh` error handling)
3. Task 3A (add new GitHub functions)
4. Task 2A (refactor collect.py)
5. Task 2B (refactor collect_project_status.py)
6. Task 2C + 3B (refactor standup.py -- combines subprocess removal and new GitHub imports)

Run `uv run ruff check . && uv run pytest` after each step.
