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

Read the markdown output from stdout. The script also saves a copy to `work/standup/{today}.md` and prints the path to stderr — reference that file if you need to point the user at the saved notes (e.g. for the full Claude Code breakdown).

### Phase 2: Enrich with MCP context

After reading the script output, enrich with live context.

1. **Calendar (always)** — Use the Google Calendar MCP `list_events` tool to check today's calendar. Note any meetings that might affect priorities (skip recurring standups, 1:1s, etc. — focus on non-recurring meetings, planning sessions, or review meetings). Run this every time.
2. **Jira comments (as needed)** — Use the Jira MCP `get_comments` tool on a specific issue only when the script output is ambiguous and a comment would clarify it — e.g., a ticket sitting in an unexpected status, an item that seems stalled, or two issues that look like they overlap. Don't sweep every in-progress issue by default; pull comments to resolve a specific question, then move on.

### Phase 3: Present the stand-up notes

Present the final stand-up notes to the user. Apply light editorial polish:

- Group related Jira issues and PRs that are part of the same effort
- Fold today's calendar into "What I'm doing today": if there are relevant meetings, add a brief note (e.g., "Also: Sprint planning at 2pm"); if there are none worth flagging, no line is needed
- Mirror the script's section structure. The script emits, in order: **What I did yesterday** (with subsections as data exists: Jira, Recently closed (activity yesterday), Jira (work logged, not closed), Pull requests (merged), Pull requests (closed, not merged), Commits, Claude Code), **What I'm doing today** (Jira, Open PRs), **Injected into sprint** (only when there are injected issues), **Status check (In Progress, not in active sprint)**, and **Blockers**. A "Data collection warnings" section may also appear if a collection step failed — surface those to the user rather than putting them in the Slack-ready notes. Keep the Slack-ready version concise; drop empty sections.
- **Recently closed (activity yesterday):** The script lists these separately from yesterday's genuine completions — they reached Done earlier and were only touched yesterday (e.g. by automation), so each shows its actual close date. Don't present them as work done yesterday. Mention them only if relevant (e.g. a stakeholder marked something Accepted), otherwise it's fine to omit them from the Slack-ready notes.
- **Claude Code section:** Show the full per-repo breakdown for ALL repos. The script emits a totals line (`N sessions, Xh Ym thinking, T turns, U user inputs`) followed by a `Repo | Sessions | Thinking | User inputs` table sorted by session count descending. Keep that totals-line-plus-table format and the "user inputs" wording. Never truncate or summarize into "and others."

The output should be ready to copy into Slack or read aloud in a stand-up meeting. Keep it concise — aim for quick readability, not exhaustive detail.

## Notes

- The script reads config from `config/standup.yaml` and `config/shared.yaml` (Jira account ID, GitHub org, git settings)
- On Mondays, "yesterday" automatically refers to the previous Friday
