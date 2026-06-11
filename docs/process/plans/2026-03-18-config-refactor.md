# Config Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic `work/sprint-notes/config.yaml` into focused config files under `config/`, move templates to `templates/`, and read identity fields directly from env vars.

**Architecture:** New top-level `config/` and `templates/` directories. `config.py` gets per-process loaders that read specific yaml files. Identity fields (`JIRA_ACCOUNT_ID`, `GITHUB_ORG`, etc.) come from `os.environ` instead of yaml passthroughs. `work/` becomes pure output.

**Tech Stack:** Python, PyYAML, pytest, dotenv

---

## Task 1: Create config directory and new yaml files

**Files:**

- Create: `config/shared.yaml`
- Create: `config/sprint-notes.yaml`
- Create: `config/standup.yaml`
- Create: `config/project-status.yaml`

**Step 1: Create `config/shared.yaml`**

```yaml
# Shared configuration used across all work-journal processes.

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

**Step 2: Create `config/sprint-notes.yaml`**

Extract sprint-specific sections from the old config. Remove all identity fields -- those come from env vars now. Keep JQL query templates, output paths, and the sprint-specific google_drive upload folder.

```yaml
# Configuration for sprint notes data collection.
# Identity fields (Jira account, GitHub org, git author, etc.) come from
# environment variables. See .env.example.

jira:
  queries:
    sprint_planned_completed:
      description: "Issues in the sprint at start that were completed during the sprint"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory = Done AND labels not in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-planned-completed.json"

    sprint_planned_incomplete:
      description: "Issues in the sprint at start that were NOT completed by sprint end"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory != Done AND labels not in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-planned-incomplete.json"

    sprint_added_completed:
      description: "Issues added to the sprint after start, completed during the sprint"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory = Done AND labels in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-added-completed.json"

    sprint_added_incomplete:
      description: "Issues added to the sprint after start, not completed by sprint end"
      jql: "assignee = {account_id} AND sprint = {sprint_id} AND statusCategory != Done AND labels in (added_to_sprint-current, added_to_sprint-id-{sprint_id})"
      output: "jira/sprint-added-incomplete.json"

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
  output: "github/prs.md"
  format: markdown

git:
  output: "git/commit-log.md"

gmail:
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
  output: "claude-code/sessions.md"
  documents_output: "claude-code/documents.md"

google_drive:
  upload_folder: "${SPRINT_NOTES_FOLDER}"
```

**Step 3: Create `config/standup.yaml`**

```yaml
# Configuration for daily stand-up notes generation.

queries:
  completed_yesterday:
    jql: "assignee = {account_id} AND updated >= \"{yesterday}\" AND updated < \"{today}\" AND statusCategory = Done"
  in_progress:
    jql: "assignee = {account_id} AND status = \"In Progress\""
  blocked:
    jql: ""
```

**Step 4: Create `config/project-status.yaml`**

```yaml
# Configuration for project status updates.
# Per-project settings go in config/project-configs/<project>.yaml.

calendar:
  credentials_dir: "${GDOCS_MCP_DIR}"

google_drive:
  upload_folder: ""
```

**Step 5: Commit**

```bash
git add config/
git commit -m "add config/ directory with split yaml files"
```

## Task 2: Create templates directory

**Files:**

- Create: `templates/sprint.yaml`
- Create: `templates/progress-brief.yaml`

**Step 1: Create `templates/sprint.yaml`**

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
    # Sprint-level config. Only the sprint name is required.
    sprint_name: "{sprint_name}"
  manual-notes.md: |
    # Manual Notes

    Add notes here for context that isn't captured by automated data collection.
    These will be read by the drafting skill and incorporated into sprint notes.

    ## Slack highlights

    ## Email highlights

    ## Meetings / discussions

    ## Other
required_vars:
  - sprint_name
```

**Step 2: Create `templates/progress-brief.yaml`**

```yaml
base_dir: work/progress-briefs
naming: "{name}"
subdirs:
  - jira-issues
  - docs
files: {}
required_vars: []
```

