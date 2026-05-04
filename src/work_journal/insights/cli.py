"""CLI entry point for parsing insights HTML reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from work_journal.insights.parse import extract_date_range, parse_insights_html
from work_journal.paths import (
    INSIGHTS_PARSED_DIR,
    INSIGHTS_RAW_DIR,
    SHARED_CONFIG_PATH,
)


def run_parse(
    raw_path: Path,
    parsed_dir: Path,
    keywords: dict,
) -> Path:
    """Parse a raw insights HTML file into classified JSON.

    Output filename is derived from the date range in the HTML subtitle:
    `{start}_to_{end}.json` (e.g., `2026-03-16_to_2026-04-15.json`).

    Returns the path to the output JSON file.
    Raises FileNotFoundError if the raw HTML doesn't exist.
    Raises ValueError if the date range cannot be extracted.
    """
    if not raw_path.exists():
        raise FileNotFoundError(f"No raw insights file at {raw_path}")

    html = raw_path.read_text()
    date_range = extract_date_range(html)
    if not date_range:
        raise ValueError(
            f"Could not extract date range from {raw_path}. "
            "Expected 'YYYY-MM-DD to YYYY-MM-DD' in the report subtitle."
        )
    start, end = date_range

    result = parse_insights_html(
        html,
        keywords.get("work_keywords", []),
        keywords.get("personal_keywords", []),
    )

    parsed_dir.mkdir(parents=True, exist_ok=True)
    output_path = parsed_dir / f"{start}-to-{end}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a Claude Code insights HTML report into classified JSON.",
    )
    parser.add_argument(
        "raw_file",
        help=(
            "Path to raw HTML, or filename within work/shared/insights/raw/ "
            "(e.g., '2026-03-16-to-2026-04-15.html')"
        ),
    )
    args = parser.parse_args()

    # Resolve raw path: accept either an absolute/relative path or a bare filename
    raw_path = Path(args.raw_file)
    if not raw_path.is_absolute() and not raw_path.exists():
        candidate = INSIGHTS_RAW_DIR / args.raw_file
        if candidate.exists():
            raw_path = candidate

    # Load keywords from shared config
    config = yaml.safe_load(SHARED_CONFIG_PATH.read_text())
    keywords = config.get("insights", {})

    try:
        output_path = run_parse(raw_path, INSIGHTS_PARSED_DIR, keywords)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    range_id = output_path.stem
    print(f"Parsed: {output_path}")
    print(f"Next: run /clean-insights {range_id}")


if __name__ == "__main__":
    main()
