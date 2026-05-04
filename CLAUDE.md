# Project: Work Journal

Tools and workflows for collecting work data and drafting sprint notes and progress briefs.

## Running Python

Always use `uv run python3` to run scripts. Use `uv add` to install dependencies.

```bash
uv run python3 src/work_journal/collect.py 2026-02-A
uv run python3 src/work_journal/jira/query_sprint_info.py --sprint-name "2026-02-A-Product-February"
```

## Development commands

```bash
uv run ruff check .           # Lint
uv run ruff format .          # Format
uv run mypy src/              # Type check
uv run pytest                 # Test
uv run pre-commit run --all-files  # All pre-commit hooks
```

## Key identifiers

- **Jira account ID:** Set via `JIRA_ACCOUNT_ID` env var (see `.env`)
- **Jira board ID:** Set via `JIRA_BOARD_ID` env var (see `.env`)
- **GitHub org:** Set via `GITHUB_ORG` env var (see `.env`)
- **Git author:** Set via `GIT_AUTHOR` env var (see `.env`)

The Jira API credentials (`JIRA_USER` / `JIRA_API_TOKEN`) authenticate as a generic API user, not bcope's personal account. JQL functions like `currentUser()` will not match bcope's issues — always use the explicit account ID from `JIRA_ACCOUNT_ID`.

## Project structure

- `src/work_journal/` — Python package (collection, queries, parsing)
- `src/work_journal/paths.py` — Centralized path constants (repo root, config path, work dirs)
- `src/work_journal/config.py` — Config loading with env var resolution (per-process loaders)
- `src/work_journal/scaffold.py` — Config-driven directory scaffolding
- `config/` — Configuration files (shared settings, per-process configs, project configs)
- `config/shared.yaml` — Shared settings (project name mappings, value categories, Google Drive script path, insights keywords)
- `config/sprint-notes.yaml` — Sprint notes collection config (JQL queries, output paths)
- `config/standup.yaml` — Standup notes config (JQL queries)
- `config/project-status.yaml` — Project status config (calendar, Google Drive)
- `config/project-configs/` — Per-project config files (e.g., `ggdisburse.yaml`)
- `templates/` — Scaffold templates for creating work directories
- `src/work_journal/collect.py` — Main orchestrator: reads config, resolves sprint dates via Jira API, runs all collection steps
- `src/work_journal/jira/` — Jira API queries and CSV parsing
- `src/work_journal/github/` — GitHub PR queries
- `src/work_journal/git/` — Local git log queries
- `src/work_journal/gcalendar/` — Google Calendar event queries
- `src/work_journal/claude_code/` — Claude Code activity collection
- `src/work_journal/insights/` — Claude Code insights report parsing and classification
- `src/work_journal/collect_project_status.py` — Project status data collection (GitHub, Jira, Calendar)
- `src/work_journal/collect_progress_brief.py` — Quarterly rollup collection (aggregates sprint data for progress briefs)
- `src/work_journal/quarters.py` — Quarter-sprint mapping utilities
- `tests/` — Test suite
- `work/sprint-notes/` — Sprint note data and drafts. Each sprint is a subdirectory (e.g., `2026-02-A/`).
- `work/sprint-notes/{sprint}/sprint.yaml` — Sprint-level config (just the `sprint_name` field)
- `work/shared/` — Cross-process inputs (insights reports)
- `work/shared/insights/raw/` — Raw HTML from Claude Code `/insights` command (any filename)
- `work/shared/insights/parsed/` — Classified JSON, named `{start}-to-{end}.json` (date range from the report)
- `work/shared/insights/cleaned/` — Final cleaned markdown, named `{start}-to-{end}.md`. Sprint and progress brief draft skills find files whose date range overlaps the sprint/quarter and treat them as pattern-level commentary, not accomplishment evidence.
- `work/project-status/` — Project status update data and drafts
- `work/progress-briefs/` — Quarterly progress brief artifacts (forms, Jira exports, authored docs, drafts)
- `work/okrs/` — OKR tracking
- `docs/` — Plans and design documents
- `.claude/skills/` — Claude Code skill definitions

## Jira project key mapping

These map Jira project keys to readable names used in sprint notes:

- COMPLY = "Compliance"
- DATA = "Data"
- BSR = "BSR"
- AGILE = "Agile"
- GGL = "GGL"
- VAST = "VAST"
- GGDM = "GGDisburse Migration"
- UPKEEP = "Upkeep"