**Step 3: Commit**

```bash
git add templates/
git commit -m "add templates/ directory with scaffold templates"
```

## Task 3: Move project-configs to config/

**Files:**

- Move: `work/project-status/project-configs/` -> `config/project-configs/`

**Step 1: Move the directory**

```bash
mv work/project-status/project-configs config/project-configs
```

**Step 2: Commit**

```bash
git add config/project-configs/ work/project-status/project-configs/
git commit -m "move project-configs to config/"
```

## Task 4: Update paths.py

**Files:**

- Modify: `src/work_journal/paths.py`
- Test: `tests/test_paths.py`

**Step 1: Write the failing test**

Update `tests/test_paths.py` to test the new path constants:

```python
def test_config_dir_exists():
    from work_journal.paths import CONFIG_DIR

    assert CONFIG_DIR.exists()
    assert CONFIG_DIR.name == "config"


def test_shared_config_path_exists():
    from work_journal.paths import SHARED_CONFIG_PATH

    assert SHARED_CONFIG_PATH.exists()
    assert SHARED_CONFIG_PATH.name == "shared.yaml"


def test_templates_dir_exists():
    from work_journal.paths import TEMPLATES_DIR

    assert TEMPLATES_DIR.exists()
    assert TEMPLATES_DIR.name == "templates"


def test_project_configs_dir_exists():
    from work_journal.paths import PROJECT_CONFIGS_DIR

    assert PROJECT_CONFIGS_DIR.exists()
```

Remove the old `test_config_path_exists` test that checks for `CONFIG_PATH`.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL -- `CONFIG_DIR`, `SHARED_CONFIG_PATH`, `TEMPLATES_DIR` not defined.

**Step 3: Update `src/work_journal/paths.py`**

```python
"""Centralized path constants for the work-journal repo.

All modules should import paths from here instead of computing their own.
Loads .env as a side effect on first import.
"""

from pathlib import Path

from dotenv import load_dotenv


def _find_repo_root() -> Path:
    """Walk up from this file until we find pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repo root (no pyproject.toml found)")


REPO_ROOT = _find_repo_root()
SRC_DIR = REPO_ROOT / "src" / "work_journal"
WORK_DIR = REPO_ROOT / "work"
SPRINT_NOTES_DIR = WORK_DIR / "sprint-notes"
PROGRESS_BRIEFS_DIR = WORK_DIR / "progress-briefs"
PROJECT_STATUS_DIR = WORK_DIR / "project-status"
STANDUP_DIR = WORK_DIR / "standup"

# Config paths
CONFIG_DIR = REPO_ROOT / "config"
SHARED_CONFIG_PATH = CONFIG_DIR / "shared.yaml"
SPRINT_NOTES_CONFIG_PATH = CONFIG_DIR / "sprint-notes.yaml"
STANDUP_CONFIG_PATH = CONFIG_DIR / "standup.yaml"
PROJECT_STATUS_CONFIG_PATH = CONFIG_DIR / "project-status.yaml"
PROJECT_CONFIGS_DIR = CONFIG_DIR / "project-configs"
TEMPLATES_DIR = REPO_ROOT / "templates"

# Load .env from repo root — every entry point needs this
load_dotenv(REPO_ROOT / ".env")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_journal/paths.py tests/test_paths.py
git commit -m "update paths.py with new config/ and templates/ constants"
```

## Task 5: Update config.py

**Files:**

- Modify: `src/work_journal/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing tests**

Replace the `test_load_config_returns_dict` test and add new tests:

```python
def test_load_shared_config_returns_dict():
    from work_journal.config import load_shared_config

    config = load_shared_config()
    assert isinstance(config, dict)
    assert "project_names" in config


def test_load_sprint_notes_config_returns_dict():
    from work_journal.config import load_sprint_notes_config

    config = load_sprint_notes_config()
    assert isinstance(config, dict)
    assert "jira" in config


