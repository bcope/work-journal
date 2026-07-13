---
name: enrich-sprint-data
description: Enrich collected sprint data with Gmail, Calendar, Google Docs, and Jira comment context via MCP. Use after collect.py and before drafting sprint notes. Invoke this skill whenever the user says "enrich", "enrich sprint", "/enrich-sprint-data", or asks to gather additional context for sprint notes beyond what collect.py provides.
---

# Enrich Sprint Data

Gather qualitative context that deterministic scripts cannot capture -- email decisions, meeting patterns, document content, and issue comment threads. The user will specify a sprint directory name (e.g., `2026-02-A`).

## Prerequisites

- `collect.py` has been run for the sprint (at minimum, `jira/sprint-info.json` must exist)
- MCP tools available: Gmail (`mcp__gdocs__search_emails`, `mcp__gdocs__read_email`), Calendar (`mcp__gdocs__list_events`, `mcp__gdocs__search_events`, `mcp__gdocs__get_event`), Google Docs (`mcp__gdocs__search_files`, `mcp__gdocs__read_doc`), Jira (`mcp__jira__get_issue`, `mcp__jira__get_comments`)

## Process

### Phase 0: Gate on the merged daily log

Check that `work/sprint-notes/{sprint}/daily-log/merged-edited.md` exists. If it is missing, stop and tell the user to run:

```bash
uv run python3 src/work_journal/daily_log.py {sprint}
```

then `/merge-daily-log {sprint}`, and re-invoke this skill afterward.

**Exemption:** sprints before 2026-07-A predate daily notes — proceed without the file.

### Phase 1: Build context from collected data

Read these files from `work/sprint-notes/{sprint}/` to build a search context:

1. **`jira/sprint-info.json`** -- Extract `startDate` and `endDate` (YYYY-MM-DD). These scope all MCP searches.
2. **All Jira issue files:**
   - `jira/sprint-planned-completed.json`
   - `jira/sprint-planned-incomplete.json`
   - `jira/sprint-added-completed.json`
   - `jira/sprint-added-incomplete.json`
   - `jira/non-sprint-completed.json`
   - `jira/non-sprint-incomplete.json`
   - `jira/non-sprint-non-assigned-with-worklog.json`

   Extract: issue keys and summaries, project keys, people (reporters, assignees, commenters), and any Google Doc/Sheet URLs in issue descriptions.

   **These JSON files are often too large to read directly** (70k+ tokens each). Use a Python one-liner via Bash to extract just the fields you need:

   ```bash
   uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/{sprint} --doc-urls
   ```

3. **`github/prs.md`** -- Extract repo names and PR titles (additional search context). Optional.
4. **`manual-notes.md`** -- Extract any names, topics, or links the user flagged. Optional.
5. **`daily-log/merged-edited.md`** -- Extract names, topics, and links worth targeting in Gmail/Docs/Calendar searches (required unless the sprint predates 2026-07-A; see Phase 0).
6. **`config/shared.yaml`** -- Read `project_names` for mapping keys to readable names. Use `OWNER_EMAIL` env var for email search context.

Build a structured context with:

- `date_range`: start and end dates
- `date_range_slash`: dates in `YYYY/MM/DD` format (for Gmail queries)
- `date_range_rfc3339`: dates in `YYYY-MM-DDT00:00:00Z` format (for Calendar queries)
- `key_issues`: issues that look important (high priority, Epics/Stories over sub-tasks, issues with many linked items)
- `project_keys`: set of active project keys
- `project_names`: readable names from config
- `people`: set of names/emails from Jira data
- `doc_urls`: any Google Doc/Sheet URLs found in issue descriptions

### Phases 2-5: Run enrichment in parallel

Phases 2 through 5 (Gmail, Calendar, Google Docs, Jira) are independent of each other. Launch them concurrently to save time -- make all the initial MCP calls for each phase in a single tool-call block. The prior sprint check (Phase 6) is also independent and can run alongside them.

### Phase 2: Gmail enrichment

**Goal:** Find email threads that reveal decisions, requests, stakeholder context, and collaboration patterns.

