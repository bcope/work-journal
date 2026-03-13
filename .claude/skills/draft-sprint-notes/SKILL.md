---
name: draft-sprint-notes
description: Draft sprint notes for a specific sprint from collected Jira, GitHub, git, Claude Code, and enrichment data. Use when the user says "draft sprint notes", "draft notes", "/draft-sprint-notes", or asks to write up what happened in a sprint. Requires collect.py to have been run first.
---

# Draft Sprint Notes

Generate a polished sprint notes document from collected data. The user will specify a sprint directory name (e.g., `2026-02-A`) that corresponds to a directory under `work/sprint-notes/`.

## Prerequisites

Before running this skill, the user should have:

1. Collected data using `src/work_journal/collect.py` (at minimum, `jira/sprint-info.json` and some Jira query results)
2. Optionally run `/enrich-sprint-data {sprint}` to gather Gmail, Calendar, Google Docs, and Jira comment context

GitHub data, git commits, Claude Code sessions, manual notes, and enrichment output are all optional but improve the draft significantly.

## Process

### Phase 1: Load collected data

Read the following files from `work/sprint-notes/{sprint}/`:

1. **`jira/sprint-info.json`** -- Sprint metadata (name, start date, end date).
2. **Jira issue files** -- categorized by how work entered the sprint:
   - `jira/sprint-planned-completed.json` -- Issues in the sprint at start, completed. Delivered commitments.
   - `jira/sprint-planned-incomplete.json` -- Issues in the sprint at start, not completed. Look for why (blocked? descoped? carried over?).
   - `jira/sprint-added-completed.json` -- Issues added after sprint start, completed. Shows responsiveness.
   - `jira/sprint-added-incomplete.json` -- Issues added after sprint start, not completed.
   - `jira/non-sprint-completed.json` -- Work completed in the date range but never in this sprint. Operational/ad-hoc work.
   - `jira/non-sprint-incomplete.json` -- Work touched in the date range but never in the sprint, still open.
   - `jira/non-sprint-non-assigned-with-worklog.json` -- Issues not assigned to user but with worklogs by user.
3. **`github/prs.md`** -- GitHub PR activity (authored and reviewed). Optional.
4. **`git/commit-log.md`** -- Local git commits. Optional.
5. **`claude-code/sessions.md`** -- Claude Code session activity during the sprint, broken down by project. Shows which repos were worked on, session counts, tool usage, and files created/modified. Useful for understanding effort distribution and identifying work not captured in Jira. Optional.
6. **`manual-notes.md`** -- User-curated notes (Slack links, email summaries, meeting notes). Optional.

If a file is missing, note it and continue with available data.

**The Jira JSON files are often too large to read directly** (70k+ tokens each). Use a Python one-liner via Bash to extract key fields:

```bash
uv run python3 -c "
import json, re
for fname, label in [
    ('jira/sprint-planned-completed.json', 'planned-completed'),
    ('jira/sprint-planned-incomplete.json', 'planned-incomplete'),
    ('jira/sprint-added-completed.json', 'added-completed'),
    ('jira/sprint-added-incomplete.json', 'added-incomplete'),
    ('jira/non-sprint-completed.json', 'non-sprint-completed'),
    ('jira/non-sprint-incomplete.json', 'non-sprint-incomplete'),
    ('jira/non-sprint-non-assigned-with-worklog.json', 'non-sprint-worklog'),
]:
    with open(fname) as f:
        issues = json.load(f)
    print(f'=== {label} ({len(issues)} issues) ===')
    for i in issues:
        fields = i.get('fields', {})
        key = i.get('key', '?')
        summary = fields.get('summary', '?')
        priority = (fields.get('priority') or {}).get('name', '?')
        itype = (fields.get('issuetype') or {}).get('name', '?')
        reporter = (fields.get('reporter') or {}).get('displayName', '?')
        status = (fields.get('status') or {}).get('name', '?')
        print(f'  {key}: [{itype}/{priority}] {summary} (status: {status}, reporter: {reporter})')
    print()
"
```

Run this from the sprint directory (`work/sprint-notes/{sprint}/`).

### Phase 2: Read enrichment data

If `/enrich-sprint-data` was run, read the enrichment output files:

0. **`enrichment-summary.md`** -- Read this first. Check the Coverage Assessment for each source. If a source has `low` or `none` coverage, keep that in mind -- you will need to add TODO markers in the draft where that source would have provided context.
1. **`email/highlights.md`** -- Key email threads with decisions, requests, and stakeholder context. Explains *why* work happened.
2. **`calendar/events.md`** -- Meeting activity. Non-recurring events are high signal. Attendee cross-references show collaboration patterns.
3. **`google-docs/doc-summaries.md`** -- Documents modified during the sprint. Connects Jira issues to the analysis that explains *why the work mattered*.
4. **`jira/issue-details.md`** -- Comments and deeper context on key issues. Impact metrics, decision rationale, stakeholder context.
5. **`prior-sprint/continuity.md`** -- Carryover themes, incomplete work from the prior sprint, and prior metrics useful for showing progress over time.

If enrichment files don't exist, proceed with available data. The draft will have more `TODO` markers but is still useful.

**Fallback:** If enrichment was not run and you need specific context for a key accomplishment, make targeted MCP calls (e.g., `mcp__jira__get_comments` for a single critical issue). But prefer running the full enrichment skill first.

### Phase 3: Analyze and categorize

#### Understand the sprint narrative