def test_load_standup_config_returns_dict():
    from work_journal.config import load_standup_config

    config = load_standup_config()
    assert isinstance(config, dict)
    assert "queries" in config


def test_load_project_status_config_returns_dict():
    from work_journal.config import load_project_status_config

    config = load_project_status_config()
    assert isinstance(config, dict)


def test_load_template_returns_dict():
    from work_journal.config import load_template

    template = load_template("sprint")
    assert isinstance(template, dict)
    assert "base_dir" in template
    assert "subdirs" in template


def test_load_template_missing():
    from work_journal.config import load_template

    with pytest.raises(SystemExit):
        load_template("nonexistent")


def test_list_templates():
    from work_journal.config import list_templates

    templates = list_templates()
    assert "sprint" in templates
    assert "progress-brief" in templates
```

Keep the existing `resolve_env_vars` tests and `load_sprint_config` tests unchanged.

Remove the `test_load_config_returns_dict` test.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL -- new functions not defined.

**Step 3: Update `src/work_journal/config.py`**

```python
"""Shared configuration loading for the work-journal repo.

Provides config file loading with environment variable resolution.
"""

import os
import re
import sys
from pathlib import Path

import yaml

from work_journal.paths import (
    PROJECT_STATUS_CONFIG_PATH,
    SHARED_CONFIG_PATH,
    SPRINT_NOTES_CONFIG_PATH,
    STANDUP_CONFIG_PATH,
    TEMPLATES_DIR,
)


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

        return re.sub(r"\$\{(\w+)\}", replacer, obj)
    elif isinstance(obj, dict):
        return {k: resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_env_vars(item) for item in obj]
    return obj


