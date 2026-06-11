# Standup: separate stale-but-touched Done issues from true yesterday completions

## Problem

The standup `completed_yesterday` query keys off Jira's `updated` field:

```jql
assignee = {account_id} AND updated >= "{yesterday}" AND updated < "{today}"
  AND statusCategory = Done AND issuetype != "Time Tracking" AND filter != 15385
```

`updated` bumps on *any* field change — automation touches, comments, label edits.
So an issue that reached Done days ago resurfaces under "What I did yesterday" the
moment anything touches it. Example: COMPLY-723 was Closed on 2026-05-29 but showed
up in the 2026-06-03 standup because an automation updated it that morning.

## Key insight

Jira already returns `statuscategorychangedate` — the timestamp the issue last
entered its current status category (i.e. when it actually became Done) — in the
default bulkfetch response. No changelog crawl, no extra API calls. COMPLY-723:

- `updated`: 2026-06-03 (automation touch)
- `statuscategorychangedate`: 2026-05-29 (real completion)
- `resolutiondate`: 2026-05-29

## Decision

Keep the broad `updated`-based query (it's a cheap superset), then split the
results in Python by `statuscategorychangedate`:

- In `[yesterday, today)` → genuine yesterday completion → main "Jira" list.
- Before `yesterday` → Done earlier, only touched yesterday → new
  **"Recently closed (activity yesterday)"** subsection, annotated with the
  actual close date.

This preserves visibility (the item isn't silently dropped) while keeping the
main list honest.

## Implementation

1. **`src/work_journal/standup.py`**
   - Add a helper `completion_date(issue) -> str | None` that returns the date
     prefix (`YYYY-MM-DD`) of `statuscategorychangedate`, falling back to
     `resolutiondate`, else `None`.
   - In `collect_data`, after the `completed_yesterday` query, partition results:
     `completed["jira"]` keeps issues where
     `yesterday_str <= completion_date < today_str` (or date unknown — preserve
     current behavior rather than lose an item); the rest go to a new
     `completed["recently_closed"]` bucket. String comparison on ISO date
     prefixes handles the Monday → Friday window correctly.
   - Request explicit `fields` on the completed query
     (`summary`, `status`, `statuscategorychangedate`, `resolutiondate`) so the
     field is guaranteed present. Add an optional `fields` passthrough to
     `query_jira`.
   - `format_jira_issue`: add optional `completion_date` param that appends the
     date after the status (e.g. `— Closed 2026-05-29`).
   - `format_markdown`: render the `recently_closed` bucket as a
     "### Recently closed (activity yesterday)" subsection right after the main
     completed Jira list. Include it in the `has_yesterday` emptiness check so a
     day with only stale touches doesn't print a contradictory "Nothing tracked"
     beneath the recently-closed note.
   - Seed `data["completed"]["recently_closed"] = []` in the initial dict.

2. **`config/standup.yaml`** — update the `completed_yesterday` comment to note
   the query is intentionally a broad `updated` superset, post-filtered by
   `statuscategorychangedate` in the script.

3. **`.claude/skills/standup/SKILL.md`** — document the new subsection in the
   Phase 3 presentation guidance.

4. **`tests/test_standup.py`** (new) — unit-test the partition: an issue
   transitioned in-window stays in `completed`, an issue transitioned earlier but
   updated in-window lands in `recently_closed`, and a missing date stays in
   `completed`.

## Cost

Zero additional API calls. One extra date comparison per completed issue.
