# Centralized Paths and Config-Driven Scaffolding

## Context

The work-journal repo has path constants (`REPO_ROOT`, `SRC_DIR`, `CONFIG_PATH`,
etc.) duplicated across `collect.py` and `standup.py`, each independently
computing the repo root from `__file__` position. Config loading (`load_config`,
`resolve_env_vars`, `load_dotenv`) is also duplicated.

Sprint and progress-brief directories are created by copying physical template
directories that live inside `work/`. This approach has several problems: template
dirs are code/config masquerading as work artifacts, `.gitkeep` files get copied
into gitignored paths, `copy_template_dir.py` exists but isn't wired to anything,
and there's no variable substitution (sprint name must be manually edited after
copy).

## Design

### Part 1: `paths.py` and `config.py`

**`src/work_journal/paths.py`** — single source for all repo paths.

```python
from pathlib import Path

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
CONFIG_PATH = SPRINT_NOTES_DIR / "config.yaml"
PROGRESS_BRIEFS_DIR = WORK_DIR / "progress-briefs"
```

`load_dotenv(REPO_ROOT / ".env")` runs as a module-level side effect in
`paths.py`, since every entry point needs it.

**`src/work_journal/config.py`** — shared config loading, extracted from the
duplicated code in `collect.py` and `standup.py`.

- `resolve_env_vars(obj)` — recursively resolve `${ENV_VAR}` placeholders
- `load_config()` — load and resolve `config.yaml`
- `load_sprint_config(sprint_dir)` — load a sprint's `sprint.yaml`

Modules that currently define their own path constants and config helpers get
replaced with imports from these two modules.

### Part 2: Config-driven scaffolding

Template definitions move into `config.yaml` under a new `templates` key:

```yaml
templates:
  sprint:
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
        # All other settings are inherited from sprint-notes/config.yaml.
        sprint_name: "{sprint_name}"
      manual-notes.md: |
        # Manual Notes

        Add notes here for context that isn't captured by automated data
        collection. These will be read by the drafting skill and incorporated
        into sprint notes.

        ## Slack highlights

        ## Email highlights

        ## Meetings / discussions

        ## Other
    required_vars:
      - sprint_name

  progress-brief:
    base_dir: work/progress-briefs
    naming: "{name}"
    subdirs:
      - jira-issues
      - docs
    files: {}
    required_vars: []
```

`{name}` is always the directory name passed on the CLI. Other variables come
from `--var` flags.

**`src/work_journal/scaffold.py`** — new module that:

1. Loads the template definition from config
2. Validates that all `required_vars` are provided
3. Creates `base_dir / naming.format(...)` with all `subdirs`
4. Writes each entry in `files` with variable substitution
5. Errors if the target directory already exists

CLI:

```bash
uv run python3 src/work_journal/scaffold.py sprint 2026-03-A \
    --var sprint_name="2026-03-A-Product-March"

uv run python3 src/work_journal/scaffold.py progress-brief 2026-Q1
```

## Deletions

- `work/sprint-notes/template-dir-sprint-name/` — replaced by config
- `work/progress-briefs/template-dir-quarter/` — replaced by config
- `src/work_journal/copy_template_dir.py` — dead code

## Updates

- `collect.py` — imports from `paths` and `config` instead of defining its own.
  `ensure_sprint_dir()` drops `shutil.copytree` fallback; errors if dir doesn't
  exist, telling you to run `scaffold.py` first.
- `standup.py` — imports from `paths` and `config` instead of defining its own.
- `CLAUDE.md` — workflow step 1 becomes `scaffold.py` command, dev commands
  updated.
- Skills referencing the old workflow get updated.

## New files

- `src/work_journal/paths.py`
- `src/work_journal/config.py`
- `src/work_journal/scaffold.py`
