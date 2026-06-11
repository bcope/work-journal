# Security Hardening for Initial Commit

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move sensitive identifiers into environment variables and gitignore generated data files so the repo can be safely committed to version control.

**Architecture:** Create a `.env` file (gitignored) for user-specific identifiers. Update `config.yaml` to use `${ENV_VAR}` placeholder syntax. Update `src/collect.py` to resolve env vars when loading config. Update CLAUDE.md to reference env vars instead of hardcoded values. Gitignore all generated data files (Jira JSON exports, enrichment output, progress brief exports).

**Tech Stack:** Python, PyYAML, python-dotenv, uv

---

### Task 1: Add .env file with all sensitive identifiers

This is the user's local config. It will never be committed.

**Files:**

- Create: `.env`
- Create: `.env.example`

**Step 1: Create .env with real values**

```bash
# .env - local environment variables (NEVER commit this file)
# See .env.example for the full list of keys.
# Values redacted from this plan doc — copy .env.example and fill in your values.
```

**Step 2: Create .env.example with placeholder values**

Same keys, no real values:

```bash
# .env.example - copy to .env and fill in your values

# Jira
JIRA_ACCOUNT_ID=your-jira-account-id
JIRA_BOARD_ID=your-board-id

# Email / Calendar / Drive
OWNER_EMAIL=you@example.com

# Google Drive
SPRINT_NOTES_FOLDER=https://drive.google.com/drive/folders/your-folder-id
MD_TO_GDOC_SCRIPT=~/path/to/md-to-gdoc.js

# Git
GIT_REPOS_DIR=~/git
GIT_AUTHOR=your-git-username

# Claude Code
CLAUDE_HISTORY_PATH=~/.claude/history.jsonl
CLAUDE_STATS_CACHE_PATH=~/.claude/stats-cache.json
CLAUDE_PROJECTS_PATH=~/.claude/projects
CLAUDE_WORK_DIRS=~/git
```

**Step 3: Verify**

```bash
cat .env | head -5
cat .env.example | head -5
```

---

### Task 2: Update .gitignore

**Files:**

- Modify: `.gitignore`

**Step 1: Replace .gitignore with comprehensive rules**

```gitignore
# Python-generated files
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv

# Environment variables
.env

# Generated data files - Jira JSON exports (contain PII)
work/sprint-notes/*/jira/*.json

# Generated data files - enrichment output (contain internal URLs, emails, attendee lists)
work/sprint-notes/*/email/
work/sprint-notes/*/calendar/
work/sprint-notes/*/google-docs/
work/sprint-notes/*/prior-sprint/
work/sprint-notes/*/enrichment-summary.md

# Generated data files - Claude Code raw history
work/sprint-notes/*/claude-code/history-excerpt.jsonl

# Progress brief Jira exports (contain PII)
work/progress-briefs/*/jira-issues/

# One-off data files
events-mentioning-ai.json
```

**Step 2: Verify no sensitive patterns are missing**

```bash
git status
```

Confirm that .env, JSON exports, enrichment files, and jira-issues/ would not be tracked.

---

### Task 3: Update config.yaml to use env var placeholders

**Files:**

- Modify: `work/sprint-notes/config.yaml`

Replace hardcoded values with `${ENV_VAR}` syntax. The Python loader (Task 4) will resolve these.

**Step 1: Replace sensitive values in config.yaml**

