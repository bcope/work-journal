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
2. **`jira/prior-sprint-info.json`** -- Prior sprint metadata (name, dates, completeDate). Used to identify the between-sprints gap period. Optional.
3. **Jira issue files** -- categorized by how work entered the sprint:
   - `jira/sprint-planned-completed.json` -- Issues in the sprint at start, completed. Delivered commitments.
   - `jira/sprint-planned-incomplete.json` -- Issues in the sprint at start, not completed. Look for why (blocked? descoped? carried over?).
   - `jira/sprint-added-completed.json` -- Issues added after sprint start, completed. Shows responsiveness.
   - `jira/sprint-added-incomplete.json` -- Issues added after sprint start, not completed.
   - `jira/between-sprints-completed.json` -- Issues resolved between the previous sprint close and this sprint's start. Work that happened in the gap.
   - `jira/non-sprint-completed.json` -- Work completed in the date range but never in this sprint. Operational/ad-hoc work.
   - `jira/non-sprint-incomplete.json` -- Work touched in the date range but never in the sprint, still open.
   - `jira/non-sprint-non-assigned-with-worklog.json` -- Issues not assigned to user but with worklogs by user.
4. **Sprint-period activity files:**
   - `github/prs.md` -- GitHub PR activity (authored and reviewed). Optional.
   - `git/commit-log.md` -- Local git commits. Optional.
   - `claude-code/sessions.md` -- Claude Code session activity. Optional.
5. **Between-sprints activity files** (gap between prior sprint close and this sprint start):
   - `github/between-sprints-prs.md` -- PRs merged in the gap. Optional.
   - `git/between-sprints-commit-log.md` -- Commits in the gap. Optional.
   - `claude-code/between-sprints-sessions.md` -- Claude Code sessions in the gap. Optional.
6. **`manual-notes.md`** -- User-curated notes (Slack links, email summaries, meeting notes). Optional.
7. **`daily-log/merged-edited.md`** -- **Required.** The merged daily log: the primary record of what actually happened per day. If it is missing, stop and tell the user to run `uv run python3 src/work_journal/daily_log.py {sprint}` and then `/merge-daily-log {sprint}` first. **Exemption:** sprints before 2026-07-A predate daily notes — proceed without it.

   Other sources (Jira, GitHub, git, Claude Code) corroborate the daily log and add links and metrics. When sources conflict, the daily log wins and the disagreement gets a `TODO:` marker in the draft. Never read `merged-raw.md` — it exists only for diffing against the edited copy.
8. **Claude Code insights** -- one or more cleaned files in
   `work/shared/insights/cleaned/` whose date range overlaps the sprint period.
   Files are named `{start}-to-{end}.md`. Find candidates by reading the
   sprint date range from `jira/sprint-info.json` and listing cleaned files
   whose `[start, end]` overlaps the sprint dates.

   **Important framing:** The /insights tool reports on a rolling 30-day window,
   so the cleaned file typically covers more than a single sprint -- it may
   span the prior sprint and part of the next one. Use the cleaned insights as
   **commentary on working patterns and productivity** (informing the
   Developer Tooling / AI Toolkit narrative paragraphs and any retrospective
   commentary). **Do not** use insights items as primary accomplishment
   headlines -- the actual accomplishments come from sprint-scoped sources
   (Jira, GitHub, git, and `claude-code/sessions.md`, all of which are
   strictly date-filtered to this sprint).

   If no overlapping insights file exists, proceed without one and note the
   gap in the draft.

If a file is missing, note it and continue with available data.

**The Jira JSON files are often too large to read directly** (70k+ tokens each). Use a Python one-liner via Bash to extract key fields:

```bash
uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/{sprint}
```

### Phase 2: Read enrichment data

If `/enrich-sprint-data` was run, read the enrichment output files:

0. **`enrichment-summary.md`** -- Read this first. Check the Coverage Assessment for each source. If a source has `low` or `none` coverage, keep that in mind -- you will need to add TODO markers in the draft where that source would have provided context.
1. **`email/highlights.md`** -- Key email threads with decisions, requests, and stakeholder context. Explains *why* work happened.
2. **`calendar/events.md`** -- Meeting activity. Non-recurring events are high signal. Attendee cross-references show collaboration patterns.
3. **`google-docs/doc-summaries.md`** -- Documents created in (or explicitly referenced from) the sprint, with summaries. Connects Jira issues to the analysis that explains *why the work mattered*.
4. **`jira/issue-details.md`** -- Comments and deeper context on key issues. Impact metrics, decision rationale, stakeholder context.
5. **`prior-sprint/continuity.md`** -- Carryover themes, incomplete work from the prior sprint, and prior metrics useful for showing progress over time.

