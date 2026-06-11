# Plan: Stand-up Script

## Context

The daily stand-up at GlobalGiving follows three questions: "What did I do yesterday?", "What am I doing today?", and "Am I blocked on anything?" Answering these requires checking Jira, GitHub, and git every morning. This plan adds a script that automates that lookup and produces ready-to-use stand-up notes.

## Approach

Create a single new script `src/standup.py` that reuses existing helpers via subprocess (matching the `collect.py` pattern) and reads shared config from `config.yaml`. No new dependencies needed beyond what's already in the project.

## Changes

### 1. New file: `src/standup.py`

**Date handling:**

- Default: yesterday = previous calendar day, today = current date
- Weekend-aware: if today is Monday, yesterday = previous Friday
- Accept optional `--yesterday YYYY-MM-DD` override for flexibility

**Data collection (6 subprocess calls):**

| Question | Source | Query |
| --- | --- | --- |
| Yesterday | Jira | `assignee = {account_id} AND updated >= "{yesterday}" AND updated < "{today}" AND statusCategory = Done` |
| Yesterday | GitHub | `gh search prs --author=$GIT_AUTHOR --merged={yesterday}..{today} --org=$GITHUB_ORG` |
| Yesterday | Git | `query_git_log.py --since {yesterday} --until {today}` |
| Today | Jira | `assignee = {account_id} AND status = "In Progress"` |
| Today | GitHub | `gh search prs --author=$GIT_AUTHOR --state=open --org=$GITHUB_ORG` |
| Blocked | Jira | Placeholder — user will provide custom JQL |

Calls existing helpers:

- `src/jira/query_issues.py "{jql}" --pretty` for each Jira query (3 calls)
- `src/git/query_git_log.py --since ... --until ...` (1 call)
- `gh search prs ...` directly via subprocess (2 calls)

**Config:** Reads `account_id`, `git.repos_dir`, `git.author`, `github.org`, and `project_names` from `work/sprint-notes/config.yaml`. Adds a new `standup` section to `config.yaml` with the three JQL templates, so blocker logic is easy to customize.

**Output:** Prints markdown to stdout, structured as three sections: Yesterday / Today / Blockers.

**Flags:**

- `--yesterday YYYY-MM-DD` — override the "yesterday" date
- `--json` — output raw JSON instead of markdown

### 2. New file: `.claude/skills/standup.md`

A skill `/standup` that:

1. Runs `uv run python3 src/standup.py`
2. Reads the markdown output
3. Optionally enriches with MCP context (recent Jira comments on in-progress items, calendar for today's meetings)
4. Presents the stand-up notes, ready to copy into Slack or read aloud

### 3. Modified file: `work/sprint-notes/config.yaml`

Add a `standup.queries` section with JQL templates for completed_yesterday, in_progress, and blocked.

## Verification

1. Run `uv run python3 src/standup.py` and confirm output covers all three sections
2. Run `uv run python3 src/standup.py --yesterday 2026-03-03` to test date override
3. Run on a Monday to verify weekend logic (yesterday = Friday)
4. Run `/standup` skill to verify enriched output
5. Test with `--json` flag for structured output