#### Step 1: Search sent mail

Use `mcp__gdocs__search_emails` with:

```
from:me after:{start_date_slash} before:{end_date_slash}
```

Scan results for decision language, stakeholder requests, status updates, and threads with external partners.

#### Step 2: Search for stakeholder threads

For people identified from Jira issues (reporters, commenters on key issues), search:

```
from:{email} after:{start_date_slash} before:{end_date_slash}
```

Limit to 2-3 key stakeholders to avoid excessive API calls.

#### Step 3: Search by project/topic

For each active project with key accomplishments, search:

```
subject:{project_name} after:{start_date_slash} before:{end_date_slash}
```

#### Step 4: Read promising threads

Use `mcp__gdocs__read_email` for threads containing decisions, requests that triggered work, impact evidence, or cross-functional coordination.

#### Step 5: Save output

Write `email/highlights.md`:

```markdown
# Email Highlights

## Key threads

### {Subject line}
- **Date:** {date}
- **Participants:** {from/to}
- **Relevance:** {which Jira issue or project this relates to}
- **Summary:** {2-3 sentence summary of the decision/request/outcome}

## Stakeholder communication patterns

- {Name}: {brief note on interaction pattern}

## Threads worth reviewing manually

- {Subject} ({date}) -- {why it might be relevant}
```

### Phase 3: Calendar enrichment

**Goal:** Understand meeting patterns, identify non-recurring meetings (higher signal), and cross-reference attendees with Jira participants.

#### Step 1: List all events in the sprint

Use `mcp__gdocs__list_events` with `timeMin`/`timeMax` in RFC3339 format and `calendarId: primary`.

#### Step 2: Categorize events

- **Non-recurring events** -- High signal. A one-off meeting usually means something noteworthy happened.
- **Recurring events** -- Lower signal individually, but patterns matter (e.g., "attended 4 of 5 COMPLY standups").

#### Step 3: Get details on interesting events

Use `mcp__gdocs__get_event` for non-recurring events and project-specific meetings. Extract attendee lists, descriptions, and conference details.

#### Step 4: Save output

Write `calendar/events.md`:

```markdown
# Calendar Events

**Sprint dates:** {start_date} to {end_date}

## Non-recurring events (high signal)

- **{date}** {event title} -- Attendees: {names}. {Brief note.}

## Recurring meetings by project

### {Project Name}
- {meeting name}: attended {X} of {Y} during sprint
- Attendees typically include: {names}

## Cross-reference notes

- {Attendee name} appears in {N} meetings and is also {reporter/commenter} on {issue key}.
```

### Phase 4: Google Docs enrichment

**Goal:** Find documents the user created or substantively edited during the sprint that provide evidence of accomplishments, analysis, or decisions.

#### Step 1: Search for docs in the date range

Use `mcp__gdocs__search_files` with:

```
owner:{owner_email} after:{start_date} before:{end_date}
```

The Drive search query operator `after:` matches `modifiedTime`, which over-includes
docs that were merely opened or had their permissions touched. The MCP returns
richer metadata (`createdTime`, `modifiedByMeTime`, `lastModifyingUser`,
`version`, `trashed`, `owners`, `parents`, `shared`, `starred`, `description`,
`driveId`) so we triage in Step 3 rather than relying on the search filter alone.

#### Step 2: Fetch known doc URLs

If Phase 1 extracted Google Doc/Sheet URLs from Jira issue descriptions, fetch those directly using `mcp__gdocs__read_doc` or `mcp__gdocs__read_sheet`. These count as primary regardless of timing — they're explicitly referenced by sprint work.

#### Step 3: Triage results into three buckets

Drop any file with `trashed: true` outright. For everything else, classify into one of:

