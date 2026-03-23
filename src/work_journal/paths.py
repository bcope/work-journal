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
load_dotenv(REPO_ROOT / ".env", override=True)
