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

    base_dir = base_override if base_override is not None else REPO_ROOT / template["base_dir"]

    dir_name = template["naming"].format(**all_vars)
    target = base_dir / dir_name

    if target.exists():
        print(f"Error: {target} already exists.", file=sys.stderr)
        sys.exit(1)

    target.mkdir(parents=True)
    for subdir in template.get("subdirs", []):
        (target / subdir).mkdir(parents=True, exist_ok=True)

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
