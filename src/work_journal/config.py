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
