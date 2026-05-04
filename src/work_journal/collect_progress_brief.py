"""Collect quarterly rollup data for progress brief drafting.

Aggregates sprint notes, annotations, impact metrics, and summary statistics
across all sprints in a quarter. Produces a rollup.md file that serves as the
primary input to the draft-progress-brief skill.

Usage:
    uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1
    uv run python3 src/work_journal/collect_progress_brief.py 2026-Q1 --dry-run
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from work_journal.config import load_shared_config
from work_journal.paths import PROGRESS_BRIEFS_DIR, SPRINT_NOTES_DIR
from work_journal.quarters import quarter_sprints


def find_sprint_note(sprint_dir: Path) -> Path | None:
    """Return the best available sprint note (prefer final.md over draft.md)."""
    for name in ("final.md", "draft.md"):
        path = sprint_dir / name
        if path.exists():
            return path
    return None


def load_annotations(sprint_dir: Path) -> list[dict]:
    """Load annotations.yaml if present, return list of accomplishments."""
    path = sprint_dir / "annotations.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return data.get("accomplishments", [])


def extract_headlines_from_markdown(text: str) -> list[dict]:
    """Fallback: extract H3 headlines and their parent H2 project from markdown."""
    accomplishments: list[dict] = []
    current_project = ""
    for line in text.splitlines():
        h2_match = re.match(r"^##\s+\*?\*?(.+?)\*?\*?\s*$", line)
        if h2_match:
            current_project = h2_match.group(1).strip("* ")
            continue
        h3_match = re.match(r"^###\s+\*?\*?(.+?)\*?\*?\s*$", line)
        if h3_match:
            accomplishments.append(
                {
                    "headline": h3_match.group(1).strip("* "),
                    "project": current_project,
                    "value_categories": [],
                    "summary": "",
                    "jira_keys": [],
                }
            )
    return accomplishments


def count_jira_issues(sprint_dir: Path) -> dict[str, dict[str, int]]:
    """Count Jira issues by project key, split into closed and incomplete.

    Returns {project_key: {"closed": N, "incomplete": N}}.
    """
    jira_dir = sprint_dir / "jira"
    if not jira_dir.exists():
        return {}

    closed_files = [
        "sprint-planned-completed.json",
        "sprint-added-completed.json",
        "between-sprints-completed.json",
        "non-sprint-completed.json",
    ]
    incomplete_files = [
        "sprint-planned-incomplete.json",
        "sprint-added-incomplete.json",
        "non-sprint-incomplete.json",
    ]

    counts: dict[str, dict[str, int]] = {}

    def tally(filenames: list[str], category: str) -> None:
        for filename in filenames:
            path = jira_dir / filename
            if not path.exists():
                continue
            try:
                with open(path) as f:
                    issues = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            for issue in issues:
                key = issue.get("key", "")
                project = key.split("-")[0] if "-" in key else "UNKNOWN"
                if project not in counts:
                    counts[project] = {"closed": 0, "incomplete": 0}
                counts[project][category] += 1

    tally(closed_files, "closed")
    tally(incomplete_files, "incomplete")
    return counts


def parse_claude_code_stats(sprint_dir: Path) -> tuple[int, str]:
    """Extract summary stats from claude-code/sessions.md.

    Returns (total_sessions, thinking_time_str).
    """
    sessions = 0
    thinking_time = ""
    for filename in ("claude-code/sessions.md", "claude-code/between-sprints-sessions.md"):
        path = sprint_dir / filename
        if not path.exists():
            continue
        text = path.read_text()
        sessions_match = re.search(r"\*\*Total sessions:\*\*\s*(\d+)", text)
        thinking_match = re.search(r"\*\*Claude thinking time:\*\*\s*(.+)", text)
        if sessions_match:
            sessions += int(sessions_match.group(1))
        if thinking_match and not thinking_time:
            thinking_time = thinking_match.group(1).strip()
    return sessions, thinking_time


def count_prs(sprint_dir: Path) -> dict[str, int]:
    """Count authored and reviewed PRs from prs.md files."""
    counts = {"authored": 0, "reviewed": 0}
    for filename in ("github/prs.md", "github/between-sprints-prs.md"):
        path = sprint_dir / filename
        if not path.exists():
            continue
        text = path.read_text()
        section = ""
        for line in text.splitlines():
            if line.startswith("## PRs Authored"):
                section = "authored"
            elif line.startswith("## PRs Reviewed"):
                section = "reviewed"
            elif section and re.match(r"^- \[#\d+", line):
                counts[section] += 1
    return counts


def read_enrichment_docs(sprint_dir: Path) -> list[str]:
    """Extract key document entries from google-docs enrichment."""
    path = sprint_dir / "google-docs" / "doc-summaries.md"
    if not path.exists():
        return []
    docs = []
    in_key_docs = False
    for line in path.read_text().splitlines():
        if line.startswith("## Key documents"):
            in_key_docs = True
            continue
        if in_key_docs and line.startswith("## "):
            break
        if in_key_docs and line.startswith("### "):
            docs.append(line.lstrip("# ").strip())
    return docs


def load_impact_metrics(brief_dir: Path) -> list[dict]:
    """Load impact-metrics.yaml if present."""
    path = brief_dir / "impact-metrics.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return data.get("metrics", [])


def format_rollup(
    quarter: str,
    sprints_found: list[str],
    sprints_missing: list[str],
    accomplishments_by_project: dict[str, list[dict]],
    impact_metrics: list[dict],
    jira_totals: dict[str, dict[str, int]],
    pr_totals: dict[str, int],
    cc_sessions: int,
    cc_thinking_time: str,
    key_docs: list[tuple[str, str]],
    value_category_counts: dict[str, int],
    project_names: dict[str, str],
) -> str:
    """Format the rollup markdown document."""
    lines: list[str] = []
    now = datetime.now(UTC).strftime("%Y-%m-%d")

    lines.append(f"# Quarterly Rollup: {quarter}")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Sprints covered:** {', '.join(sprints_found)}")
    if sprints_missing:
        lines.append(f"**Sprints missing:** {', '.join(sprints_missing)}")
    lines.append("")

    # Accomplishments by project
    lines.append("## Accomplishments by Project")
    lines.append("")
    for project, items in sorted(accomplishments_by_project.items()):
        lines.append(f"### {project}")
        lines.append("")
        for item in items:
            cats = item.get("value_categories", [])
            cat_str = f" [{', '.join(cats)}]" if cats else ""
            sprint = item.get("sprint", "")
            lines.append(f"- **{sprint}:** {item['headline']}{cat_str}")
        lines.append("")

    # Impact metrics
    if impact_metrics:
        lines.append("## Impact Metrics")
        lines.append("")
        lines.append("| Sprint | Project | Metric | Type |")
        lines.append("| --- | --- | --- | --- |")
        for m in impact_metrics:
            lines.append(
                f"| {m.get('sprint', '')} | {m.get('project', '')} "
                f"| {m.get('metric', '')} | {m.get('type', '')} |"
            )
        lines.append("")

    # Summary statistics
    total_closed = sum(v["closed"] for v in jira_totals.values())
    total_incomplete = sum(v["incomplete"] for v in jira_totals.values())

    lines.append("## Summary Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Sprints covered | {len(sprints_found)} |")
    lines.append(f"| Jira issues closed | {total_closed} |")
    lines.append(f"| Jira issues incomplete | {total_incomplete} |")
    lines.append(f"| PRs authored | {pr_totals.get('authored', 0)} |")
    lines.append(f"| PRs reviewed | {pr_totals.get('reviewed', 0)} |")
    if cc_sessions:
        lines.append(f"| Claude Code sessions | {cc_sessions} |")
    if cc_thinking_time:
        lines.append(f"| Claude Code thinking time | {cc_thinking_time} |")
    total_accomplishments = sum(len(v) for v in accomplishments_by_project.values())
    lines.append(f"| Key accomplishments | {total_accomplishments} |")
    lines.append("")

    # Issues by project
    if jira_totals:
        lines.append("### Issues by Project")
        lines.append("")
        lines.append("| Project | Closed | Incomplete |")
        lines.append("| --- | --- | --- |")
        for key in sorted(jira_totals.keys()):
            name = project_names.get(key, key)
            counts = jira_totals[key]
            lines.append(f"| {name} | {counts['closed']} | {counts['incomplete']} |")
        lines.append("")

    # Key documents
    if key_docs:
        lines.append("## Key Documents Produced")
        lines.append("")
        for sprint, title in key_docs:
            lines.append(f"- **{sprint}:** {title}")
        lines.append("")

    # Value category distribution
    if value_category_counts:
        lines.append("## Value Category Distribution")
        lines.append("")
        lines.append("| Category | Count |")
        lines.append("| --- | --- |")
        for cat, count in sorted(value_category_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect quarterly rollup data for progress brief drafting.",
    )
    parser.add_argument(
        "quarter",
        help="Quarter identifier (e.g., 2026-Q1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without writing output",
    )

    args = parser.parse_args()

    # Validate quarter format
    if not re.match(r"^\d{4}-Q[1-4]$", args.quarter):
        print(f"Error: Invalid quarter format '{args.quarter}'. Use YYYY-Q[1-4].", file=sys.stderr)
        sys.exit(1)

    shared_config = load_shared_config()
    project_names = shared_config.get("project_names", {})

    sprint_names = quarter_sprints(args.quarter)
    brief_dir = PROGRESS_BRIEFS_DIR / args.quarter

    print(f"Collecting quarterly rollup for {args.quarter}")
    print(f"  Sprints: {', '.join(sprint_names)}")
    print()

    # Check which sprint directories exist
    sprints_found = []
    sprints_missing = []
    for name in sprint_names:
        if (SPRINT_NOTES_DIR / name).exists():
            sprints_found.append(name)
        else:
            sprints_missing.append(name)

    if sprints_missing:
        print(f"  Missing sprint directories: {', '.join(sprints_missing)}")
    if not sprints_found:
        print("Error: No sprint directories found for this quarter.", file=sys.stderr)
        sys.exit(1)
    print(f"  Found: {', '.join(sprints_found)}")
    print()

    if args.dry_run:
        print("Dry run -- would collect:")
        for sprint in sprints_found:
            sprint_dir = SPRINT_NOTES_DIR / sprint
            note = find_sprint_note(sprint_dir)
            annotations_path = sprint_dir / "annotations.yaml"
            print(f"  {sprint}:")
            print(f"    Sprint note: {note.name if note else 'MISSING'}")
            has_ann = "yes" if annotations_path.exists() else "no (will parse headlines)"
            print(f"    Annotations: {has_ann}")
            print(f"    Jira data: {'yes' if (sprint_dir / 'jira').exists() else 'no'}")
            print(f"    GitHub data: {'yes' if (sprint_dir / 'github').exists() else 'no'}")
            print(f"    Claude Code: {'yes' if (sprint_dir / 'claude-code').exists() else 'no'}")
            enrichment = sprint_dir / "enrichment-summary.md"
            print(f"    Enrichment: {'yes' if enrichment.exists() else 'no'}")
        print(f"\n  Output: {brief_dir / 'rollup.md'}")
        return

    # Collect data from each sprint
    accomplishments_by_project: dict[str, list[dict]] = {}
    jira_totals: dict[str, dict[str, int]] = {}
    pr_totals: dict[str, int] = {"authored": 0, "reviewed": 0}
    cc_sessions_total = 0
    cc_thinking_time_last = ""
    key_docs: list[tuple[str, str]] = []
    value_category_counts: dict[str, int] = {}

    for sprint in sprints_found:
        sprint_dir = SPRINT_NOTES_DIR / sprint
        print(f"Processing {sprint}...")

        # Sprint note + annotations
        note_path = find_sprint_note(sprint_dir)
        annotations = load_annotations(sprint_dir)

        if annotations:
            print(f"  Loaded {len(annotations)} annotations")
            items = annotations
        elif note_path:
            text = note_path.read_text()
            items = extract_headlines_from_markdown(text)
            print(f"  No annotations.yaml, extracted {len(items)} headlines from {note_path.name}")
        else:
            items = []
            print("  No sprint note found")

        for item in items:
            item["sprint"] = sprint
            project = item.get("project", "Other")
            accomplishments_by_project.setdefault(project, []).append(item)
            for cat in item.get("value_categories", []):
                value_category_counts[cat] = value_category_counts.get(cat, 0) + 1

        # Jira issue counts
        sprint_jira = count_jira_issues(sprint_dir)
        for key, counts in sprint_jira.items():
            if key not in jira_totals:
                jira_totals[key] = {"closed": 0, "incomplete": 0}
            jira_totals[key]["closed"] += counts["closed"]
            jira_totals[key]["incomplete"] += counts["incomplete"]

        # PR counts
        sprint_prs = count_prs(sprint_dir)
        pr_totals["authored"] += sprint_prs["authored"]
        pr_totals["reviewed"] += sprint_prs["reviewed"]

        # Claude Code stats
        sessions, thinking_time = parse_claude_code_stats(sprint_dir)
        cc_sessions_total += sessions
        if thinking_time:
            cc_thinking_time_last = thinking_time

        # Enrichment docs
        docs = read_enrichment_docs(sprint_dir)
        for title in docs:
            key_docs.append((sprint, title))

    print()

    # Load impact metrics from the brief directory
    impact_metrics = load_impact_metrics(brief_dir) if brief_dir.exists() else []

    # Format and write rollup
    rollup = format_rollup(
        quarter=args.quarter,
        sprints_found=sprints_found,
        sprints_missing=sprints_missing,
        accomplishments_by_project=accomplishments_by_project,
        impact_metrics=impact_metrics,
        jira_totals=jira_totals,
        pr_totals=pr_totals,
        cc_sessions=cc_sessions_total,
        cc_thinking_time=cc_thinking_time_last,
        key_docs=key_docs,
        value_category_counts=value_category_counts,
        project_names=project_names,
    )

    brief_dir.mkdir(parents=True, exist_ok=True)
    output_path = brief_dir / "rollup.md"
    output_path.write_text(rollup)
    print(f"Wrote {output_path}")
    print()
    print("Next steps:")
    print(f"  1. Copy form PDFs to {brief_dir / 'format/'}")
    print(f"  2. Run /draft-progress-brief {args.quarter}")


if __name__ == "__main__":
    main()
