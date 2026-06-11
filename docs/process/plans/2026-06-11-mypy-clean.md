# Plan: Make mypy fully clean

Goal: eliminate all 26 `uv run mypy src/` errors so type checking passes with the
current config, then make CI gate on it.

## Root-cause groups

The 26 errors trace to 8 root causes. Most are single-line annotation fixes that
cascade across multiple reported errors.

| # | Location | Errors fixed | Root cause | Fix |
| --- | --- | --- | --- | --- |
| A | `claude_code/collect_activity.py:72` (`load_history` return) | 6 (110, 646, 651, 652, 673, `standup.py:164`) | Return annotated `dict[str, list[dict]]` but builds `dict[str, dict]` | Correct annotation to `dict[str, dict]` |
| B | `claude_code/collect_activity.py:156` (`analyze_conversation`) | 9 (202, 205, 222×2, 223×2, 233, 252, 271) | `result` literal infers `dict[str, object]` | Add `ConversationMetrics` TypedDict, annotate local `result`; keep `-> dict` return |
| C | `claude_code/collect_activity.py:527,548` | 4 (527, 530, 548, 551) | Loop var `docs` (dict) reused for a list | Rename reassignment to `entries`, update usages |
| D | `jira/query_sprint_info.py:57` | 1 | `params` mixed int/str infers `dict[str, object]` | Annotate `params: dict[str, str \| int]` |
| E | `jira/query_sprint_info.py:169,178,181` | 3 | `result` rebound across `dict` / `dict\|None` / `list[dict]` | Annotate `result: dict[Any, Any] \| list[dict[Any, Any]] \| None` |
| F | `jira/query_issues.py:114` | 1 | `keys` is `list[Any\|None]`, `_bulk_fetch` wants `list[str]` | Wrap in `str(...)` in the comprehension |
| G | `claude_code/collect_activity.py:373` | 1 | `sorted(key=dict.get)` overload rejected | Use `key=lambda c: agg_categories[c]` |
| H | `gcalendar/query_events.py:23` | 1 | `googleapiclient` has no stubs / `py.typed` | `[[tool.mypy.overrides]]` `ignore_missing_imports` for `googleapiclient.*` |

## Verification

- `uv run mypy src/` → 0 errors
- `uv run pytest` → still green
- `uv run ruff check .` and `uv run ruff format --check .` → clean

## CI

- Remove `continue-on-error: true` from the mypy step in `.github/workflows/ci.yml`
  so type checking gates going forward.

## Out of scope

- Tightening the mypy config (`disallow_untyped_defs`, `warn_return_any`, etc.) is a
  separate, larger effort. This plan only makes the codebase clean under the current
  config.