The canonical source for this mapping is `config/shared.yaml` under `project_names`.

## Sprint notes workflow

1. Scaffold sprint directory: `uv run python3 src/work_journal/scaffold.py sprint {sprint} --var sprint_name="{jira-sprint-name}"`
2. Prepare insights report (collect.py gates on this — needs at least one cleaned report whose date range overlaps the sprint):
   a. Run `/insights` in Claude Code (covers a rolling 30-day window)
   b. Copy the HTML to `work/shared/insights/raw/` (any filename — the date range is read from the report itself)
   c. Parse: `uv run python3 src/work_journal/insights/cli.py <raw-filename>` (writes `parsed/{start}-to-{end}.json`)
   d. Clean: `/clean-insights {start}-to-{end}` (writes `cleaned/{start}-to-{end}.md`)
3. Collect data: `uv run python3 src/work_journal/collect.py {sprint}`
4. Optionally edit `work/sprint-notes/{sprint}/manual-notes.md`
5. Enrich via MCP: `/enrich-sprint-data {sprint}` (Gmail, Calendar, Google Docs, Jira comments)
6. Draft via skill: `/draft-sprint-notes {sprint}`
7. Upload to Google Docs: `/upload-sprint-notes {sprint}`

Steps 4 and 5 are optional but significantly improve draft quality. Step 5 saves its output to files, so re-drafting (step 6) doesn't re-fetch MCP data.

Step 6 also produces `annotations.yaml` (business value tags per accomplishment) and appends impact metrics to the quarter's `impact-metrics.yaml`. These feed the progress brief pipeline.

## Progress brief workflow

1. Scaffold: `uv run python3 src/work_journal/scaffold.py progress-brief {YEAR}-{QUARTER}`
2. (Sprint notes should already exist from the sprint workflow above, including annotations and impact metrics)
3. Collect rollup: `uv run python3 src/work_journal/collect_progress_brief.py {YEAR}-{QUARTER}`
4. Copy form PDFs to `work/progress-briefs/{YEAR}-{QUARTER}/format/`
5. Optionally add supplementary docs to `docs/`
6. Draft: `/draft-progress-brief {YEAR}-{QUARTER}`
7. Edit and finalize

The rollup script aggregates sprint notes, annotations, Jira issue counts, PR counts, Claude Code stats, and enrichment highlights into a single `rollup.md` that serves as the primary input for drafting.

## Project status updates workflow

1. Create project config: `cp config/project-configs/example.yaml config/project-configs/{project}.yaml`
2. Edit the project config with repos, JQL queries, calendar settings
3. Collect data: `uv run python3 src/work_journal/collect_project_status.py {project} --since YYYY-MM-DD`
4. Draft via skill: `/project-status {project} --since YYYY-MM-DD --audience slt`
5. Edit `work/project-status/{project}/{date}/draft.md`
6. Upload to Google Docs via `md-to-gdoc.js`

Overview mode (no dates): omit `--since` to get a general status based on the
project's `default_days` setting. Calendar collection is skipped in this mode.

## Uploading to Google Docs

The `md-to-gdoc.js` script converts markdown to styled Google Docs. The script path is configured in `config/shared.yaml` under `google_drive.md_to_gdoc_script`. The target Drive folder is configured per-process: in `config/sprint-notes.yaml` under `google_drive.upload_folder` for sprint notes, and in each project config file (e.g., `config/project-configs/ggdisburse.yaml`) under `google_drive.upload_folder` for project status updates.

```bash
node $MD_TO_GDOC_SCRIPT upload <file.md> \
  --title "Doc Title" \
  --folder "$SPRINT_NOTES_FOLDER"
```

The `--folder` flag accepts a Google Drive folder URL or bare folder ID.

## MCP servers used by skills

- **Google Docs / Drive / Sheets** — searching for documents modified during a sprint, reading doc content and comments, reading spreadsheet data
- **Gmail** — searching sent mail and stakeholder threads for decisions, requests, and collaboration context
- **Calendar** — listing events in the sprint date range, identifying non-recurring meetings and collaboration patterns
- **Jira** — fetching issue details and comments for key accomplishments during enrichment

## Google Drive search tips

When searching for docs owned by the user in a date range, use the query format with the email from `OWNER_EMAIL` env var:

```text
owner:{OWNER_EMAIL} after:YYYY-MM-DD before:YYYY-MM-DD
```

Google Sheets API and Google Drive API must both be enabled for spreadsheet reading to work.
