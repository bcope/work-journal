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
- `src/work_journal/config.py` — Shared config loading with env var resolution
- `src/work_journal/scaffold.py` — Config-driven directory scaffolding
- `src/work_journal/collect.py` — Main orchestrator: reads config, resolves sprint dates via Jira API, runs all collection steps
- `src/work_journal/jira/` — Jira API queries and CSV parsing
- `src/work_journal/github/` — GitHub PR queries
- `src/work_journal/git/` — Local git log queries
- `src/work_journal/calendar/` — Google Calendar event queries
- `src/work_journal/claude_code/` — Claude Code activity collection
- `src/work_journal/collect_project_status.py` — Project status data collection (GitHub, Jira, Calendar)
- `tests/` — Test suite
- `work/sprint-notes/` — Sprint note data and drafts. Each sprint is a subdirectory (e.g., `2026-02-A/`).
- `work/sprint-notes/config.yaml` — Repo-level config (Jira settings, JQL templates, GitHub/git settings, project name mappings). JQL templates use `{account_id}`, `{start_date}`, `{end_date}`, `{sprint_id}` placeholders.
- `work/sprint-notes/{sprint}/sprint.yaml` — Sprint-level config (just the `sprint_name` field)
- `work/project-status/` — Project status update data and drafts
- `work/project-status/config.yaml` — Repo-level config for project status updates
- `work/project-status/project-configs/` — Per-project config files (e.g., `ggdisburse.yaml`)
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

The canonical source for this mapping is `work/sprint-notes/config.yaml` under `project_names`.

## Sprint notes workflow

1. Scaffold sprint directory: `uv run python3 src/work_journal/scaffold.py sprint {sprint} --var sprint_name="{jira-sprint-name}"`
2. Collect data: `uv run python3 src/work_journal/collect.py {sprint}`
3. Optionally edit `work/sprint-notes/{sprint}/manual-notes.md`
4. Enrich via MCP: `/enrich-sprint-data {sprint}` (Gmail, Calendar, Google Docs, Jira comments)
5. Draft via skill: `/draft-sprint-notes {sprint}`
6. Upload to Google Docs: `/upload-sprint-notes {sprint}`

Steps 3 and 4 are optional but significantly improve draft quality. Step 4 saves its output to files, so re-drafting (step 5) doesn't re-fetch MCP data.

## Project status updates workflow

1. Create project config: `cp work/project-status/project-configs/example.yaml work/project-status/project-configs/{project}.yaml`
2. Edit the project config with repos, JQL queries, calendar settings
3. Collect data: `uv run python3 src/work_journal/collect_project_status.py {project} --since YYYY-MM-DD`
4. Draft via skill: `/project-status {project} --since YYYY-MM-DD --audience slt`
5. Edit `work/project-status/{project}/{date}/draft.md`
6. Upload to Google Docs via `md-to-gdoc.js`

Overview mode (no dates): omit `--since` to get a general status based on the
project's `default_days` setting. Calendar collection is skipped in this mode.

## Uploading to Google Docs

The `md-to-gdoc.js` script converts markdown to styled Google Docs. The script path and target Drive folder are configured in `work/sprint-notes/config.yaml` under `google_drive` (resolved from env vars).

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
