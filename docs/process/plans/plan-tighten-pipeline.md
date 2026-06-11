# Plan: Tighten Data Collection and Create Explicit Analysis Skills

## Part 1: Data collection improvements

### 1.1 Two-tier config: repo-level and sprint-level

Most collection parameters are constant across sprints. Only the sprint name
varies. The config is split accordingly.

**Repo-level config** (`work/sprint-notes/config.yaml`) — set once, rarely changes:

```yaml
jira:
  account_id: "${JIRA_ACCOUNT_ID}"
  board_id: "${JIRA_BOARD_ID}"
  queries:
    assigned_issues:
      jql: "assignee = '{account_id}' AND updated >= '{start_date}' AND updated <= '{end_date}'"
      output: "jira/assigned-issues.json"
    sprint_issues:
      jql: "sprint = {sprint_id}"
      output: "jira/sprint-issues.json"
github:
  org: "${GITHUB_ORG}"
  output: "github/prs.md"
  format: markdown
git:
  repos_dir: "${GIT_REPOS_DIR}"
  author: "${GIT_AUTHOR}"
  output: "git/commit-log.md"
project_names:
  COMPLY: "CA AB 488"
  GGDISB: "GGDisburse"
  GGDASH: "GGDashboard"
  GGSITE: "GGSite"
  DEVOPS: "DevOps"
  DATA: "Data"
  BSR: "BSR"
  AGILE: "Agile"
  GGL: "GGL"
  VAST: "VAST"
```

**Sprint-level config** (`work/sprint-notes/{sprint}/sprint.yaml`) — one field:

```yaml
sprint_name: "2026-02-A-Product-February"
```

Optionally, a sprint can override any repo-level setting (e.g., a different board
or an extra JQL query). But the default case is just the sprint name.

The collect script:

1. Reads `work/sprint-notes/config.yaml` for repo defaults
2. Reads `work/sprint-notes/{sprint}/sprint.yaml` for the sprint name
3. Calls `query_sprint_info.py` to resolve the sprint name to dates and ID
4. Templates the JQL queries with `{account_id}`, `{start_date}`, `{end_date}`,
   `{sprint_id}` from the resolved sprint info
5. Runs each query and writes output to the configured filename
6. Runs GitHub and git collection with the derived dates
7. Reports what was collected

### 1.2 Smarter Jira issue collection

The repo-level config supports multiple named JQL queries. The default set:

- `assigned_issues` — issues assigned to the user, updated in the date range
  (the "my work" view)
- `sprint_issues` — all issues in the sprint regardless of assignment (the
  "sprint scope" view)

Future additions could include:

- `commented_issues` — issues the user commented on but isn't assigned to
- `worklog_issues` — issues where the user logged time

Each query has a configurable output filename, so adding a new query is just
adding a block to the YAML — no code changes needed.

### 1.3 Richer GitHub PR data

**Problem:** `gh search prs` returns limited metadata. No PR body, review
comments, or `mergedAt` field.

**Improvements:**

- After search, use `gh pr view {url} --json body,reviews,comments,mergedAt` for
  each PR to get full context. PR bodies often contain the best description of
  what changed and why.
- Extract Jira issue keys from PR titles/branches (the convention `COMPLY-632` in
  branch names) and cross-reference with the Jira data.
- Capture review comments authored (not just PRs reviewed) — these show engagement
  with other people's work.

### 1.4 Google Docs collection as a script (future, post-MCP-expansion)

Currently Google Docs enrichment happens interactively in the skill because it
requires judgment. Once the pattern is proven, consider:

- A helper script that searches Google Drive for docs owned by the user, modified
  in the date range, and saves a manifest (`google-docs/manifest.json`) with doc
  IDs, titles, URLs, modified dates, and sizes.
- The skill then reads the manifest and selectively fetches content for relevant
  docs instead of doing the search itself.
- This separates "what docs exist" (deterministic, scriptable) from "which docs
  matter" (requires judgment, belongs in the skill).

