"""Summarize Jira issue JSON exports for sprint notes.

Reads the standard set of Jira JSON files from a sprint directory and prints
a compact summary to stdout. Used by the draft-sprint-notes and
enrich-sprint-data skills.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FILES = [
    ("jira/sprint-planned-completed.json", "planned-completed"),
    ("jira/sprint-planned-incomplete.json", "planned-incomplete"),
    ("jira/sprint-added-completed.json", "added-completed"),
    ("jira/sprint-added-incomplete.json", "added-incomplete"),
    ("jira/non-sprint-completed.json", "non-sprint-completed"),
    ("jira/non-sprint-incomplete.json", "non-sprint-incomplete"),
    ("jira/non-sprint-non-assigned-with-worklog.json", "non-sprint-worklog"),
]

DOC_URL_PATTERN = re.compile(r"https://docs\.google\.com/[^\s\"\\)]+")


def summarize(sprint_dir: Path, *, doc_urls: bool = False) -> None:
    """Print a summary of all Jira issue files in *sprint_dir*."""
    for filename, label in FILES:
        path = sprint_dir / filename
        if not path.exists():
            print(f"=== {label} (file not found) ===")
            print()
            continue

        with open(path) as f:
            issues = json.load(f)

        print(f"=== {label} ({len(issues)} issues) ===")
        for issue in issues:
            fields = issue.get("fields", {})
            key = issue.get("key", "?")
            summary = fields.get("summary", "?")
            priority = (fields.get("priority") or {}).get("name", "?")
            itype = (fields.get("issuetype") or {}).get("name", "?")
            reporter = (fields.get("reporter") or {}).get("displayName", "?")
            status = (fields.get("status") or {}).get("name", "?")
            print(
                f"  {key}: [{itype}/{priority}] {summary} (status: {status}, reporter: {reporter})"
            )
            if doc_urls:
                desc = json.dumps(fields.get("description", "") or "")
                urls = DOC_URL_PATTERN.findall(desc)
                if urls:
                    print(f"    Doc URLs: {urls}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize Jira issue JSON exports for a sprint.",
    )
    parser.add_argument(
        "sprint_dir",
        help="Path to the sprint directory (e.g. work/sprint-notes/2026-02-A)",
    )
    parser.add_argument(
        "--doc-urls",
        action="store_true",
        help="Extract Google Doc/Sheet URLs from issue descriptions",
    )
    args = parser.parse_args()

    sprint_path = Path(args.sprint_dir)
    if not sprint_path.is_dir():
        print(f"Error: {sprint_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    summarize(sprint_path, doc_urls=args.doc_urls)


if __name__ == "__main__":
    main()
