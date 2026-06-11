# Centralized Paths and Config-Driven Scaffolding — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract duplicated path constants and config loading into shared modules, replace physical template directories with config-driven scaffolding.

**Architecture:** Two new shared modules (`paths.py`, `config.py`) centralize repo paths and config loading. A new `scaffold.py` reads template definitions from `config.yaml` to create work directories. Existing scripts (`collect.py`, `standup.py`) become thin consumers of these shared modules.

**Tech Stack:** Python 3.12, pathlib, PyYAML, pytest, ruff, uv

---

### Task 1: Create `paths.py` with repo root discovery

**Files:**

- Create: `src/work_journal/paths.py`
- Test: `tests/test_paths.py`

**Step 1: Write the failing test**

```python
# tests/test_paths.py
from pathlib import Path


def test_repo_root_contains_pyproject():
    from work_journal.paths import REPO_ROOT

    assert (REPO_ROOT / "pyproject.toml").exists()


def test_repo_root_is_absolute():
    from work_journal.paths import REPO_ROOT

    assert REPO_ROOT.is_absolute()


def test_src_dir_exists():
    from work_journal.paths import SRC_DIR

    assert SRC_DIR.exists()
    assert SRC_DIR.name == "work_journal"


def test_config_path_exists():
    from work_journal.paths import CONFIG_PATH

    assert CONFIG_PATH.exists()
    assert CONFIG_PATH.name == "config.yaml"


def test_sprint_notes_dir():
    from work_journal.paths import SPRINT_NOTES_DIR

    assert SPRINT_NOTES_DIR.name == "sprint-notes"


def test_progress_briefs_dir():
    from work_journal.paths import PROGRESS_BRIEFS_DIR

    assert PROGRESS_BRIEFS_DIR.name == "progress-briefs"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

```python
# src/work_journal/paths.py
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
CONFIG_PATH = SPRINT_NOTES_DIR / "config.yaml"
PROGRESS_BRIEFS_DIR = WORK_DIR / "progress-briefs"

# Load .env from repo root — every entry point needs this
load_dotenv(REPO_ROOT / ".env")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (all 6 tests)

**Step 5: Run linter**

Run: `uv run ruff check src/work_journal/paths.py tests/test_paths.py && uv run ruff format --check src/work_journal/paths.py tests/test_paths.py`
Expected: All checks passed

**Step 6: Commit**

```bash
git add src/work_journal/paths.py tests/test_paths.py
git commit -m "feat: add centralized paths module with repo root discovery"
```

---

### Task 2: Create `config.py` with shared config loading

**Files:**

- Create: `src/work_journal/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import os


def test_resolve_env_vars_simple(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "hello")
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars("${TEST_VAR}") == "hello"


def test_resolve_env_vars_nested_dict(monkeypatch):
    monkeypatch.setenv("A", "1")
    monkeypatch.setenv("B", "2")
    from work_journal.config import resolve_env_vars

    result = resolve_env_vars({"x": "${A}", "y": {"z": "${B}"}})
    assert result == {"x": "1", "y": {"z": "2"}}


def test_resolve_env_vars_list(monkeypatch):
    monkeypatch.setenv("ITEM", "val")
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars(["${ITEM}", "literal"]) == ["val", "literal"]


def test_resolve_env_vars_missing_warns(monkeypatch, capsys):
    monkeypatch.delenv("SURELY_MISSING", raising=False)
    from work_journal.config import resolve_env_vars

    result = resolve_env_vars("${SURELY_MISSING}")
    assert result == "${SURELY_MISSING}"
    assert "SURELY_MISSING" in capsys.readouterr().err


def test_resolve_env_vars_passthrough():
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars(42) == 42
    assert resolve_env_vars(None) is None


def test_load_config_returns_dict():
    from work_journal.config import load_config

    config = load_config()
    assert isinstance(config, dict)
    assert "jira" in config


def test_load_sprint_config(tmp_path):
    from work_journal.config import load_sprint_config

    sprint_yaml = tmp_path / "sprint.yaml"
    sprint_yaml.write_text('sprint_name: "test-sprint"\n')
    result = load_sprint_config(tmp_path)
    assert result["sprint_name"] == "test-sprint"


def test_load_sprint_config_missing(tmp_path):
    import pytest

    from work_journal.config import load_sprint_config

    with pytest.raises(SystemExit):
        load_sprint_config(tmp_path)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Extract the duplicated functions from `collect.py` and `standup.py`:

```python
# src/work_journal/config.py
"""Shared configuration loading for the work-journal repo.

Provides config file loading with environment variable resolution.
"""

