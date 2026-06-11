# Python Project Setup Plan

## Context

The work-journal repo has Python scripts in `src/` with a minimal `pyproject.toml` (metadata + 3 runtime deps only). It's missing standard dev tooling: linting, formatting, type checking, testing, pre-commit hooks, and CI. This plan adds all of that and reorganizes the source into an installable package.

The user wants this to be an installable tool eventually, but doesn't need CLI entry points yet. So we'll reorganize into `src/work_journal/` with hatchling build-system now, and add `[project.scripts]` later.

## Steps

### 1. Reorganize source into `src/work_journal/`

Move existing files from `src/` into `src/work_journal/`, preserving subdirectory structure.

Update `SRC_DIR` constant in `collect.py` and `standup.py` to `REPO_ROOT / "src" / "work_journal"`.

Update CLAUDE.md and skills to reference the new paths.

### 2. Update `pyproject.toml`

- Add `[build-system]` with hatchling
- Add `[dependency-groups]` dev group: ruff, mypy, pytest, pytest-cov, pre-commit
- Add `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`

### 3. Run ruff format + fix on existing code

### 4. Create `tests/` directory with smoke test

### 5. Create `.pre-commit-config.yaml`

### 6. Create `.github/workflows/ci.yml`

### 7. Update `.gitignore`

### 8. Update `CLAUDE.md`

## Verification

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest
uv run pre-commit run --all-files
uv run python3 src/work_journal/collect.py --help
```