def _load_yaml(path: Path) -> dict:
    """Load a yaml file with env var resolution, or exit on error."""
    if not path.exists():
        print(f"Error: Config not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        config = yaml.safe_load(f)
    return resolve_env_vars(config)


def load_shared_config() -> dict:
    """Load the shared config (project_names, google_drive script)."""
    return _load_yaml(SHARED_CONFIG_PATH)


def load_sprint_notes_config() -> dict:
    """Load the sprint notes collection config."""
    return _load_yaml(SPRINT_NOTES_CONFIG_PATH)


def load_standup_config() -> dict:
    """Load the standup config."""
    return _load_yaml(STANDUP_CONFIG_PATH)


def load_project_status_config() -> dict:
    """Load the project status config."""
    return _load_yaml(PROJECT_STATUS_CONFIG_PATH)


def load_sprint_config(sprint_dir: Path) -> dict:
    """Load the sprint-level config."""
    sprint_yaml = sprint_dir / "sprint.yaml"
    if not sprint_yaml.exists():
        print(f"Error: Sprint config not found at {sprint_yaml}", file=sys.stderr)
        sys.exit(1)
    with open(sprint_yaml) as f:
        return yaml.safe_load(f)


def load_template(name: str) -> dict:
    """Load a scaffold template by name."""
    path = TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        print(f"Error: Template not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)


def list_templates() -> list[str]:
    """Return available template names."""
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml"))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_journal/config.py tests/test_config.py
git commit -m "update config.py with per-process loaders and template loading"
```

## Task 6: Update collect.py

**Files:**

- Modify: `src/work_journal/collect.py`

**Step 1: Update imports and config loading**

Replace:

```python
from work_journal.config import load_config, load_sprint_config
```

With:

```python
from work_journal.config import load_sprint_config, load_sprint_notes_config
```

**Step 2: Update `resolve_sprint` to read `board_id` from env**

```python
def resolve_sprint(sprint_config: dict) -> dict:
    """Resolve sprint name to full sprint metadata via Jira API."""
    board_id = int(sprint_config.get("board_id", os.environ["JIRA_BOARD_ID"]))
    sprint_name = sprint_config["sprint_name"]

    session = _make_session()
    result = find_sprint_by_name(session, board_id, sprint_name)
    if result is None:
        print(
            f"Error: Could not find sprint '{sprint_name}' on board {board_id}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return result
```

**Step 3: Update `collect_jira_issues` to take `account_id` parameter**

Change the signature to accept `account_id` directly instead of reading from config:

```python
def collect_jira_issues(sprint_dir: Path, queries: dict, variables: dict) -> None:
```

The `queries` come from `config["jira"]["queries"]` where `config` is now `load_sprint_notes_config()`.

**Step 4: Update `collect_github_prs` to read from env**

```python
def collect_github_prs(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    gh_config = config.get("github", {})
    org = os.environ.get("GITHUB_ORG", "")
    output_file = gh_config.get("output", "github/prs.md")
    output_format = gh_config.get("format", "markdown")
    # ... rest unchanged
```

**Step 5: Update `collect_git_commits` to read from env**

```python
def collect_git_commits(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    git_config = config.get("git", {})
    repos_dir = os.path.expanduser(os.environ.get("GIT_REPOS_DIR", "~/git"))
    author = os.environ.get("GIT_AUTHOR", "")
    output_file = git_config.get("output", "git/commit-log.md")
    # ... rest unchanged
```

**Step 6: Update `collect_claude_code_activity` to read from env**

```python
def collect_claude_code_activity(
    sprint_dir: Path, config: dict, start_date: str, end_date: str
) -> None:
    cc_config = config.get("claude_code", {})
    history_path = os.path.expanduser(
        os.environ.get("CLAUDE_HISTORY_PATH", "~/.claude/history.jsonl")
    )
    stats_cache_path = os.path.expanduser(
        os.environ.get("CLAUDE_STATS_CACHE_PATH", "~/.claude/stats-cache.json")
    )
    projects_path = os.path.expanduser(
        os.environ.get("CLAUDE_PROJECTS_PATH", "~/.claude/projects")
    )
    work_dirs = [os.path.expanduser(os.environ.get("CLAUDE_WORK_DIRS", "~/git"))]
    output_file = cc_config.get("output", "claude-code/sessions.md")
    docs_output_file = cc_config.get("documents_output", "claude-code/documents.md")
    # ... rest unchanged
```

**Step 7: Update `main()` to use new config loaders**

```python
def main():
    # ... argparse unchanged ...

    config = load_sprint_notes_config()
    sprint_dir = ensure_sprint_dir(args.sprint)

    # ... sprint.yaml check unchanged ...

    sprint_config = load_sprint_config(sprint_dir)

    print(f"Resolving sprint: {sprint_config['sprint_name']}")
    sprint_info = resolve_sprint(sprint_config)
    start_date, end_date = extract_dates(sprint_info)
    sprint_id = sprint_info["id"]
    # ...

    variables = {
        "account_id": os.environ["JIRA_ACCOUNT_ID"],
        "start_date": start_date,
        "end_date": end_date,
        "sprint_id": str(sprint_id),
    }

    # ... dry_run section: read queries from config["jira"]["queries"] ...

    # Collect everything
    print("Collecting sprint info...")
    collect_jira_sprint_info(sprint_dir, sprint_info)

    print("Collecting Jira issues...")
    collect_jira_issues(sprint_dir, config["jira"].get("queries", {}), variables)

    # ... rest unchanged, each function reads identity from env ...
```

**Step 8: Run tests**

Run: `uv run pytest -v`
Expected: PASS

**Step 9: Commit**

```bash
git add src/work_journal/collect.py
git commit -m "update collect.py to use sprint-notes config and env vars"
```

## Task 7: Update standup.py

**Files:**

- Modify: `src/work_journal/standup.py`

**Step 1: Update imports**

Replace:

```python
from work_journal.config import load_config
```

With:

```python
from work_journal.config import load_shared_config, load_standup_config
```

**Step 2: Update `collect_data` to read identity from env**

```python
def collect_data(standup_config: dict, yesterday: date, today: date) -> dict:
    """Collect all stand-up data from Jira, GitHub, and git."""
    account_id = os.environ["JIRA_ACCOUNT_ID"]
    org = os.environ.get("GITHUB_ORG", "")
    git_author = os.environ.get("GIT_AUTHOR", "")
    standup_queries = standup_config.get("queries", {})
    # ... rest of function unchanged, except remove config["git"] references
```

**Step 3: Update `query_git_log` to read from env**

```python
def query_git_log(since: str, until: str) -> str:
    """Query local git commits via direct import."""
    repos_dir = os.path.expanduser(os.environ.get("GIT_REPOS_DIR", "~/git"))
    author = os.environ.get("GIT_AUTHOR", "")
    # ... rest unchanged
```

**Step 4: Update `main()`**

```python
def main():
    # ... argparse unchanged ...

    standup_config = load_standup_config()
    shared_config = load_shared_config()
    yesterday, today = resolve_dates(args.yesterday)

    print(f"Collecting stand-up data (yesterday={yesterday}, today={today})...", file=sys.stderr)

    data = collect_data(standup_config, yesterday, today)

    if args.output_json:
        output = json.dumps(data, indent=2)
    else:
        project_names = shared_config.get("project_names", {})
        output = format_markdown(data, project_names)

    # ... rest unchanged
```

**Step 5: Update the `collect_data` call to `query_git_log`**

Change from `query_git_log(config, yesterday_str, today_str)` to `query_git_log(yesterday_str, today_str)`.

**Step 6: Run tests**

Run: `uv run pytest -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/work_journal/standup.py
git commit -m "update standup.py to use standup config and env vars"
```

## Task 8: Update collect_project_status.py

**Files:**

- Modify: `src/work_journal/collect_project_status.py`

**Step 1: Update imports**

Replace:

```python
from work_journal.config import resolve_env_vars
from work_journal.paths import (
    PROJECT_CONFIGS_DIR,
    PROJECT_STATUS_CONFIG_PATH,
    PROJECT_STATUS_DIR,
    REPO_ROOT,
)
```

With:

```python
from work_journal.config import load_project_status_config
from work_journal.paths import (
    PROJECT_CONFIGS_DIR,
    PROJECT_STATUS_DIR,
    REPO_ROOT,
)
```

**Step 2: Remove the local `load_config` function**

Delete the `load_config()` function defined in this file (lines 36-43). Use the imported `load_project_status_config()` instead.

**Step 3: Update `main()`**

```python
    config = load_project_status_config()
    project_config = load_project_config(args.project)
```

The `load_project_config` function already reads from `PROJECT_CONFIGS_DIR`, which now points to `config/project-configs/` via the updated `paths.py`.

**Step 4: Run tests**

Run: `uv run pytest tests/test_collect_project_status.py -v`
Expected: PASS (these tests only test `resolve_run_dir`, no config dependency)

**Step 5: Commit**

```bash
git add src/work_journal/collect_project_status.py
git commit -m "update collect_project_status.py to use project-status config"
```

## Task 9: Update scaffold.py

**Files:**

- Modify: `src/work_journal/scaffold.py`
- Test: `tests/test_scaffold.py`

**Step 1: Update imports**

Replace:

```python
from work_journal.config import load_config
```

With:

```python
from work_journal.config import list_templates, load_template
```

**Step 2: Update `main()`**

```python
def main():
    available = list_templates()

    parser = argparse.ArgumentParser(
        description="Create work directories from config-driven templates.",
    )
    parser.add_argument(
        "template",
        choices=available if available else [],
        help="Template type to scaffold",
    )
    parser.add_argument(
        "name",
        help="Directory name (e.g., 2026-03-A, 2026-Q1)",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Variable for template substitution (repeatable)",
    )

    args = parser.parse_args()

    variables: dict[str, str] = {}
    for var_str in args.var:
        if "=" not in var_str:
            print(f"Error: --var must be KEY=VALUE, got: {var_str}", file=sys.stderr)
            sys.exit(1)
        key, value = var_str.split("=", 1)
        variables[key] = value

    template = load_template(args.template)
    required = template.get("required_vars", [])
    validate_vars(variables, required)

    result = scaffold(template, args.name, variables)
    print(f"Created {result.relative_to(REPO_ROOT)}")
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_scaffold.py -v`
Expected: PASS (scaffold tests use `base_override` and inline template dicts, no config dependency)

**Step 4: Commit**

```bash
git add src/work_journal/scaffold.py
git commit -m "update scaffold.py to load templates from templates/"
```

## Task 10: Delete old config files

**Files:**

- Delete: `work/sprint-notes/config.yaml`
- Delete: `work/project-status/config.yaml`

**Step 1: Verify nothing else references the old paths**

```bash
uv run ruff check .
uv run pytest -v
```

Expected: PASS

**Step 2: Delete old files**

```bash
git rm work/sprint-notes/config.yaml
git rm work/project-status/config.yaml
```

**Step 3: Commit**

```bash
git commit -m "remove old config.yaml files from work/"
```

## Task 11: Update CLAUDE.md

**Files:**

- Modify: `CLAUDE.md`

**Step 1: Update project structure section**

Replace references to `work/sprint-notes/config.yaml` and `work/project-status/config.yaml` with the new paths. Update the project structure to include `config/` and `templates/`. Key changes:

- Add `config/` directory description
- Add `templates/` directory description
- Update `src/work_journal/config.py` description
- Remove `work/sprint-notes/config.yaml` reference
- Remove `work/project-status/config.yaml` reference
- Update `project_names` canonical source to `config/shared.yaml`
- Update Google Drive script reference to `config/shared.yaml`
- Update project-configs path to `config/project-configs/`

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "update CLAUDE.md for new config structure"
```

## Task 12: Update skill files

**Files:**

- Modify: `.claude/skills/standup/SKILL.md`
- Modify: `.claude/skills/project-status/SKILL.md`
- Modify: `.claude/skills/draft-sprint-notes/SKILL.md`
- Modify: `.claude/skills/enrich-sprint-data/SKILL.md`
- Modify: `.claude/skills/upload-sprint-notes/SKILL.md`

**Step 1: Update each skill file**

For each file, replace references to old config paths:

- `work/sprint-notes/config.yaml` -> `config/shared.yaml` (for project_names), `config/sprint-notes.yaml` (for sprint settings), or `config/standup.yaml` (for standup queries)
- `work/project-status/config.yaml` -> `config/shared.yaml` (for project_names)
- `config.yaml` (generic) -> the specific config file

Specific changes:

**standup/SKILL.md:**

- "reads config from `work/sprint-notes/config.yaml`" -> "reads config from `config/standup.yaml` and `config/shared.yaml`"
- "the `standup.queries.blocked.jql` template in config.yaml" -> "the `queries.blocked.jql` template in `config/standup.yaml`"

**project-status/SKILL.md:**

- "The `project_names` mapping in `work/project-status/config.yaml`" -> "The `project_names` mapping in `config/shared.yaml`"

**draft-sprint-notes/SKILL.md:**

- "from `config.yaml` `project_names`" -> "from `config/shared.yaml` `project_names`"

**enrich-sprint-data/SKILL.md:**

- "Read `project_names` for mapping keys to readable names, and `gmail.owner_email` for email search context" -> "Read `config/shared.yaml` for `project_names` mapping, and `OWNER_EMAIL` env var for email search context"

**upload-sprint-notes/SKILL.md:**

- "path configured in `work/sprint-notes/config.yaml` under `google_drive.md_to_gdoc_script`" -> "path configured in `config/shared.yaml` under `google_drive.md_to_gdoc_script`"
- "Read `work/sprint-notes/config.yaml` and extract" -> "Read config files and extract"
- `google_drive.md_to_gdoc_script` from `config/shared.yaml`
- `google_drive.upload_folder` from `config/sprint-notes.yaml`

**Step 2: Commit**

```bash
git add .claude/skills/
git commit -m "update skill files for new config paths"
```

## Task 13: Run full test suite and lint

**Step 1: Run all checks**

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
uv run pytest -v
```

**Step 2: Fix any issues found**

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix lint and type issues from config refactor"
```