import os
import re
import sys
from pathlib import Path

import yaml

from work_journal.paths import CONFIG_PATH


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


def load_config() -> dict:
    """Load the repo-level config with env var resolution."""
    if not CONFIG_PATH.exists():
        print(f"Error: Config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return resolve_env_vars(config)


def load_sprint_config(sprint_dir: Path) -> dict:
    """Load the sprint-level config."""
    sprint_yaml = sprint_dir / "sprint.yaml"
    if not sprint_yaml.exists():
        print(f"Error: Sprint config not found at {sprint_yaml}", file=sys.stderr)
        sys.exit(1)
    with open(sprint_yaml) as f:
        return yaml.safe_load(f)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (all 8 tests)

**Step 5: Run linter**

Run: `uv run ruff check src/work_journal/config.py tests/test_config.py && uv run ruff format --check src/work_journal/config.py tests/test_config.py`
Expected: All checks passed

**Step 6: Commit**

```bash
git add src/work_journal/config.py tests/test_config.py
git commit -m "feat: add shared config module with env var resolution"
```

---

### Task 3: Refactor `collect.py` to use `paths` and `config` modules

**Files:**

- Modify: `src/work_journal/collect.py`

**Step 1: Replace path constants and config functions**

Remove these lines from `collect.py`:

```python
# DELETE these imports:
import re
import shutil
from dotenv import load_dotenv

# DELETE these constants:
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "src" / "work_journal"
SPRINT_NOTES_DIR = REPO_ROOT / "work" / "sprint-notes"
CONFIG_PATH = SPRINT_NOTES_DIR / "config.yaml"
TEMPLATE_DIR = SPRINT_NOTES_DIR / "template-dir-sprint-name"

# Load .env file from repo root
load_dotenv(REPO_ROOT / ".env")

# DELETE these functions (entire bodies):
def resolve_env_vars(obj): ...
def load_config() -> dict: ...
def load_sprint_config(sprint_dir: Path) -> dict: ...
```

Add these imports at the top (after stdlib imports, before `yaml`):

```python
from work_journal.config import load_config, load_sprint_config
from work_journal.paths import REPO_ROOT, SRC_DIR, SPRINT_NOTES_DIR
```

The `import yaml` line can also be removed since `collect.py` only used it inside the now-deleted `load_config` and `load_sprint_config`.

**Step 2: Replace `ensure_sprint_dir` with a version that errors instead of creating**

Replace the entire `ensure_sprint_dir` function:

```python
def ensure_sprint_dir(sprint_name: str) -> Path:
    """Return the sprint directory path, erroring if it doesn't exist."""
    sprint_dir = SPRINT_NOTES_DIR / sprint_name
    if not sprint_dir.exists():
        print(
            f"Error: Sprint directory {sprint_dir.relative_to(REPO_ROOT)} does not exist.\n"
            f"Create it first with: uv run python3 src/work_journal/scaffold.py"
            f" sprint {sprint_name} --var sprint_name=\"YOUR-SPRINT-NAME\"",
            file=sys.stderr,
        )
        sys.exit(1)
    return sprint_dir
```

**Step 3: Remove the REPLACE-ME check from main()**

Since `scaffold.py` will write the correct sprint name at creation time, the `REPLACE-ME` check in `main()` is no longer needed. Remove this block:

```python
    if sprint_config.get("sprint_name") == "REPLACE-ME":
        print(
            f"Error: sprint_name in {sprint_yaml_path.relative_to(REPO_ROOT)}"
            " is still 'REPLACE-ME'.\n"
            "Set it to the actual Jira sprint name.",
            file=sys.stderr,
        )
        sys.exit(1)
```

**Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS (all tests including smoke test — `import work_journal` still works)

**Step 5: Run linter**

Run: `uv run ruff check src/work_journal/collect.py && uv run ruff format --check src/work_journal/collect.py`
Expected: All checks passed. Fix any unused import warnings (e.g. `yaml`, `re`, `shutil`).

**Step 6: Verify script still runs**

Run: `uv run python3 src/work_journal/collect.py --help`
Expected: Shows usage help without errors

**Step 7: Commit**

```bash
git add src/work_journal/collect.py
git commit -m "refactor: collect.py uses shared paths and config modules"
```

---

### Task 4: Refactor `standup.py` to use `paths` and `config` modules

**Files:**

- Modify: `src/work_journal/standup.py`

**Step 1: Replace path constants and config functions**

Remove these lines from `standup.py`:

```python
# DELETE these imports:
import re
from pathlib import Path
from dotenv import load_dotenv

# DELETE these constants:
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = REPO_ROOT / "src" / "work_journal"
CONFIG_PATH = REPO_ROOT / "work" / "sprint-notes" / "config.yaml"

# Load .env file from repo root
load_dotenv(REPO_ROOT / ".env")

# DELETE these functions:
def resolve_env_vars(obj): ...
def load_config() -> dict: ...
```

Add these imports (after stdlib imports):

```python
from work_journal.config import load_config
from work_journal.paths import SRC_DIR
```

Note: `standup.py` does not use `REPO_ROOT` anywhere after removing the constants, so don't import it. It does still need `Path` for type annotations — but check if it actually uses `Path` anywhere in the remaining code. If not, remove that import too.

`standup.py` still uses `import yaml` indirectly through its own `load_config` — but since that's deleted now and it doesn't call `yaml` anywhere else, remove the `import yaml` line too.

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS

**Step 3: Run linter**

Run: `uv run ruff check src/work_journal/standup.py && uv run ruff format --check src/work_journal/standup.py`
Expected: All checks passed. Fix any unused imports flagged.

**Step 4: Verify script still runs**

Run: `uv run python3 src/work_journal/standup.py --help`
Expected: Shows usage help without errors

**Step 5: Commit**

```bash
git add src/work_journal/standup.py
git commit -m "refactor: standup.py uses shared paths and config modules"
```

---

### Task 5: Add template definitions to `config.yaml`

**Files:**

- Modify: `work/sprint-notes/config.yaml`

**Step 1: Append templates section to config.yaml**

Add at the end of the file, after the `project_names` section:

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

        Add notes here for context that isn't captured by automated data collection.
        These will be read by the drafting skill and incorporated into sprint notes.

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

**Step 2: Verify config still loads**

Run: `uv run python3 -c "from work_journal.config import load_config; c = load_config(); print(list(c['templates'].keys()))"`
Expected: `['sprint', 'progress-brief']`

**Step 3: Commit**

```bash
git add work/sprint-notes/config.yaml
git commit -m "feat: add template definitions to config.yaml for scaffolding"
```

---

### Task 6: Create `scaffold.py`

**Files:**

- Create: `src/work_journal/scaffold.py`
- Test: `tests/test_scaffold.py`

**Step 1: Write the failing tests**

```python
# tests/test_scaffold.py
import pytest

from work_journal.scaffold import scaffold, validate_vars


def test_validate_vars_passes():
    """No error when all required vars are provided."""
    validate_vars({"sprint_name": "x"}, ["sprint_name"])


def test_validate_vars_missing():
    """SystemExit when a required var is missing."""
    with pytest.raises(SystemExit):
        validate_vars({}, ["sprint_name"])


def test_scaffold_creates_subdirs(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": ["a", "b", "c"],
        "files": {},
        "required_vars": [],
    }
    result = scaffold(template, "test-dir", {}, base_override=tmp_path)
    assert result.exists()
    assert (result / "a").is_dir()
    assert (result / "b").is_dir()
    assert (result / "c").is_dir()


def test_scaffold_writes_files_with_substitution(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {
            "config.yaml": 'name: "{sprint_name}"\n',
        },
        "required_vars": ["sprint_name"],
    }
    result = scaffold(
        template, "my-sprint", {"sprint_name": "Sprint-One"}, base_override=tmp_path
    )
    content = (result / "config.yaml").read_text()
    assert 'name: "Sprint-One"' in content


def test_scaffold_errors_if_dir_exists(tmp_path):
    (tmp_path / "existing").mkdir()
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {},
        "required_vars": [],
    }
    with pytest.raises(SystemExit):
        scaffold(template, "existing", {}, base_override=tmp_path)


def test_scaffold_naming_with_vars(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {},
        "required_vars": [],
    }
    result = scaffold(template, "2026-Q1", {}, base_override=tmp_path)
    assert result.name == "2026-Q1"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scaffold.py -v`
Expected: FAIL with "ImportError"

**Step 3: Write the implementation**

```python
# src/work_journal/scaffold.py
"""Create work directories from config-driven templates.

Reads template definitions from config.yaml and creates directory structures
with variable substitution in file contents.

Usage:
    uv run python3 src/work_journal/scaffold.py sprint 2026-03-A \
        --var sprint_name="2026-03-A-Product-March"
    uv run python3 src/work_journal/scaffold.py progress-brief 2026-Q1
"""

import argparse
import sys
from pathlib import Path

from work_journal.config import load_config
from work_journal.paths import REPO_ROOT


def validate_vars(variables: dict[str, str], required: list[str]) -> None:
    """Check that all required variables are provided."""
    missing = [v for v in required if v not in variables]
    if missing:
        print(
            f"Error: Missing required variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


def scaffold(
    template: dict,
    name: str,
    variables: dict[str, str],
    base_override: Path | None = None,
) -> Path:
    """Create a directory from a template definition.

    Args:
        template: Template dict from config (base_dir, naming, subdirs, files,
            required_vars).
        name: Directory name (available as {name} in templates).
        variables: User-provided variables for substitution.
        base_override: Override base_dir for testing. If None, resolves
            relative to REPO_ROOT.

    Returns:
        Path to the created directory.
    """
    all_vars = {"name": name, **variables}

    # Resolve base directory
    if base_override is not None:
        base_dir = base_override
    else:
        base_dir = REPO_ROOT / template["base_dir"]

    # Resolve directory name
    dir_name = template["naming"].format(**all_vars)
    target = base_dir / dir_name

    if target.exists():
        print(f"Error: {target} already exists.", file=sys.stderr)
        sys.exit(1)

    # Create directory and subdirs
    target.mkdir(parents=True)
    for subdir in template.get("subdirs", []):
        (target / subdir).mkdir(parents=True, exist_ok=True)

    # Write files with variable substitution
    for filename, content in template.get("files", {}).items():
        file_path = target / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content.format(**all_vars))

    return target


def main():
    config = load_config()
    templates = config.get("templates", {})

    parser = argparse.ArgumentParser(
        description="Create work directories from config-driven templates.",
    )
    parser.add_argument(
        "template",
        choices=list(templates.keys()) if templates else [],
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

    # Parse --var KEY=VALUE pairs
    variables: dict[str, str] = {}
    for var_str in args.var:
        if "=" not in var_str:
            print(f"Error: --var must be KEY=VALUE, got: {var_str}", file=sys.stderr)
            sys.exit(1)
        key, value = var_str.split("=", 1)
        variables[key] = value

    template = templates[args.template]
    required = template.get("required_vars", [])
    validate_vars(variables, required)

    result = scaffold(template, args.name, variables)
    print(f"Created {result.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scaffold.py -v`
Expected: PASS (all 6 tests)

**Step 5: Run linter**

Run: `uv run ruff check src/work_journal/scaffold.py tests/test_scaffold.py && uv run ruff format --check src/work_journal/scaffold.py tests/test_scaffold.py`
Expected: All checks passed

**Step 6: Commit**

```bash
git add src/work_journal/scaffold.py tests/test_scaffold.py
git commit -m "feat: add config-driven scaffold command"
```

---

### Task 7: Delete old template directories and dead code

**Files:**

- Delete: `work/sprint-notes/template-dir-sprint-name/` (entire directory)
- Delete: `work/progress-briefs/template-dir-quarter/` (entire directory)
- Delete: `src/work_journal/copy_template_dir.py`

**Step 1: Remove files**

```bash
git rm -r work/sprint-notes/template-dir-sprint-name/
git rm -r work/progress-briefs/template-dir-quarter/
git rm src/work_journal/copy_template_dir.py
```

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS (no test imported `copy_template_dir`)

**Step 3: Commit**

```bash
git commit -m "chore: remove physical template dirs and dead copy_template_dir.py"
```

---

### Task 8: Update CLAUDE.md

**Files:**

- Modify: `CLAUDE.md`

**Step 1: Update sprint notes workflow**

Replace step 1 in the "Sprint notes workflow" section. Change:

```markdown
1. Create sprint directory: `cp -r work/sprint-notes/template-dir-sprint-name work/sprint-notes/{sprint}`
2. Set `sprint_name` in `work/sprint-notes/{sprint}/sprint.yaml`
```

To:

```markdown
1. Scaffold sprint directory: `uv run python3 src/work_journal/scaffold.py sprint {sprint} --var sprint_name="{jira-sprint-name}"`
```

(Step 2 is gone — sprint name is set during scaffolding.)

Renumber remaining steps (old 3 becomes 2, etc.).

**Step 2: Update project structure section**

Add these lines to the project structure list:

```markdown
- `src/work_journal/paths.py` — Centralized path constants (repo root, config path, work dirs)
- `src/work_journal/config.py` — Shared config loading with env var resolution
- `src/work_journal/scaffold.py` — Config-driven directory scaffolding
```

Remove any mention of `template-dir-sprint-name`.

**Step 3: Verify no broken references**

Run: `grep -r "template-dir" CLAUDE.md .claude/skills/`
Expected: No matches

**Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for scaffold workflow and new modules"
```

---

### Task 9: Run full verification

**Step 1: Run all checks**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -v
```

Expected: All pass

**Step 2: Run pre-commit**

```bash
uv run pre-commit run --all-files
```

Expected: All pass

**Step 3: Verify scaffold works end-to-end**

```bash
uv run python3 src/work_journal/scaffold.py sprint test-sprint \
    --var sprint_name="Test-Sprint-Name"
```

Expected: Creates `work/sprint-notes/test-sprint/` with subdirs and files.

Verify the output:

```bash
ls work/sprint-notes/test-sprint/
cat work/sprint-notes/test-sprint/sprint.yaml
```

Expected: Shows subdirs (jira, github, git, etc.) and sprint.yaml with `sprint_name: "Test-Sprint-Name"`.

Clean up:

```bash
rm -rf work/sprint-notes/test-sprint
```

**Step 4: Verify collect.py still runs**

```bash
uv run python3 src/work_journal/collect.py --help
```

Expected: Shows help text

**Step 5: Verify standup.py still runs**

```bash
uv run python3 src/work_journal/standup.py --help
```

Expected: Shows help text