- **Bucket A — Created in sprint window.** `createdTime` falls within `[start_date, end_date]`. These are the primary key documents. Read in full, summarize, and write to `google-docs/doc-summaries.md` with Jira cross-references and comment context (`mcp__gdocs__get_doc_comments`).
- **Bucket B — Created earlier, but the user attributably touched it during the sprint.** `createdTime < start_date` AND `modifiedByMeTime` is within `[start_date, end_date]`. **Important caveat:** `modifiedByMeTime` bumps for *any* user-attributable change, including permission/share edits — not just content changes. To distinguish, the skill calls `mcp__gdocs__get_revisions` for each Bucket B candidate and inspects whether any revisions exist with `modifiedTime` inside the window. If yes, the file represents real content work and stays in Bucket B; if no in-window revisions exist, demote to Bucket C with a note that the change was metadata-only (typically a permission/share tweak). Log results to `google-docs/modified-not-created.md` with both timestamps and the revision-check finding. Do NOT auto-summarize; the user reviews and manually moves any genuine sprint work into `doc-summaries.md`.
- **Bucket C — Touched in window, but not by the user.** `modifiedTime` in window but `modifiedByMeTime` is missing or outside the window. Probably a collaborator edit or a metadata-only change. Log under a separate section of `modified-not-created.md` for audit visibility.

Tiebreakers and edge cases:

- A doc explicitly referenced from a Jira issue (Step 2) goes into `doc-summaries.md` regardless of bucket.
- Templates and admin docs are skipped as today.
- `version` field on the Files resource bumps for any modification (including metadata) — it is *not* a reliable proxy for content change. Use `get_revisions` instead.

#### Step 3b: Revision check for Bucket B candidates

For each Bucket B candidate (created earlier, `modifiedByMeTime` in window), call `mcp__gdocs__get_revisions` with the file's `id`. Inspect the returned revisions:

- **Has at least one revision with `modifiedTime` in the sprint window AND `lastModifyingUser.emailAddress` matching the user's email** → confirmed content edit by the user. Keep in Bucket B; mark as "content-confirmed" in the output.
- **Has revisions in window but none by the user** → demote to Bucket C ("collaborator content edit") with a note.
- **No revisions in window at all** → demote to Bucket C ("metadata-only / permission change") with a note. This is the common false-positive case: opening a doc, sharing it, or tweaking permissions bumps `modifiedTime` and `modifiedByMeTime` without producing a revision.

Caveat: For Google-native docs (Docs/Sheets/Slides), intermediate revisions may be auto-purged after ~30 days unless explicitly pinned with `keepForever`. For sprint windows ≤ 2–3 weeks this is rarely an issue, but for older sprints the revision list may be sparse. If the revision list is empty AND `createdTime` predates the typical 30-day retention window, treat the result as inconclusive rather than confirmed-Bucket-C; flag it in the output for manual review.

For Bucket A and Bucket C candidates, the revision check is unnecessary — A is already confirmed (created in window) and C was never user-attributable to begin with.

#### Step 4: Save output

Write `google-docs/doc-summaries.md` (Bucket A + Step 2 docs only):

```markdown
# Google Docs Activity

**Sprint dates:** {start_date} to {end_date}

## Key documents

### {Document title}
- **URL:** {url}
- **Created:** {createdTime}  |  **Last modified by me:** {modifiedByMeTime}
- **Related to:** {Jira issue key(s) or project}
- **Summary:** {3-5 sentence summary}
- **Key data points:** {any metrics or quantitative findings}
- **Comments:** {summary of notable comments}

## Documents not found

- {Issue key} references a Google Doc but it was not accessible.
```

Also write `google-docs/modified-not-created.md` (Buckets B + C):

```markdown
# Documents modified during the sprint window but not created in it

Review these and manually fold any real sprint-period work into
`doc-summaries.md` (and the eventual draft).

**Sprint dates:** {start_date} to {end_date}

## Content-edited by me in window (Bucket B, revision-confirmed)

- **{name}** ([url]({url}))
  - Created: {createdTime}  |  modifiedByMeTime: {ts}
  - Revisions in window by me: {N} (most recent: {revisionTimestamp})
  - mimeType: {mimeType}, size: {size}
  - One-line description (no full read).

## Touched in window but not content-edited (Bucket C, revision-check confirms metadata-only)

- **{name}** ([url]({url}))
  - Created: {createdTime}  |  modifiedTime: {ts}  |  lastModifyingUser: {name}
  - get_revisions returned no in-window revisions → permission/share/metadata change only.

## Touched in window by a collaborator (Bucket C, content edit but not by me)

- **{name}** ([url]({url}))
  - Created: {createdTime}  |  modifiedTime: {ts}  |  lastModifyingUser: {name}
  - In-window revisions exist but none are mine.

## Inconclusive (revision history older than ~30-day retention)

- **{name}** ([url]({url}))
  - Created: {createdTime}  |  modifiedByMeTime: {ts}
  - get_revisions returned no entries; doc may have had revisions auto-purged.
    Manual review recommended.
```