If enrichment files don't exist, pause and ask the user whether to proceed without enrichment. Recommend running `/enrich-sprint-data {sprint}` first — the draft is significantly better with it.

**Do not** read `google-docs/modified-not-created.md`. That file is an audit list of documents touched during the sprint window but created earlier — most of which represent prior work whose `modifiedTime` was bumped by a permission tweak, an open-with-autosave, or a collaborator's edit. The user reviews that list manually and folds any genuine sprint-period work into `doc-summaries.md` before drafting. If `doc-summaries.md` is missing or thin and you need more Google Docs context, surface that as a TODO rather than pulling from `modified-not-created.md`.

**Fallback:** If enrichment was not run and you need specific context for a key accomplishment, make targeted MCP calls (e.g., `mcp__jira__get_comments` for a single critical issue). But prefer running the full enrichment skill first.

### Phase 3: Analyze and categorize

#### Understand the sprint narrative

- **Between-sprints work** (between-sprints-completed + between-sprints PRs/commits/Claude Code): What happened in the gap between the prior sprint close and this sprint start? This work would otherwise be invisible. Treat it as its own section in the draft, similar to non-sprint work.
- **Planned work** (planned-completed + planned-incomplete): What was committed to? What was delivered vs. carried over?
- **Added work** (added-completed + added-incomplete): What emerged after sprint start? Who requested it and why?
- **Non-sprint work** (non-sprint-completed + non-sprint-incomplete + non-sprint-worklog): What happened outside the formal sprint? These often contain hidden accomplishments.

#### Map to project themes

Map Jira project keys to readable names (from `config/shared.yaml` `project_names`). Group issues, PRs, and commits under project themes. If work spans multiple projects but serves a single initiative, group by initiative instead.

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
- **No LLM signatures.** The draft should read like Barrett wrote it, not like a model did. Specifically:
  - **No em dashes (—).** Use a period, comma, colon, semicolon, or parentheses instead — whichever the sentence actually calls for. En dashes in date ranges (`7/14 – 7/15`) are fine.
  - No "X — Y" reframing pivots or "It's not X, it's Y" / "not just X but Y" contrast constructions.
  - No cleft flourishes like "That's what converted...", "What this means is...", "The key insight is...".
  - No "X rather than Y" more than once or twice per document; vary the construction.
  - Don't bold single words or dates mid-sentence for emphasis. Bold is only for the metric phrases the doc series already uses (e.g., **67 rcptitems**) and headline conventions.
  - Skip the stock vocabulary: "delve", "leverage", "robust", "seamless", "comprehensive", "crucial", "landscape", "streamline".
  - Don't close sections with tidy summary sentences that restate what the section just said.
  - Prefer plain sentences over stacked appositives; if a sentence needs three clauses hung off it, split it.

#### Save the output

Save the draft to `work/sprint-notes/{sprint}/draft.md`.

### Phase 5: Annotations and impact metrics

After saving the draft, produce two structured outputs that feed the quarterly progress brief pipeline.

#### 5a: Business value annotations

Create `work/sprint-notes/{sprint}/annotations.yaml` with one entry per H3 accomplishment in the draft. Reference the value category vocabulary from `config/shared.yaml` under `value_categories`.

```yaml
sprint: "2026-03-B"
accomplishments:
  - headline: "Automated the GG-driven redesignation workflow end-to-end"
    project: Compliance
    value_categories: [process_efficiency, risk_reduction]
    summary: >
      Built complete automation pipeline for monthly redesignation,
      eliminating manual work across Google Sheets, Salesforce, and database.
    jira_keys: [COMPLY-697, COMPLY-698]
```

Each entry should have:

- `headline` -- the H3 text from the draft
- `project` -- the readable project name (from `config/shared.yaml` `project_names`)
- `value_categories` -- one or more categories from the vocabulary that describe the business value
- `summary` -- one sentence capturing why this work mattered (business outcome, not technical description)
- `jira_keys` -- list of Jira issue keys associated with this accomplishment (empty list if none)

