#!/usr/bin/env python3
"""
Parse a Jira CSV export and produce a clean summary of issues.

Usage:
    python3 parse_jira_csv.py <path-to-csv> [--output <output-file>]

Examples:
    python3 parse_jira_csv.py ../progress-briefs/2025-Q4/jira-issues/2025-Q4-assigned-jira-issues.csv
    python3 parse_jira_csv.py issues.csv --output summary.md
"""

import argparse
import csv
from collections import Counter


def parse_jira_csv(csv_path):
    """Parse a Jira CSV export and return structured issue data."""
    issues = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            issues.append(
                {
                    "summary": row.get("Summary", "").strip(),
                    "key": row.get("Issue key", "").strip(),
                    "issue_type": row.get("Issue Type", "").strip(),
                    "status": row.get("Status", "").strip(),
                    "project_key": row.get("Project key", "").strip(),
                    "project_name": row.get("Project name", "").strip(),
                    "priority": row.get("Priority", "").strip(),
                    "created": row.get("Created", "").strip(),
                    "updated": row.get("Updated", "").strip(),
                    "resolved": row.get("Resolved", "").strip(),
                }
            )
    return issues


def summarize_issues(issues):
    """Produce summary statistics from parsed issues."""
    project_counts = Counter(i["project_key"] for i in issues)
    status_counts = Counter(i["status"] for i in issues)
    type_counts = Counter(i["issue_type"] for i in issues)
    return {
        "total": len(issues),
        "by_project": dict(project_counts.most_common()),
        "by_status": dict(status_counts.most_common()),
        "by_type": dict(type_counts.most_common()),
    }


def render_markdown(issues, summary):
    """Render issues and summary as Markdown."""
    lines = []
    lines.append(f"# Jira Issues Summary ({summary['total']} issues)\n")

    lines.append("## By Project\n")
    lines.append("| Project | Count |")
    lines.append("| ------- | ----- |")
    for project, count in sorted(
        summary["by_project"].items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {project} | {count} |")
    lines.append("")

    lines.append("## By Status\n")
    lines.append("| Status | Count |")
    lines.append("| ------ | ----- |")
    for status, count in sorted(summary["by_status"].items(), key=lambda x: -x[1]):
        lines.append(f"| {status} | {count} |")
    lines.append("")

    lines.append("## By Issue Type\n")
    lines.append("| Type | Count |")
    lines.append("| ---- | ----- |")
    for issue_type, count in sorted(
        summary["by_type"].items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {issue_type} | {count} |")
    lines.append("")

    lines.append("## All Issues\n")
    lines.append("| Key | Type | Status | Project | Summary |")
    lines.append("| --- | ---- | ------ | ------- | ------- |")
    for i in sorted(issues, key=lambda x: x["project_key"]):
        truncated = i["summary"][:100]
        lines.append(
            f"| {i['key']} | {i['issue_type']} | {i['status']} "
            f"| {i['project_key']} | {truncated} |"
        )
    lines.append("")

    return "\n".join(lines)


def render_plain(issues, summary):
    """Render issues and summary as plain text."""
    lines = []
    lines.append(f"Total issues: {summary['total']}\n")

    lines.append("By project:")
    for project, count in sorted(
        summary["by_project"].items(), key=lambda x: -x[1]
    ):
        lines.append(f"  {project}: {count}")
    lines.append("")

    lines.append("By status:")
    for status, count in sorted(summary["by_status"].items(), key=lambda x: -x[1]):
        lines.append(f"  {status}: {count}")
    lines.append("")

    lines.append("All issues:")
    for i in sorted(issues, key=lambda x: x["project_key"]):
        truncated = i["summary"][:100]
        lines.append(f"  {i['key']}\t{i['issue_type']}\t{i['status']}\t{truncated}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Parse a Jira CSV export and produce a summary."
    )
    parser.add_argument("csv_path", help="Path to the Jira CSV export file")
    parser.add_argument(
        "--output", "-o", help="Output file path (default: stdout)", default=None
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["markdown", "plain"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    issues = parse_jira_csv(args.csv_path)
    summary = summarize_issues(issues)

    if args.format == "markdown":
        output = render_markdown(issues, summary)
    else:
        output = render_plain(issues, summary)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
