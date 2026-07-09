# Daily Notes Integration Design

**Date:** 2026-07-09
**Status:** Approved

## Problem

Barrett writes manual daily notes in `work/shared/daily-note/{YYYY-MM-DD}.md` —
short per-day bullet lists of what actually happened, sometimes with context
(coverage for teammates, why work happened). The sprint notes pipeline does not
read them. The only manual input today is the per-sprint `manual-notes.md`.

Daily notes are the most reliable record of what definitely happened on a given
day. The pipeline should treat them as the primary narrative source, with saved
standup output (`work/standup/{date}.md`) filling gaps.

## Precedence rules

- A day's daily note, when present, is the primary record of what happened.
- When no daily note exists for a day, the standup's completed-work content
  covering that day is the primary record.
- When both exist, standup completed-work items not already covered by the
  daily note are merged in as additions.
- Standup "What I'm doing today" content has many false positives. Items there
  that are not corroborated by the daily note are ignored. (Net effect: only
  completed-work sections of standups are ever used.)
- The standup's "Recently closed (recent activity)" subsection lists issues
  that reached Done before the window and were only touched recently — these
  are not genuine completions and are excluded.

## Standup date attribution

A standup file dated `D` reports work done since the previous working day: its
"What I did" section is evidence for day `D-1` (or Friday through Sunday when
`D` is a Monday), not day `D`. Its "Completed today" subsection is evidence for
day `D` itself. The standup header states the coverage window explicitly
("since the last working day (Wednesday, 2026-07-08)"), so attribution is
parseable.

## Architecture

Script + skill, mirroring the insights raw → cleaned pattern:

```text
work/sprint-notes/{sprint}/daily-log/
  raw/
    daily-notes/{date}.md      # copied from work/shared/daily-note/
    standups/{date}.md         # completed-work sections extracted from work/standup/
  merged-raw.md                # merge skill output; never hand-edited
  merged-edited.md             # editable copy; the file downstream steps read
```

### Snapshot script: `src/work_journal/daily_log.py`

Run as `uv run python3 src/work_journal/daily_log.py {sprint}` after
`collect.py`.

1. **Window:** from the prior sprint's `completeDate` (date part, inclusive —
   sprints close midway into a day, so the remainder of the close day is
   sprintless) through this sprint's end date. Read from
   `jira/prior-sprint-info.json` and `jira/sprint-info.json`; fall back to the
   sprint start date if prior-sprint info is missing. Error out with a "run
   collect.py first" message if `sprint-info.json` is missing.
2. **Daily notes:** copy every `work/shared/daily-note/{date}.md` with `date`
   in the window to `daily-log/raw/daily-notes/`. Zero-byte notes are copied
   too (treated downstream as "note exists but empty").
3. **Standups:** for each `work/standup/*.md`, parse the coverage window from
   the "since the last working day" header line (start) and the file date
   (end). Include files whose coverage overlaps the sprint window — this
   correctly pulls in the standup from the first working day after sprint end,
   which is the evidence for the sprint's final day. If a header cannot be
   parsed, fall back to a coverage window of (file date − 3 days, file date)
   rather than dropping the file. From each included standup, extract only
   completed-work evidence to `daily-log/raw/standups/`:
   - the "What I did since the last working day" section, minus the "Recently
     closed (recent activity)" subsection and the "Claude Code" stats table
     (usage stats, not work items; `claude-code/sessions.md` covers this at
     sprint level)
   - the "Completed today" subsection of "What I'm doing today"

   Everything else (doing today, injected, status check, blockers, warnings)
   is dropped at snapshot time. Extraction is header-based against the format
   the standup script itself emits — deterministic and testable.
4. **Coverage summary:** print per-day coverage to stdout — which days have a
   daily note, which have only standup coverage, which have neither (weekends
   flagged) — so gaps are visible before merging.

Idempotent: re-running clears and re-copies `raw/`.

### Merge skill: `/merge-daily-log {sprint}`

Reads `daily-log/raw/`, writes `merged-raw.md` and `merged-edited.md`. One
section per day across the window:

- **Day has a daily note:** the note's bullets are the day's record,
  reproduced essentially verbatim. Standup completed-items attributed to that
  day are compared against the note; anything genuinely new — not already
  covered even in different words (e.g., "closed BSR-2461" vs "Produce
  Blackbaud bulk import files") — is appended under
  **"Also completed (from standup YYYY-MM-DD)"**. This semantic dedup is the
  judgment step that justifies using a skill rather than a script.
- **Day has no daily note:** the standup completed-items covering that day
  become the record, heading marked **"(from standup — no daily note)"**.
- **Multi-day standup windows** (Monday standup covering Fri–Sun): a single
  combined entry spanning those days, since the standup cannot attribute items
  to individual days.
- **Day with neither source:** listed as **"no record"** (weekends noted as
  such) so gaps are visible during review.
- **Empty daily note file:** flagged as "note exists but empty"; standup
  fallback applies.

Day headers match the standup convention (`## Wednesday, 2026-07-08`), weekday
computed by the script and passed through, never inferred. The file opens with
a provenance line (sprint, window, generation date) and a note that
`merged-edited.md` is the copy to edit.

**Two-file contract:** the skill always rewrites `merged-raw.md`. It writes
`merged-edited.md` only if it does not already exist; an existing edited copy
is never clobbered — the skill reports that it left it alone so edits can be
reconciled via `diff merged-raw.md merged-edited.md`. If the user never edits,
the two files are identical and the pipeline works unchanged.

## Downstream integration

- **`/enrich-sprint-data` (now a required step):** enrichment moves from
  "optional but recommended" to a standard step in the workflow. It gates on
  `daily-log/merged-edited.md` (stop with instructions if missing) and reads
  it alongside `manual-notes.md` to extract names, topics, and links worth
  targeting in Gmail/Docs/Calendar searches.
- **`/draft-sprint-notes`:** Phase 1 gains `daily-log/merged-edited.md` as a
  required input — stop with instructions if missing. The merged log is the
  primary record of what actually happened per day: Jira/GitHub/git data
  corroborates and adds links and metrics, but when sources conflict, the
  daily log wins and disagreements get a TODO marker. If enrichment files
  don't exist, the skill pauses and asks the user whether to proceed without
  them rather than deciding on its own.
- **Gate exemption:** sprints before 2026-07-A are exempt from both gates
  (daily notes did not exist yet).
- **`manual-notes.md`:** unchanged — sprint-level extras like Slack links and
  one-off context.
- **Out of scope:** `work/shared/contemporaneous-notes/` remains unread by the
  pipeline.

## Workflow changes (CLAUDE.md)

The sprint notes workflow gains a step between collect (3) and manual notes
(4):

1. Run `uv run python3 src/work_journal/daily_log.py {sprint}`
2. Review the printed coverage summary
3. Run `/merge-daily-log {sprint}`
4. Optionally edit `daily-log/merged-edited.md`

The enrich step's wording changes from optional to required. The
draft-sprint-notes SKILL.md directory-structure diagram gains the `daily-log/`
entries.

## Error handling

- Script fails clearly if `sprint-info.json` is missing (run collect first).
- Missing standups or daily notes are fine; the coverage summary shows holes.
- Unparseable standup headers fall back to a 3-day coverage window.

## Testing

Unit tests for the script only: window computation (including the
prior-sprint-close-day inclusive start), standup header parsing, completed-work
section extraction, and file selection. The skill is prose; its output gets
manual review each sprint by design.
