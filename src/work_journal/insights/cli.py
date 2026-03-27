"""CLI entry point for parsing insights HTML reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from work_journal.insights.parse import parse_insights_html
from work_journal.paths import (
    INSIGHTS_PARSED_DIR,
    INSIGHTS_RAW_DIR,
    SHARED_CONFIG_PATH,
)


def run_parse(
    sprint: str,
    raw_dir: Path,
    parsed_dir: Path,
    keywords: dict,
) -> Path:
    """Parse a raw insights HTML file into classified JSON.

    Returns the path to the output JSON file.
    Raises FileNotFoundError if the raw HTML doesn't exist.
    """
    raw_path = raw_dir / f"{sprint}.html"
    if not raw_path.exists():
        raise FileNotFoundError(f"No raw insights file at {raw_path}")

    html = raw_path.read_text()
    result = parse_insights_html(
        html,
        keywords.get("work_keywords", []),
        keywords.get("personal_keywords", []),
    )

    parsed_dir.mkdir(parents=True, exist_ok=True)
    output_path = parsed_dir / f"{sprint}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a Claude Code insights HTML report into classified JSON.",
    )
    parser.add_argument(
        "sprint",
        help="Sprint identifier (e.g., 2026-03-A)",
    )
    args = parser.parse_args()

    # Load keywords from shared config
    config = yaml.safe_load(SHARED_CONFIG_PATH.read_text())
    keywords = config.get("insights", {})

    output_path = run_parse(args.sprint, INSIGHTS_RAW_DIR, INSIGHTS_PARSED_DIR, keywords)
    print(f"Parsed: {output_path}")
    print(f"Next: run /clean-insights {args.sprint}")


if __name__ == "__main__":
    main()