### Phase 5: Jira enrichment

**Goal:** Get deeper context on key issues -- comments, linked documents, and decision rationale that the bulk JQL export doesn't include.

#### Step 1: Identify key issues

From the Phase 1 context, select issues for enrichment. Prioritize Epics/Stories over sub-tasks, high/critical priority, issues whose summaries suggest a deliverable, and completed work (which has the most narrative value). Limit to 10-15 issues.

#### Step 2: Fetch details and comments

For each selected issue, use `mcp__jira__get_comments` (and `mcp__jira__get_issue` if needed). Extract impact metrics, decision rationale, stakeholder requests, blockers, and linked resources.

#### Step 3: Save output

Write `jira/issue-details.md`:

```markdown
# Jira Issue Details

Enriched details for key issues in this sprint.

## {ISSUE-KEY}: {Summary}
- **Status:** {status}
- **Category:** {planned-completed | added-completed | non-sprint-completed | etc.}
- **Priority:** {priority}
- **Comment highlights:**
  - {date} -- {author}: {relevant excerpt}
- **Linked documents:** {URLs found in description or comments}
- **Impact evidence:** {any metrics or outcomes mentioned}
```

### Phase 6: Prior sprint continuity

**Goal:** Identify carryover work and ongoing themes from the previous sprint.

Decrement the sprint identifier:

- If current is `YYYY-MM-B`, check `YYYY-MM-A`
- If current is `YYYY-MM-A`, check the prior month's `B` (e.g., `2026-02-A` → `2026-01-B`)

If `work/sprint-notes/{prior-sprint}/draft.md` exists, read it and note continuing projects/themes, incomplete work that was picked up, and prior metrics useful for showing progress over time.

#### Save output

Write `prior-sprint/continuity.md`:

```markdown
# Prior Sprint Continuity

**Current sprint:** {sprint}
**Prior sprint:** {prior-sprint}

## Continuing projects/themes

- **{Project Name}**: {brief description of what carried over}

## Incomplete work picked up

- {ISSUE-KEY}: {summary} -- was {status} at end of prior sprint

## Prior metrics (useful for comparison)

- {metric description}: {value}
```

If the prior sprint directory or draft doesn't exist, write a minimal file noting that:

```markdown
# Prior Sprint Continuity

**Current sprint:** {sprint}
**Prior sprint:** {prior-sprint}

No prior sprint draft found at `work/sprint-notes/{prior-sprint}/draft.md`.
```

## Output files

All saved to `work/sprint-notes/{sprint}/`:

| File | Content |
| --- | --- |
| `email/highlights.md` | Key email threads, stakeholder patterns |
| `calendar/events.md` | Meeting activity, non-recurring events, attendee patterns |
| `google-docs/doc-summaries.md` | Documents created in (or explicitly referenced from) the sprint, with summaries |
| `google-docs/modified-not-created.md` | Audit list of docs touched in the window but created earlier — manual review whether any belong in `doc-summaries.md` |
| `jira/issue-details.md` | Comments and context on key issues |
| `prior-sprint/continuity.md` | Carryover themes, incomplete work, prior metrics |
| `enrichment-summary.md` | Persistent summary with results, warnings, and coverage assessment |

## Error and quality tracking

### Per-file Data Quality table

Every enrichment output file (`email/highlights.md`, `calendar/events.md`, `google-docs/doc-summaries.md`, `google-docs/modified-not-created.md`, `jira/issue-details.md`, `prior-sprint/continuity.md`) must end with a `## Data quality` section separated by a horizontal rule. This table logs every MCP call made during that phase, including successful ones. The Google Docs phase Data Quality table should also report counts for each triage bucket: created-in-window, modified-by-me-but-created-earlier, touched-by-others.

