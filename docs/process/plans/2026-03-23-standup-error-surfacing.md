# Plan: Surface data collection errors in standup script

## Context

The standup script silently swallows all connectivity and permissions errors, making it impossible to tell the difference between "no data" and "data source broken." We just experienced this: missing Jira credentials produced an empty standup with no indication anything was wrong. The project's other collection scripts (`collect.py`, `collect_project_status.py`) already follow a better pattern -- catch exceptions, print warnings to stderr, continue.

## Approach

The script always continues on error (no interactive prompting), but makes failures visible so the user can decide whether to stop and fix or proceed. This works both from the CLI and when invoked by Claude Code.

1. Collect warnings into a `warnings` list during `collect_data`
2. Print each warning to stderr immediately (visible during collection)
3. Include a "Data collection warnings" section at the bottom of the markdown output
4. Exit with a non-zero exit code when warnings are present, so callers can detect issues

This is a single-file change to `src/work_journal/standup.py`.

## Changes

### 1. Update `query_jira` to accept warnings list and label

Add `warnings: list[str]` and `label: str` parameters. On exception, append a message to warnings and print to stderr. Return `[]` as before.

### 2. Update `get_active_sprint_id` to accept warnings list

On exception, append message and print to stderr. Return `""` as before.

### 3. Update `query_git_log` to accept warnings list

Warn if `GIT_REPOS_DIR` doesn't exist. Wrap commit collection in try/except.

### 4. Update `collect_claude_activity` to accept warnings list

Wrap the session processing loop in try/except. Missing history file is not an error (leave as-is returning None).

### 5. Wrap GitHub PR calls in try/except

They print warnings internally, but an unexpected exception could still crash the process. Catch and add to warnings list.

### 6. Update `collect_data` to thread warnings through all calls

- Create `warnings = []` at the top, add to `data["warnings"]`
- Pass warnings to each helper with descriptive labels for Jira queries:
  - "Completed yesterday (Jira)"
  - "In-progress (Jira)"
  - "Blocked (Jira)"
  - "Injected (Jira)"

### 7. Add warnings section to `format_markdown`

After the Blockers section, before the return, add a "Data collection warnings" section if any warnings exist. Bullet list format.

### 8. Non-zero exit code on warnings

In `main()`, after writing output, exit with code 1 if `data["warnings"]` is non-empty. This lets callers (scripts, Claude Code skill) detect that something went wrong without parsing the output.

## Files

- `src/work_journal/standup.py` -- only file modified

## Verification

1. Run standup with valid credentials -- confirm no warnings section appears and exit code is 0
2. Temporarily set `JIRA_API_TOKEN=bad` in `.env` and re-run -- confirm warnings appear in both stderr and the markdown output, and exit code is 1
3. Run with `--json` -- confirm warnings array present in JSON output
