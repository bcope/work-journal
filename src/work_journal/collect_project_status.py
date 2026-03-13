"""Collect project status data from GitHub, Jira, and Google Calendar.

Reads work/project-status/config.yaml for repo defaults and
work/project-status/project-configs/<project>.yaml for per-project settings.
Writes output to work/project-status/<project>/<date>[-n]/.

Usage:
    uv run python3 src/work_journal/collect_project_status.py ggdisburse --since 2026-02-01
    uv run python3 src/work_journal/collect_project_status.py ggdisburse
    uv run python3 src/work_journal/collect_project_status.py ggdisburse --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from work_journal.config import resolve_env_vars
from work_journal.paths import (
    PROJECT_CONFIGS_DIR,
    PROJECT_STATUS_CONFIG_PATH,
    PROJECT_STATUS_DIR,
    REPO_ROOT,
)


def load_config() -> dict:
    """Load the repo-level project-status config with env var resolution."""
    if not PROJECT_STATUS_CONFIG_PATH.exists():
        print(f"Error: Config not found at {PROJECT_STATUS_CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(PROJECT_STATUS_CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return resolve_env_vars(config)


def load_project_config(project_name: str) -> dict:
    """Load a project-level config."""
    project_yaml = PROJECT_CONFIGS_DIR / f"{project_name}.yaml"
    if not project_yaml.exists():
        print(
            f"Error: Project config not found at {project_yaml}\nAvailable projects:",
            file=sys.stderr,
        )
        for p in sorted(PROJECT_CONFIGS_DIR.glob("*.yaml")):
            if p.name != ".gitkeep":
                print(f"  {p.stem}", file=sys.stderr)
        sys.exit(1)
    with open(project_yaml) as f:
        return yaml.safe_load(f)


def resolve_run_dir(project_dir: Path, date_str: str) -> Path:
    """Resolve the run directory, adding -N suffix if date dir already exists."""
    base = project_dir / date_str
    if not base.exists():
        return base
    n = 2
    while (project_dir / f"{date_str}-{n}").exists():
        n += 1
    return project_dir / f"{date_str}-{n}"


def collect_github_prs(
    run_dir: Path, project_config: dict, config: dict, since: str, until: str
) -> None:
    """Collect GitHub PR data for each repo in the project config."""
    gh_config = project_config.get("github", {})
    repos = gh_config.get("repos", [])
    output_format = config.get("github", {}).get("format", "markdown")
    output_path = run_dir / "github" / "prs.md"

    if not repos:
        print("  No GitHub repos configured, skipping.")
        return

    from work_journal.github.query_github_prs import search_repo_prs

    all_prs: list[dict] = []
    for repo in repos:
        print(f"  GitHub PRs: {repo}, {since} to {until}")
        prs = search_repo_prs(repo, since, until)
        all_prs.extend(prs)

    if all_prs:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "markdown":
            from work_journal.github.query_github_prs import _format_markdown

            content = _format_markdown(all_prs, [])
        else:
            content = json.dumps(all_prs, indent=2) + "\n"
        with open(output_path, "w") as f:
            f.write(content)
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({len(all_prs)} PRs)")
    else:
        print("  No PRs found.")


def collect_jira_issues(
    run_dir: Path, project_config: dict, since: str | None, until: str | None
) -> None:
    """Run the project's Jira queries via the query_issues.py script."""
    queries = project_config.get("jira", {}).get("queries", {})
    if not queries:
        print("  No Jira queries configured, skipping.")
        return

    for name, jql in queries.items():
        if since and until:
            jql = jql.replace("{start_date}", since).replace("{end_date}", until)

        output_path = run_dir / "jira" / f"{name}.json"
        print(f"  Jira query '{name}': {jql}")

        cmd = [
            sys.executable,
            str(REPO_ROOT / "src" / "work_journal" / "jira" / "query_issues.py"),
            jql,
            "--pretty",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(
                f"  Warning: Jira query '{name}' failed (exit {result.returncode})",
                file=sys.stderr,
            )
            if result.stderr:
                print(f"  {result.stderr.strip()}", file=sys.stderr)
            continue

        if result.stdout.strip():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(result.stdout)
            try:
                count = len(json.loads(result.stdout))
                print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({count} issues)")
            except json.JSONDecodeError:
                print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_calendar_events(run_dir: Path, project_config: dict, since: str, until: str) -> None:
    """Collect calendar events matching project keywords."""
    cal_config = project_config.get("calendar", {})
    calendar_ids = cal_config.get("calendar_ids", [])
    keywords = cal_config.get("keywords", [])

    if not calendar_ids:
        print("  No calendar IDs configured, skipping.")
        return

    output_path = run_dir / "calendar" / "events.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "src" / "work_journal" / "calendar" / "query_events.py"),
        "--since",
        since,
        "--until",
        until,
    ]
    for cal_id in calendar_ids:
        cmd.extend(["--calendar-id", cal_id])
    if keywords:
        cmd.extend(["--keywords", *keywords])
    cmd.append("--pretty")

    print(f"  Calendar events: {since} to {until}, keywords={keywords}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Warning: Calendar query failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return

    if result.stdout.strip():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result.stdout)
        try:
            count = len(json.loads(result.stdout))
            print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({count} events)")
        except json.JSONDecodeError:
            print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(
        description="Collect project status data from GitHub, Jira, and Calendar.",
    )
    parser.add_argument(
        "project",
        help="Project config name (matches project-configs/<name>.yaml)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Start date (YYYY-MM-DD). If omitted, uses project's default_days.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without running queries",
    )

    args = parser.parse_args()
    today = date.today().isoformat()

    config = load_config()
    project_config = load_project_config(args.project)

    # Resolve dates
    if args.since:
        since = args.since
        mode = "date-range"
    else:
        default_days = project_config.get("github", {}).get("default_days", 30)
        since = (date.today() - timedelta(days=default_days)).isoformat()
        mode = "overview"

    until = today

    print(f"Project: {project_config.get('name', args.project)}")
    print(f"Mode: {mode}")
    print(f"Date range: {since} to {until}")
    print()

    # Create run directory
    project_dir = PROJECT_STATUS_DIR / args.project
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = resolve_run_dir(project_dir, today)

    if args.dry_run:
        print(f"Dry run — would create: {run_dir.relative_to(REPO_ROOT)}")
        gh_repos = project_config.get("github", {}).get("repos", [])
        print(f"  GitHub repos: {gh_repos}")
        jira_queries = project_config.get("jira", {}).get("queries", {})
        for name, jql in jira_queries.items():
            print(f"  Jira '{name}': {jql}")
        if mode != "overview":
            cal_config = project_config.get("calendar", {})
            print(
                f"  Calendar: ids={cal_config.get('calendar_ids', [])},"
                f" keywords={cal_config.get('keywords', [])}"
            )
        else:
            print("  Calendar: skipped (overview mode)")
        return

    run_dir.mkdir(parents=True)
    print(f"Run directory: {run_dir.relative_to(REPO_ROOT)}")
    print()

    # Write run metadata
    run_meta = {
        "project": args.project,
        "project_name": project_config.get("name", args.project),
        "mode": mode,
        "since": since,
        "until": until,
        "generated": today,
    }
    run_yaml_path = run_dir / "run.yaml"
    with open(run_yaml_path, "w") as f:
        yaml.dump(run_meta, f, default_flow_style=False)
    print(f"Wrote {run_yaml_path.relative_to(REPO_ROOT)}")
    print()

    # Collect GitHub PRs
    print("Collecting GitHub PRs...")
    collect_github_prs(run_dir, project_config, config, since, until)
    print()

    # Collect Jira issues
    print("Collecting Jira issues...")
    jira_since = since if mode == "date-range" else None
    jira_until = until if mode == "date-range" else None
    collect_jira_issues(run_dir, project_config, jira_since, jira_until)
    print()

    # Collect calendar events (skip in overview mode)
    if mode == "overview":
        print("Skipping calendar events (overview mode).")
    else:
        print("Collecting calendar events...")
        collect_calendar_events(run_dir, project_config, since, until)
    print()

    print("Done. Data collected to:")
    print(f"  {run_dir.relative_to(REPO_ROOT)}/")
    print()
    print("Next step:")
    print(f"  Run /project-status {args.project} to draft from this data")
    print(
        f"  Or re-collect with:"
        f" uv run python3 src/work_journal/collect_project_status.py {args.project} --since {since}"
    )


if __name__ == "__main__":
    main()
