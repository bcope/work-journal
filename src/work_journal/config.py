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