### 1.5 Gmail collection

Gmail tools are now available in the MCP server (`search_emails`, `read_email`).
The enrichment skill should use these during Phase 2:

- Search sent mail in the date range using
  `mcp__gdocs__search_emails` with `from:me after:YYYY/MM/DD before:YYYY/MM/DD`
- Search inbox for threads involving key stakeholders (derived from Jira issue
  reporters/commenters) using `from:stakeholder@example.com` queries
- Read relevant threads with `mcp__gdocs__read_email` and extract decisions,
  requests, and context
- Save highlights to `email/highlights.md`

### 1.6 Calendar collection

Calendar tools are now available in the MCP server (`list_events`,
`search_events`, `get_event`).

- List events in the date range using `mcp__gdocs__list_events` with `timeMin`
  and `timeMax` in RFC3339 format
- Flag non-recurring events (higher signal)
- Search for project-specific meetings with `mcp__gdocs__search_events`
- Cross-reference attendee names with Jira issue reporters/assignees
- Save event summary to `calendar/events.md`

## Part 2: Explicit analysis skills

The current `draft-sprint-notes.md` skill is a monolith that does everything:
load, enrich, analyze, and draft. Breaking it into focused skills improves
reusability and lets Claude apply more attention to each step.

### 2.1 Skill: Classify sprint work

**File:** `.claude/skills/classify-sprint-work.md`

**Purpose:** Takes the raw collected data and produces a structured classification
before any writing happens.

**Input:** Sprint directory path

**Output:** `work/sprint-notes/{sprint}/analysis/classification.md`

**Process:**

1. Read all collected data files
2. Read `work/sprint-notes/config.yaml` for project name mappings
3. For each Jira issue, classify as:
   - **Key accomplishment** — meets headline criteria (measurable outcome,
     milestone, decision-informing document, complex problem solved, novel approach)
   - **Notable work** — meaningful but not headline-worthy (medium-complexity tasks,
     incremental progress on larger initiatives)
   - **Routine** — recurring tasks, small fixes, time tracking, admin
   - **Background/support** — code reviews, meetings, helping others
4. For each key accomplishment, identify:
   - Related Jira issues (may span multiple)
   - Related PRs (from GitHub data, matched by Jira key in title/branch)
   - Related commits (from git data, matched by Jira key)
   - Related Google Docs (from search results or Jira descriptions)
   - Stakeholders involved (from Jira comments, email if available)
   - Quantifiable impact (from any source)
5. Group by project/theme using config mappings, with cross-project initiatives
   grouped together
6. Flag gaps: "COMPLY-632 looks important but has no linked Google Doc — check
   if a memo exists"

**Why separate:** Classification is the hardest analytical step. Doing it
explicitly and saving the output means you can review and adjust the
classification before drafting. It also means the drafting skill gets cleaner
input.

### 2.2 Skill: Enrich sprint data via MCP

**File:** `.claude/skills/enrich-sprint-data.md`

**Purpose:** Takes the classification and fills in gaps using MCP tools.

**Input:** Sprint directory with `analysis/classification.md`

**Output:** Updated `analysis/classification.md` with enrichment notes, plus
any new files (e.g., `google-docs/doc-summaries.md`)

**Process:**

1. Read the classification
2. For each key accomplishment:
   - Fetch Jira comments (`mcp__jira__get_comments`) — look for impact metrics,
     stakeholder context, decision rationale
   - If Google Docs are linked in Jira descriptions, read them and extract
     relevant sections
   - If spreadsheets are linked, read them for quantitative data
3. Search Google Drive for docs owned by user in the date range
   - For each result, assess relevance by checking if title/content relates to
     any classified accomplishment
   - Read and summarize relevant docs
4. Check for prior sprint notes for continuity context
5. Annotate the classification with everything found

**Why separate:** MCP enrichment is slow (many API calls) and interactive (some
docs may not be relevant). Separating it lets you run enrichment once, review
what was found, and then draft without re-fetching.

