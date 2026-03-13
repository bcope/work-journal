---
name: standup
description: Generate daily stand-up notes covering yesterday's completed work, today's plan, and blockers. Use when the user says "standup", "stand-up", "daily standup", or "/standup".
---

# Skill: Stand-up Notes

## When to use

Use this skill when the user asks to prepare their daily stand-up, or says `/standup`. Generates ready-to-use stand-up notes covering what was done yesterday, what's planned for today, and any blockers.

## Process

### Phase 1: Run the stand-up script

Run the collection script:

```bash
uv run python3 src/work_journal/standup.py
```

If the user specifies a particular "yesterday" date, pass it:

```bash
uv run python3 src/work_journal/standup.py --yesterday YYYY-MM-DD
```

Read the markdown output from stdout.

### Phase 2: Enrich with MCP context (optional)

After reading the script output, optionally enrich with live context:

1. **Jira comments** — For each in-progress issue, use the Jira MCP `get_comments` tool to check for recent comments or status updates that add context (e.g., "waiting on review from X").
2. **Calendar** — Use the Google Calendar MCP `list_events` tool to check today's calendar. Note any meetings that might affect priorities (skip recurring standups, 1:1s, etc. — focus on non-recurring meetings, planning sessions, or review meetings).

### Phase 3: Present the stand-up notes

Present the final stand-up notes to the user. Apply light editorial polish:

- Group related Jira issues and PRs that are part of the same effort
- Flag items that have been in progress for multiple days (if visible from the data)
- If today's calendar has relevant meetings, add a brief note under "What I'm doing today" (e.g., "Also: Sprint planning at 2pm")
- Keep the three-section format: Yesterday / Today / Blockers

The output should be ready to copy into Slack or read aloud in a stand-up meeting. Keep it concise — aim for quick readability, not exhaustive detail.

## Notes

- The script reads config from `work/sprint-notes/config.yaml` (Jira account ID, GitHub org, git settings)
- Blocker detection depends on the `standup.queries.blocked.jql` template in config.yaml — if it contains a placeholder condition, blockers will be empty until the user customizes it
- On Mondays, "yesterday" automatically refers to the previous Friday