```yaml
# Repo-level configuration for sprint notes data collection.
# These values are constant across sprints. Only the sprint name varies
# per sprint (set in each sprint's sprint.yaml).
#
# Values using ${ENV_VAR} syntax are resolved from environment variables
# at runtime. Copy .env.example to .env and fill in your values.

jira:
  account_id: "${JIRA_ACCOUNT_ID}"
  board_id: ${JIRA_BOARD_ID}
  queries:
    # --- Planned work: issues in the sprint at sprint start ---
    # These tell the story of what was committed to.

    sprint_planned_completed:
      description: "Issues in the sprint at start that were completed during the sprint"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory = Done AND labels not in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-planned-completed.json"

    sprint_planned_incomplete:
      description: "Issues in the sprint at start that were NOT completed by sprint end"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory != Done AND labels not in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-planned-incomplete.json"

    # --- Added work: issues added to the sprint after it started ---
    # These tell the story of what emerged or interrupted.

    sprint_added_completed:
      description: "Issues added to the sprint after start, completed during the sprint"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory = Done AND labels in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-added-completed.json"

    sprint_added_incomplete:
      description: "Issues added to the sprint after start, not completed by sprint end"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory != Done AND labels in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-added-incomplete.json"

    # --- Non-sprint work: work done in the date range but never in this sprint ---
    # These tell the story of what happened outside the formal sprint scope.

    non_sprint_completed:
      description: "Issues assigned to user, completed in the date range, never in this sprint"
      jql: "assignee = {account_id} AND sprint != {sprint_id} AND statusCategory = Done AND resolved >= {start_date} AND resolved <= {end_date}"
      output: "jira/non-sprint-completed.json"

    non_sprint_incomplete:
      description: "Issues assigned to user, updated in the date range, never in this sprint, still open"
      jql: "assignee = {account_id} AND sprint != {sprint_id} AND statusCategory != Done AND worklogDate >= {start_date} AND worklogDate <= {end_date} AND worklogAuthor = {account_id}"
      output: "jira/non-sprint-incomplete.json"

    non_assigned_with_worklog:
      description: "Issues not assigned to user, but with worklogs by user in the date range, never in this sprint"
      jql: "assignee != {account_id} AND sprint != {sprint_id} AND worklogDate >= {start_date} AND worklogDate <= {end_date} AND worklogAuthor = {account_id}"
      output: "jira/non-sprint-non-assigned-with-worklog.json"

github:
  org: "${GITHUB_ORG}"
  output: "github/prs.md"
  format: markdown

git:
  repos_dir: "${GIT_REPOS_DIR}"
  author: "${GIT_AUTHOR}"
  output: "git/commit-log.md"

gmail:
  owner_email: "${OWNER_EMAIL}"
  queries:
    sent_mail:
      query: "from:me after:{start_date_slash} before:{end_date_slash}"
      output: "email/sent.md"
    highlighted_mail:
      query: TODO
      output: "email/highlights.md"
    incoming_requests:
      query: TODO
      output: "email/requests.md"

calendar:
  calendar_id: primary
  output: "calendar/events.md"

claude_code:
  history_path: "${CLAUDE_HISTORY_PATH}"
  stats_cache_path: "${CLAUDE_STATS_CACHE_PATH}"
  projects_path: "${CLAUDE_PROJECTS_PATH}"
  work_dirs:
    - "${CLAUDE_WORK_DIRS}"
  output: "claude-code/sessions.md"
  documents_output: "claude-code/documents.md"

google_drive:
  sprint_notes_folder: "${SPRINT_NOTES_FOLDER}"
  md_to_gdoc_script: "${MD_TO_GDOC_SCRIPT}"

standup:
  queries:
    completed_yesterday:
      jql: "assignee = {account_id} AND updated >= \"{yesterday}\" AND updated < \"{today}\" AND statusCategory = Done"
    in_progress:
      jql: "assignee = {account_id} AND status = \"In Progress\""
    blocked:
      jql: ""

project_names:
  COMPLY: "Compliance"
  DATA: "Data"
  BSR: "BSR"
  AGILE: "Agile"
  GGL: "GGL"
  VAST: "VAST"
  GGDM: "GGDisburse Migration"
  UPKEEP: "Upkeep"
```

Note: The `{account_id}`, `{sprint_id}`, etc. in JQL templates are **not** env vars -- they are runtime placeholders resolved by `template_jql()` in collect.py. Only `${ENV_VAR}` syntax refers to environment variables.

---

### Task 4: Update collect.py to resolve env vars in config

**Files:**

- Modify: `src/collect.py`

**Step 1: Add python-dotenv dependency**