- **Planned work** (planned-completed + planned-incomplete): What was committed to? What was delivered vs. carried over?
- **Added work** (added-completed + added-incomplete): What emerged after sprint start? Who requested it and why?
- **Non-sprint work** (non-sprint-completed + non-sprint-incomplete + non-sprint-worklog): What happened outside the formal sprint? These often contain hidden accomplishments.

#### Map to project themes

Map Jira project keys to readable names (from `config.yaml` `project_names`). Group issues, PRs, and commits under project themes. If work spans multiple projects but serves a single initiative, group by initiative instead.

#### Identify key accomplishments

Work that deserves a headline (H3) should meet one or more criteria:

- Produced measurable outcomes (before/after metrics, time savings, error reductions)
- Completed a milestone or deliverable
- Created a document that informed a decision
- Resolved a complex or high-priority problem
- Introduced a novel tool, process, or approach

Key accomplishments can come from any category. Added and non-sprint work often contains the most compelling narrative because it shows initiative and responsiveness.

#### Separate routine work

Brief mentions, not headlines: recurring operational tasks, small bug fixes, standard code reviews, routine maintenance.

#### Find quantifiable impact

Look for metrics in issue descriptions/comments, Google Docs, PR descriptions, and manual notes. Use specific numbers when available. Prefer "75% reduction" over "significant improvement."

#### Cross-reference sources

For each accomplishment, collect all relevant links:

- Jira issue URL: `$JIRA_URL/browse/{KEY}` (JIRA_URL is set in `.env`)
- Google Doc URL (from search results or manual notes)
- GitHub PR URL (from `prs.md`)
- Slack links (from `manual-notes.md`)

### Phase 4: Draft

Write the sprint notes document following this structure:

```markdown
# YYYY-MM-[A|B] - Sprint Notes & Demo - Shared

**Prior Sprint:** [YYYY-MM-[A|B] - Sprint Notes & Demo - Shared](LINK_IF_AVAILABLE)

## **Project/Theme Name**

### **Action-oriented headline with quantified impact**

Narrative paragraph (2-4 sentences, first person). Describe what was done, why it matters,
and what the outcome was. Embed links to Jira issues, Google Docs, GitHub PRs, and Slack
messages inline.

### **Another accomplishment**

...

## **Another Project/Theme**

...
```

#### Writing guidelines

- **Headlines (H3):** Start with an action verb or outcome. Include numbers when available. Example: "75% reduction to time spent on FXecute repair queue"
- **Narrative:** Write in first person. Keep paragraphs to 2-4 sentences. Lead with the outcome, then explain the approach.
- **Links:** Embed inline -- `[descriptive text](url)`. Don't dump bare URLs.
- **TODO markers:** If information is incomplete, add `TODO: description` so the user knows what to fill in.
- **Enrichment gaps:** If `enrichment-summary.md` shows `low` or `none` coverage for a source, add `TODO: [source] enrichment had low coverage -- verify this manually` next to any accomplishment where that source would have provided supporting context (e.g., email decisions, meeting attendees, doc analysis).
- **Tone:** Professional but not stiff. This is for sharing with a manager and team.

#### Save the output

Save the draft to `work/sprint-notes/{sprint}/draft.md`.

## Directory structure

```
work/sprint-notes/
  {sprint}/
    jira/
      sprint-info.json                          # Sprint metadata (dates, ID)
      sprint-planned-completed.json             # Planned work, completed
      sprint-planned-incomplete.json            # Planned work, not completed
      sprint-added-completed.json               # Added mid-sprint, completed
      sprint-added-incomplete.json              # Added mid-sprint, not completed
      non-sprint-completed.json                 # Outside sprint, completed
      non-sprint-incomplete.json                # Outside sprint, still open
      non-sprint-non-assigned-with-worklog.json # Worklogs on others' issues
      issue-details.md                          # Jira enrichment (from /enrich-sprint-data)
    github/
      prs.md                                    # GitHub PR activity
    git/
      commit-log.md                             # Local git commits
    claude-code/
      sessions.md                               # Claude Code session activity
    email/
      highlights.md                             # Gmail enrichment (from /enrich-sprint-data)
    calendar/
      events.md                                 # Calendar enrichment (from /enrich-sprint-data)
    google-docs/
      doc-summaries.md                          # Google Docs enrichment (from /enrich-sprint-data)
    prior-sprint/
      continuity.md                             # Prior sprint carryover (from /enrich-sprint-data)
    manual-notes.md                             # User-curated
    enrichment-summary.md                       # Enrichment quality/coverage (from /enrich-sprint-data)
    draft.md                                    # Output of this skill
```

## Tips

- Run `/enrich-sprint-data {sprint}` before this skill. Enrichment makes the draft significantly better.
- The most impactful sprint notes come from cross-referencing Jira issues with Google Docs. A Jira issue shows *what* was done; a memo or analysis doc shows *why it mattered*.
- When in doubt about whether something is a "key accomplishment" vs "routine work," consider: would you mention this in a quarterly progress brief? If yes, it's a key accomplishment.
- Sprint notes from `work/progress-briefs/2025-Q4/docs/` provide a good reference for tone and structure.
- If the Jira data shows many issues in a project but the user's manual notes don't mention it, ask before elevating it to a headline -- it may be routine work.
- If you need to re-draft without re-enriching, just run this skill again -- it reads the saved enrichment files rather than re-fetching via MCP.
- After the draft is finalized, use `/upload-sprint-notes {sprint}` to upload to Google Docs with company styles applied.