### 2.3 Skill: Draft sprint notes (simplified)

**File:** Update existing `.claude/skills/draft-sprint-notes.md`

**Purpose:** Takes an enriched classification and writes the sprint notes.

**Input:** Sprint directory with `analysis/classification.md` (enriched)

**Output:** `work/sprint-notes/{sprint}/draft.md`

**Process:** Pure writing — no data fetching, no classification decisions. The
skill reads the enriched classification and writes narrative prose following the
established format and tone guidelines.

**Why simplify:** The current skill tries to do everything in one pass, which
means if the writing isn't right you have to re-run the entire enrichment. With
the split, you can iterate on the draft without re-fetching data.

### 2.4 Skill: Review sprint notes draft

**File:** `.claude/skills/review-sprint-notes.md`

**Purpose:** Quality check on a draft before finalization.

**Input:** `work/sprint-notes/{sprint}/draft.md`

**Output:** Inline feedback or revised draft

**Process:**

1. Check structure: Does every H2 section have at least one H3? Are there empty
   sections?
2. Check links: Does every key accomplishment have at least one link (Jira, Doc,
   PR)? Flag any with zero links.
3. Check quantification: Are there headlines that claim impact without numbers?
   Flag for user to add evidence.
4. Check TODOs: List all remaining TODO markers.
5. Check tone: First person, professional, 2-4 sentence paragraphs.
6. Compare against prior sprint notes format for consistency.
7. Identify anything that looks like it belongs in the progress brief but isn't
   in the sprint notes (missed accomplishment).

### 2.5 Skill: Extract progress brief evidence

**File:** `.claude/skills/extract-brief-evidence.md`

**Purpose:** At end of quarter, scan all sprint notes in the quarter and produce
structured evidence for the progress brief skill.

**Input:** Quarter identifier (e.g., `2026-Q1`)

**Output:** `work/progress-briefs/2026-Q1/sprint-evidence.md`

**Process:**

1. Find all sprint directories in the quarter date range
2. Read each `draft.md` (or final version)
3. Extract and deduplicate: key accomplishments, quantified impacts, collaboration
   examples, challenges overcome, skills developed
4. Organize by progress brief form question (what's working, what isn't, where
   you need support)
5. Include links back to sprint notes for traceability

**Why:** This closes the loop between sprint notes and quarterly progress briefs.
The existing `draft-progress-brief.md` skill currently reads raw Jira CSVs and
docs. If sprint notes are well-structured, they become the primary input for
progress briefs — which is how they should work.

## Implementation order

| Step | Deliverable | Depends on | Effort |
|---|---|---|---|
| 1 | `config.yaml` + `collect.py` | Nothing | Small |
| 2 | `classify-sprint-work.md` skill | Dry run experience | Medium |
| 3 | `enrich-sprint-data.md` skill | Classification skill | Medium |
| 4 | Simplify `draft-sprint-notes.md` | Classification + enrichment skills | Small |
| 5 | Richer GitHub PR data in `query_github_prs.py` | Nothing | Small |
| 6 | `review-sprint-notes.md` skill | Draft skill | Small |
| 7 | `extract-brief-evidence.md` skill | At least one quarter of sprint notes | Medium |
| 8 | Gmail collection in enrichment skill | Enrichment skill | Small |
| 9 | Calendar collection in enrichment skill | Enrichment skill | Small |

Steps 1 and 5 are independent and can be done in parallel. Steps 2-4 should
be done in sequence. Steps 6 and 7 can wait until the core pipeline has been
used for a few sprints.

## Validation

- Run `collect.py` for the current sprint and confirm it produces identical output
  to the manual commands from the dry run
- Run the classification skill on 2026-02-A data and compare the output against
  the draft we already wrote — the classification should identify the same key
  accomplishments
- Run the full pipeline (collect -> classify -> enrich -> draft) for the next
  sprint (2026-02-B) and compare the time spent vs. the manual process