```bash
uv add python-dotenv
```

**Step 2: Add env var resolution to collect.py**

Add these imports and functions near the top of the file, after the existing imports:

```python
import re
from dotenv import load_dotenv

# Load .env file from repo root
load_dotenv(REPO_ROOT / ".env")
```

Add a new function after `load_config()`:

```python
def resolve_env_vars(obj):
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(obj, str):
        def replacer(match):
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                print(f"Warning: env var {var_name} not set", file=sys.stderr)
                return match.group(0)
            return value
        return re.sub(r'\$\{(\w+)\}', replacer, obj)
    elif isinstance(obj, dict):
        return {k: resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_env_vars(item) for item in obj]
    return obj
```

Update `load_config()` to resolve env vars:

```python
def load_config() -> dict:
    """Load the repo-level config with env var resolution."""
    if not CONFIG_PATH.exists():
        print(f"Error: Config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return resolve_env_vars(config)
```

**Step 3: Verify collect.py still works**

```bash
uv run python3 src/collect.py 2026-03-A --dry-run
```

Expected: Same output as before, with env vars resolved from `.env`.

**Step 4: Commit**

```bash
git add src/collect.py pyproject.toml uv.lock
git commit -m "feat: resolve env vars in config at load time"
```

---

### Task 5: Update CLAUDE.md to reference env vars

**Files:**

- Modify: `CLAUDE.md`

**Step 1: Replace hardcoded identifiers**

Replace the "Key identifiers" section:

```markdown
## Key identifiers

- **Jira account ID:** Set via `JIRA_ACCOUNT_ID` env var (see `.env`)
- **Jira board ID:** Set via `JIRA_BOARD_ID` env var (see `.env`)
- **GitHub org:** Set via `GITHUB_ORG` env var (see `.env`)
- **Git author:** Set via `GIT_AUTHOR` env var (see `.env`)

The Jira API credentials (`JIRA_USER` / `JIRA_API_TOKEN`) authenticate as a generic API user, not bcope's personal account. JQL functions like `currentUser()` will not match bcope's issues — always use the explicit account ID from `JIRA_ACCOUNT_ID`.
```

Replace the Google Drive search tips section:

```markdown
## Google Drive search tips

When searching for docs owned by the user in a date range, use the query format with the email from `OWNER_EMAIL` env var:

```
owner:{OWNER_EMAIL} after:YYYY-MM-DD before:YYYY-MM-DD
```

Google Sheets API and Google Drive API must both be enabled for spreadsheet reading to work.
```

Replace the uploading section's code example:

```markdown
## Uploading to Google Docs

The `md-to-gdoc.js` script converts markdown to styled Google Docs. The script path and target Drive folder are configured in `work/sprint-notes/config.yaml` under `google_drive` (resolved from env vars).

```bash
node $MD_TO_GDOC_SCRIPT upload <file.md> \
  --title "Doc Title" \
  --folder "$SPRINT_NOTES_FOLDER"
```

The `--folder` flag accepts a Google Drive folder URL or bare folder ID.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: replace hardcoded identifiers with env var references"
```

---

### Task 6: Update skills that reference hardcoded values

**Files:**

- Check: `.claude/skills/enrich-sprint-data/SKILL.md`
- Check: `.claude/skills/draft-sprint-notes/SKILL.md`
- Check: `.claude/skills/upload-sprint-notes/SKILL.md`
- Check: `.claude/skills/standup/SKILL.md`

**Step 1: Audit skill files for hardcoded identifiers**

Search for the `OWNER_EMAIL` value, the Jira account ID, and the Google Drive folder ID in all skill files. The enrich-sprint-data skill references `owner:<email>` in its Google Docs search example (Phase 4, Step 1).

Replace hardcoded email in skill files with a reference to the config value. Skills read from `config.yaml`, so they will get the resolved value at runtime. The example in the skill file should use a placeholder:

```
owner:{owner_email} after:{start_date} before:{end_date}
```

And the skill's Phase 1 context-building should include `owner_email` from `config.yaml`'s `gmail.owner_email`.