```markdown
---

## Data quality

| Step | Status | Detail |
| --- | --- | --- |
| Sent mail search | ok | |
| Stakeholder search (Jen Pizzurro) | ok | 2 threads found |
| Stakeholder search (Oleg Volkov) | no results | Gmail API returned 0 results |
| get_event for "Oleg / Barrett" | error | Not Found |
| read_doc for "Q1 Analysis" | ok | |
```

Status values:

- **ok** -- Call succeeded and returned useful data. Detail is optional.
- **no results** -- Call succeeded but returned nothing. Detail should explain the likely cause.
- **error** -- Call failed. Detail should include the error message or status.
- **partial** -- Call returned some data but was incomplete (e.g., truncated results, missing fields). Detail should explain what's missing.

Include a row for every MCP call, even successful ones. An all-`ok` table confirms the enrichment ran fully.

### Enrichment summary file

After all phases complete, save `work/sprint-notes/{sprint}/enrichment-summary.md`:

```markdown
# Enrichment Summary

**Sprint:** {sprint}
**Enrichment run:** {today's date}

## Results

| Source | Items found | File | Issues |
| --- | --- | --- | --- |
| Email | 2 threads | email/highlights.md | Sent mail search returned 0 results |
| Calendar | 50 events (5 non-recurring) | calendar/events.md | 5 event detail lookups returned Not Found |
| Google Docs | 18 documents | google-docs/doc-summaries.md | |
| Jira | 7 issues enriched | jira/issue-details.md | |
| Prior sprint | not found | -- | |

## Warnings

- **Email / Sent mail**: Gmail API returned 0 results for `from:me`. Highlights sourced only from stakeholder and topic searches.
- **Calendar / Event details**: `get_event` returned Not Found for 5 non-recurring events. List data (title, time, organizer) still available.

## Coverage assessment

- Email: **{rating}** -- {brief explanation}
- Calendar: **{rating}** -- {brief explanation}
- Google Docs: **{rating}** -- {brief explanation}
- Jira: **{rating}** -- {brief explanation}
```

Coverage ratings:

- **high** -- Primary search methods returned results; most MCP calls succeeded.
- **medium** -- Some data available but key calls failed or returned no results.
- **low** -- Minimal data captured; most calls failed or returned nothing.
- **none** -- Source was entirely unavailable or all calls failed.

The `## Warnings` section should only appear when at least one source has issues. Each warning should name the source, describe the failure, and note what data is still available despite the failure.

## After enrichment

Save `enrichment-summary.md` as described above, then print a terminal summary:

```
Enrichment complete for {sprint}:
  Email: {N} threads saved to email/highlights.md
  Calendar: {N} events ({M} non-recurring) saved to calendar/events.md
  Google Docs: {N} documents summarized in google-docs/doc-summaries.md
  Jira: {N} issues enriched in jira/issue-details.md
  Prior sprint: {found/not found}

  Summary saved to enrichment-summary.md
```

If any source has warnings, print them after the summary:

```
  Warnings:
  - Email / Sent mail: Gmail API returned 0 results for `from:me`
  - Calendar / Event details: get_event returned Not Found for 5 events

Next step: /draft-sprint-notes {sprint}
```

## Tips

- **Be selective with email.** Focus on threads that explain *why* work happened or capture decisions. Skip routine notifications.
- **Non-recurring calendar events are gold.** A one-off meeting usually means something noteworthy happened.
- **Google Docs comments often contain the approval signal.** The doc body describes the analysis; the comments contain "LGTM, let's proceed."
- **Don't over-enrich.** The goal is 10-20 high-quality evidence items, not exhaustive coverage.
- **If an MCP tool fails or returns no results,** log it in the Data Quality table at the end of the output file with the appropriate status (`error`, `no results`, or `partial`) and move on. Partial enrichment is still useful -- the Data Quality table and enrichment summary make gaps visible.
