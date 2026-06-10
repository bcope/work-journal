# Standup: "since last working day" framing

Date: 2026-06-10

## Problem

The standup script overloaded one concept — `yesterday` — to mean both the
reporting-window start and a literal calendar word. On a Monday the window start
is Friday, but the section was titled "What I did yesterday (Friday, ...)",
which is wrong: Friday is not yesterday. The weekend-skip was also hardcoded to
Monday only (`today - 3 days`), so it did not generalize. Separately, the
`work_logged` Jira query matched a single day (`worklogDate = {yesterday}`), so
worklogs entered on Saturday/Sunday were missed even though the completed-work
query already used a range.

## Goal

Reframe the lookback as "since the last working day" and make sure all work
between the last working day (inclusive) and today is captured — including
weekend work. Weekends are skipped automatically; holidays/PTO are handled only
when passed in explicitly via the new `--since` flag.

## Changes

1. `resolve_dates` — generalize: walk back from `today - 1` skipping Saturday and
   Sunday to find the last working day. Rename param `yesterday_override` →
   `since_override`. Override path returns the given date verbatim. Docstring
   explains the returned start is the last working day and that the window
   `[since, today)` therefore spans intervening weekend days.
2. CLI flag `--yesterday` → `--since` (dest `since`); update help text and the
   stderr collection message.
3. Output label — `## What I did since the last working day ({weekday, date})`,
   reusing `with_weekday` for the deterministic day name.
4. `config/standup.yaml` — widen `work_logged_yesterday` from
   `worklogDate = "{yesterday}"` to `worklogDate >= "{yesterday}" AND worklogDate
   < "{today}"` so weekend worklogs are captured. Update its comment.
5. Keep internal plumbing names (`{yesterday}` JQL token, `yesterday_str`
   locals, `data["yesterday"]`, `completed_yesterday` query key) as the
   conventional name for "window start" to avoid a broad rename and config break.
6. Docs — update module docstring, `SKILL.md`, and `CLAUDE.md` to the `--since`
   flag and the "last working day" framing; note that PTO/holiday gaps are
   handled by passing `--since` explicitly.
7. Tests — add `resolve_dates` cases (Tuesday→Monday, Monday→Friday, weekend
   run→Friday, explicit override) via monkeypatched `date.today`; existing
   partition tests stay valid.

## Out of scope

Automatic holiday/PTO calendars; renaming internal variables/config tokens.