**Step 2: Commit if changes were needed**

```bash
git add .claude/skills/
git commit -m "docs: replace hardcoded email in skill files with config reference"
```

---

### Task 7: Clean up generated data files from work/

These files are gitignored now (Task 2) but if they were previously tracked, `git rm --cached` is needed. Since this is the initial commit, just verify the gitignore is working.

**Files:**

- Verify: `work/sprint-notes/*/jira/*.json` are not staged
- Verify: `work/sprint-notes/*/email/` are not staged
- Verify: `work/sprint-notes/*/calendar/` are not staged
- Verify: `work/sprint-notes/*/google-docs/` are not staged
- Verify: `work/progress-briefs/*/jira-issues/` are not staged
- Verify: `events-mentioning-ai.json` is not staged

**Step 1: Check what git would track**

```bash
git add --dry-run .
```

Confirm none of the gitignored patterns appear. If any do, the gitignore rules need adjustment.

**Step 2: Also verify that files we DO want to commit are clean**

These should be tracked:

- `src/**/*.py` -- Python scripts (no secrets)
- `.claude/skills/**/*.md` -- Skill definitions (no secrets after Task 6)
- `work/sprint-notes/config.yaml` -- Config with env var placeholders (no secrets after Task 3)
- `work/sprint-notes/*/sprint.yaml` -- Sprint name only
- `work/sprint-notes/*/manual-notes.md` -- User-curated notes
- `work/sprint-notes/*/draft.md` or `final.md` -- Sprint note drafts (contain internal project names but no PII)
- `work/sprint-notes/*/github/prs.md` -- Public GitHub data
- `work/sprint-notes/*/git/commit-log.md` -- Local git commits
- `work/sprint-notes/*/claude-code/sessions.md` -- Session summaries (no raw history)
- `docs/**` -- Plans and design docs
- `CLAUDE.md`, `README.md`, `TODO.md`
- `.env.example`, `.gitignore`, `pyproject.toml`, `uv.lock`

---

### Task 8: Final verification and initial commit

**Step 1: Do a final grep for sensitive patterns**

```bash
# Check for each sensitive value from .env (Jira account ID, email, Drive folder ID, etc.)
grep -r "$JIRA_ACCOUNT_ID" --include="*.py" --include="*.md" --include="*.yaml" .
grep -r "$OWNER_EMAIL" --include="*.py" --include="*.md" --include="*.yaml" .
grep -r "<your-drive-folder-id>" --include="*.py" --include="*.md" --include="*.yaml" .
```

Expected: Zero results for all three. If any appear, go back and fix.

**Step 2: Stage and review**

```bash
git add .
git status
git diff --cached --stat
```

Review the file list. No `.env`, no `*.json` exports, no enrichment output, no jira-issues CSV/XML.

**Step 3: Commit**

```bash
git commit -m "initial commit: work-journal tooling and sprint note workflows"
```

---

## Summary of what goes where

| Data | Before | After |
| --- | --- | --- |
| Jira account ID | Hardcoded in CLAUDE.md and config.yaml | `.env` -> `${JIRA_ACCOUNT_ID}` in config.yaml |
| Jira board ID | Hardcoded in config.yaml | `.env` -> `${JIRA_BOARD_ID}` in config.yaml |
| Owner email | Hardcoded in CLAUDE.md and config.yaml | `.env` -> `${OWNER_EMAIL}` in config.yaml |
| Drive folder ID | Hardcoded in config.yaml | `.env` -> `${SPRINT_NOTES_FOLDER}` in config.yaml |
| Home dir paths | Hardcoded in config.yaml | `.env` -> `${GIT_REPOS_DIR}`, `${MD_TO_GDOC_SCRIPT}`, etc. |
| Jira JSON exports | Untracked (new repo) | Gitignored |
| Enrichment output | Untracked (new repo) | Gitignored |
| Progress brief exports | Untracked (new repo) | Gitignored |
| events-mentioning-ai.json | Untracked (new repo) | Gitignored |
