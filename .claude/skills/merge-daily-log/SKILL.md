---
name: merge-daily-log
description: Merge snapshotted daily notes and standup extracts into a curated per-day log for a sprint. Use when the user says "merge daily log", "merge the daily log", or "/merge-daily-log". Requires the daily log snapshot script (src/work_journal/daily_log.py) to have been run first.
---

# Merge Daily Log

Merge the snapshotted daily notes and standup completed-work extracts for a sprint into a single per-day log. The user will specify a sprint directory name (e.g., `2026-07-A`) that corresponds to a directory under `work/sprint-notes/`.

The design authority for this skill is `docs/process/plans/2026-07-09-daily-notes-integration-design.md`.

## Process

### Phase 1: Load

Read from `work/sprint-notes/{sprint}/`:

1. **`daily-log/raw/daily-notes/`** — one file per day (`{YYYY-MM-DD}.md`), copied from the user's manual daily notes. May include zero-byte files.
2. **`daily-log/raw/standups/`** — one file per standup day (`{YYYY-MM-DD}.md`), containing only completed-work sections extracted from saved standups.
3. **`jira/sprint-info.json`** and **`jira/prior-sprint-info.json`** — to compute the window: from the prior sprint's `completeDate` (date part, inclusive) through this sprint's `endDate` (date part). Fall back to the sprint's `startDate` if prior-sprint info is missing.

If `daily-log/raw/` does not exist, stop and tell the user to run:

```bash
uv run python3 src/work_journal/daily_log.py {sprint}
```

### Phase 2: Merge

Produce one `##` section per day across the whole window, in chronological order. Day headers follow the standup convention: `## Wednesday, 2026-07-08`. Take the weekday from the source filenames and headers — never infer it. If a day has no source file naming its weekday, compute it with `date -j -f %Y-%m-%d {day} +%A` (do not guess).

**Standup date attribution.** A standup file dated `D` covers the window stated in its "What I did since the last working day (Weekday, YYYY-MM-DD)" header: its "What I did" items are evidence for that coverage window (the day(s) before `D`), not for `D` itself. Its "Completed today" items belong to day `D` itself.

Per-day rules:

- **Day with a daily note:** reproduce the note's bullets essentially verbatim as the day's record. Compare standup completed-items attributed to that day against the note; append only items that are genuinely new — not already covered by the note **even in different words** — under `**Also completed (from standup YYYY-MM-DD):**`. The "already covered" judgment is semantic: "closed BSR-2461" is covered by "Produce Blackbaud bulk import files" when they describe the same work.
- **Day without a daily note:** the standup items covering that day become the record. Suffix the day heading with `(from standup — no daily note)`.
- **Multi-day standup coverage** (e.g., a Monday standup covering Friday through Sunday): write one combined section spanning those days (e.g., `## Friday, 2026-07-03 – Sunday, 2026-07-05 (from standup — no daily note)`), since the standup cannot attribute items to individual days. If any of those days has its own daily note, that day keeps its own section and only the note-less days are combined.
- **Day with neither source:** write the heading with `— no record` (note weekends as such, e.g., `— no record (weekend)`).
- **Zero-byte daily note:** flag the day as "note exists but empty", then apply the standup fallback as if there were no note.

### Phase 3: Write output

Both output files start with a provenance block: sprint name, window (start and end dates), generation date, and a note that `merged-edited.md` is the copy to edit (`merged-raw.md` is regenerated and never hand-edited).

1. **`daily-log/merged-raw.md`** — always write (overwrite if present).
2. **`daily-log/merged-edited.md`** — write only if it does not already exist. If it exists, leave it untouched and tell the user to reconcile changes via:

   ```bash
   diff work/sprint-notes/{sprint}/daily-log/merged-raw.md work/sprint-notes/{sprint}/daily-log/merged-edited.md
   ```

Finish by reporting which days had a daily note, which fell back to standup, and which have no record, so the user can fill gaps in `merged-edited.md` before enrichment and drafting.
