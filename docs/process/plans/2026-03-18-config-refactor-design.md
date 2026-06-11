# Config refactor design

## Problem

`work/sprint-notes/config.yaml` serves too many purposes: identity/credentials,
sprint collection queries, standup queries, scaffold templates, project name
mappings, and Google Drive upload settings. `work/project-status/config.yaml`
duplicates some of those fields. Config is mixed in with output data in `work/`.

## Design

### New directory structure

```text
config/
  shared.yaml              # project_names, md_to_gdoc_script
  sprint-notes.yaml        # sprint JQL queries, output paths, google_drive.upload_folder
  project-status.yaml      # project-status google_drive.upload_folder, other settings
  standup.yaml             # standup JQL queries
  project-configs/         # per-project configs (ggdisburse.yaml, example.yaml, etc.)
templates/
  sprint.yaml              # scaffold template for sprint directories
  progress-brief.yaml      # scaffold template for progress-brief directories
work/                      # pure output, no config files
  sprint-notes/
  project-status/
  standup/
  progress-briefs/
```

### Identity fields move to env vars

These fields currently live in config yaml as `${ENV_VAR}` passthroughs and
will be read directly via `os.environ` in Python code:

- `JIRA_ACCOUNT_ID`
- `JIRA_BOARD_ID`
- `GITHUB_ORG`
- `GIT_REPOS_DIR`
- `GIT_AUTHOR`
- `OWNER_EMAIL`
- `CLAUDE_HISTORY_PATH`
- `CLAUDE_STATS_CACHE_PATH`
- `CLAUDE_PROJECTS_PATH`
- `CLAUDE_WORK_DIRS`

These are already in `.env` / `.env.example`. No new env vars needed.

### config/shared.yaml

Contains non-scalar shared settings that don't fit in env vars:

```yaml
project_names:
  COMPLY: "Compliance"
  DATA: "Data"
  BSR: "BSR"
  AGILE: "Agile"
  GGL: "GGL"
  VAST: "VAST"
  GGDM: "GGDisburse Migration"
  UPKEEP: "Upkeep"

google_drive:
  md_to_gdoc_script: "${MD_TO_GDOC_SCRIPT}"
```

### config/sprint-notes.yaml

Sprint collection queries and settings. No identity fields — those come from
env vars. JQL templates continue to use `{placeholder}` syntax for runtime
substitution.

```yaml
jira:
  queries:
    sprint_planned_completed:
      description: "Issues in the sprint at start that were completed"
      jql: "assignee = {account_id} AND sprint = {sprint_id} ..."
      output: "jira/sprint-planned-completed.json"
    # ... (all 7 existing sprint queries)

github:
  output: "github/prs.md"
  format: markdown

git:
  output: "git/commit-log.md"

gmail:
  queries:
    sent_mail:
      query: "from:me after:{start_date_slash} before:{end_date_slash}"
      output: "email/sent.md"
    # ...

calendar:
  calendar_id: primary
  output: "calendar/events.md"

claude_code:
  output: "claude-code/sessions.md"
  documents_output: "claude-code/documents.md"

google_drive:
  upload_folder: "${SPRINT_NOTES_FOLDER}"
```

### config/standup.yaml

```yaml
queries:
  completed_yesterday:
    jql: "assignee = {account_id} AND updated >= \"{yesterday}\" AND updated < \"{today}\" AND statusCategory = Done"
  in_progress:
    jql: "assignee = {account_id} AND status = \"In Progress\""
  blocked:
    jql: ""
```

### config/project-status.yaml

```yaml
google_drive:
  upload_folder: ""

calendar:
  credentials_dir: "${GDOCS_MCP_DIR}"
```

### templates/sprint.yaml

The scaffold template definition, moved verbatim from the `templates.sprint`
section of the old config:

```yaml
base_dir: work/sprint-notes
naming: "{name}"
subdirs:
  - jira
  - github
  - git
  - email
  - calendar
  - google-docs
  - claude-code
files:
  sprint.yaml: |
    sprint_name: "{sprint_name}"
  manual-notes.md: |
    # Manual Notes
    ...
required_vars:
  - sprint_name
```

### templates/progress-brief.yaml

```yaml
base_dir: work/progress-briefs
naming: "{name}"
subdirs:
  - jira-issues
  - docs
files: {}
required_vars: []
```

## Code changes

### paths.py

Update path constants:

- `CONFIG_PATH` -> `CONFIG_DIR = REPO_ROOT / "config"`
- Add `SHARED_CONFIG_PATH = CONFIG_DIR / "shared.yaml"`
- Add `SPRINT_NOTES_CONFIG_PATH = CONFIG_DIR / "sprint-notes.yaml"`
- Add `STANDUP_CONFIG_PATH = CONFIG_DIR / "standup.yaml"`
- Add `PROJECT_STATUS_CONFIG_PATH = CONFIG_DIR / "project-status.yaml"`
- Add `PROJECT_CONFIGS_DIR = CONFIG_DIR / "project-configs"`
- Add `TEMPLATES_DIR = REPO_ROOT / "templates"`
- Remove old `CONFIG_PATH = SPRINT_NOTES_DIR / "config.yaml"`

### config.py

- `load_config()` replaced with specific loaders:
  - `load_shared_config()` — loads `config/shared.yaml`
  - `load_sprint_notes_config()` — loads `config/sprint-notes.yaml`
  - `load_standup_config()` — loads `config/standup.yaml`
  - `load_project_status_config()` — loads `config/project-status.yaml`
- `resolve_env_vars()` — kept but only needed for the few remaining
  `${ENV_VAR}` references in yaml (google_drive paths, calendar credentials_dir)
- Add `load_template(name)` — loads `templates/{name}.yaml`

### collect.py

- Use `load_sprint_notes_config()` instead of `load_config()`
- Read identity fields from `os.environ` directly
- Load `project_names` from `load_shared_config()` if needed

### standup.py

- Use `load_standup_config()` for queries
- Read identity fields from `os.environ` directly
- Load `project_names` from `load_shared_config()`

### collect_project_status.py

- Use `load_project_status_config()` instead of its local `load_config()`
- Read identity fields from `os.environ` directly
- Remove duplicated `project_names` — load from shared config

### scaffold.py

- Use `load_template(name)` instead of pulling templates from `load_config()`
- Discover available templates by listing `templates/*.yaml`

### .env.example

No changes needed — all env vars already present.

## Files deleted

- `work/sprint-notes/config.yaml`
- `work/project-status/config.yaml`

## What stays the same

- Sprint-level `sprint.yaml` files in `work/sprint-notes/{sprint}/`
- Per-project configs (move from `work/project-status/project-configs/` to
  `config/project-configs/`)
- `run.yaml` metadata files in project-status output dirs
- `.env` / `.env.example`
- All collection logic and output formats