Do not annotate routine work (brief mentions that don't have their own H3). Only annotate key accomplishments.

#### 5b: Impact metrics extraction

Scan the draft for quantified outcomes: percentages, dollar amounts, time savings, counts, before/after comparisons. For each, append an entry to the quarter's impact metrics file.

Determine the quarter from the sprint name: months 1-3 = Q1, 4-6 = Q2, 7-9 = Q3, 10-12 = Q4. The file location is `work/progress-briefs/{YEAR}-{QUARTER}/impact-metrics.yaml`.

If the file does not exist, create it with a `metrics: []` key first, then append. If it already has entries, read it, append the new entries, and write it back. Do not duplicate entries from the same sprint -- if entries for this sprint already exist, replace them.

```yaml
metrics:
  - sprint: "2026-03-B"
    project: Compliance
    headline: "Automated the GG-driven redesignation workflow end-to-end"
    metric: "13 commits across 5 Claude Code sessions (~2h 10m thinking time)"
    type: count
  - sprint: "2026-03-B"
    project: Upkeep
    headline: "GGSP shared drive audit: 98,165 files, 183.5 GB"
    metric: "76% of files haven't been modified since 2022"
    type: percentage
    value: "76%"
```

Metric types: `percentage`, `dollar_amount`, `time_savings`, `count`, `data_point`.

Include a `value` field when the metric has a single clear numeric value. Omit it for composite or descriptive metrics.

If no quantified outcomes are found in the draft, skip this step (not every sprint will have impact metrics).

If the progress brief directory for the quarter does not exist yet, skip this step and note it in the output -- the user can run `scaffold.py progress-brief` later.

## Directory structure

```
work/sprint-notes/
  {sprint}/
    jira/
      sprint-info.json                          # Sprint metadata (dates, ID)
      prior-sprint-info.json                    # Prior sprint metadata (for gap period)
      between-sprints-completed.json            # Work done in gap between sprints
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
      between-sprints-prs.md                    # PRs merged in the gap between sprints
    git/
      commit-log.md                             # Local git commits
      between-sprints-commit-log.md             # Commits in the gap between sprints
    claude-code/
      sessions.md                               # Claude Code session activity
      between-sprints-sessions.md               # Claude Code in the gap between sprints
    email/
      highlights.md                             # Gmail enrichment (from /enrich-sprint-data)
    calendar/
      events.md                                 # Calendar enrichment (from /enrich-sprint-data)
    google-docs/
      doc-summaries.md                          # Google Docs enrichment (from /enrich-sprint-data)
      modified-not-created.md                   # Audit list of touched-but-not-created docs (NOT loaded by this skill)
    prior-sprint/
      continuity.md                             # Prior sprint carryover (from /enrich-sprint-data)
    daily-log/
      raw/
        daily-notes/                            # Snapshotted daily notes (from daily_log.py)
        standups/                               # Standup completed-work extracts (from daily_log.py)
      merged-raw.md                             # Merge output; never hand-edited, never read here
      merged-edited.md                          # Editable merged log; required input for this skill
    manual-notes.md                             # User-curated
    enrichment-summary.md                       # Enrichment quality/coverage (from /enrich-sprint-data)
    draft.md                                    # Output of this skill
    annotations.yaml                            # Business value annotations (from Phase 5)
```

## Tips

- Run `/enrich-sprint-data {sprint}` before this skill. Enrichment makes the draft significantly better.
- The most impactful sprint notes come from cross-referencing Jira issues with Google Docs. A Jira issue shows *what* was done; a memo or analysis doc shows *why it mattered*.
- When in doubt about whether something is a "key accomplishment" vs "routine work," consider: would you mention this in a quarterly progress brief? If yes, it's a key accomplishment.
- Sprint notes from `work/progress-briefs/2025-Q4/docs/` provide a good reference for tone and structure.
- If the Jira data shows many issues in a project but the user's manual notes don't mention it, ask before elevating it to a headline -- it may be routine work.
- If you need to re-draft without re-enriching, just run this skill again -- it reads the saved enrichment files rather than re-fetching via MCP.
- After the draft is finalized, use `/upload-sprint-notes {sprint}` to upload to Google Docs with company styles applied.
