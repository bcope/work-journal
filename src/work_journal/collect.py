"""Collect all sprint data based on repo-level and sprint-level config.

Reads work/sprint-notes/config.yaml for repo defaults and
work/sprint-notes/{sprint}/sprint.yaml for the sprint name. Resolves the sprint
name to dates via the Jira Agile API, then runs all configured data collection
steps and writes outputs to the sprint directory.

Usage:
    uv run python3 src/work_journal/collect.py 2026-02-A
    uv run python3 src/work_journal/collect.py 2026-02-A --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

from work_journal.config import load_sprint_config, load_sprint_notes_config
from work_journal.dates import resolve_window_bound
from work_journal.git.query_git_log import find_git_repos, get_commits
from work_journal.git.query_git_log import format_markdown as format_git_markdown
from work_journal.github.query_github_prs import (
    GhError,
    search_authored_prs,
    search_reviewed_prs,
)
from work_journal.github.query_github_prs import (
    _format_markdown as format_pr_markdown,
)
from work_journal.insights.lookup import find_matching_insights
from work_journal.jira.query_issues import search_issues
from work_journal.jira.query_sprint_info import (
    _make_session,
    find_previous_sprint,
    find_sprint_by_name,
)
from work_journal.paths import INSIGHTS_CLEANED_DIR, REPO_ROOT, SPRINT_NOTES_DIR, SRC_DIR


def run_helper(script: str, args: list[str], output_path: Path | None = None) -> str:
    """Run a helper script via uv run and return stdout.

    If output_path is given, write stdout to that file instead of returning it.
    """
    cmd = [sys.executable, str(SRC_DIR / script), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Warning: {script} failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return ""

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(result.stdout)
        return result.stdout

    return result.stdout


def resolve_sprint(sprint_config: dict) -> tuple[dict, requests.Session, int]:
    """Resolve sprint name to full sprint metadata via Jira API.

    Returns (sprint_info, session, board_id) so callers can reuse the session.
    """
    board_id = int(sprint_config.get("board_id", os.environ["JIRA_BOARD_ID"]))
    sprint_name = sprint_config["sprint_name"]

    session = _make_session()
    result = find_sprint_by_name(session, board_id, sprint_name)
    if result is None:
        print(
            f"Error: Could not find sprint '{sprint_name}' on board {board_id}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return result, session, board_id


def extract_dates(sprint_info: dict) -> tuple[str, str]:
    """Extract YYYY-MM-DD start and end dates from sprint info."""
    start = sprint_info["startDate"][:10]
    end = sprint_info["endDate"][:10]
    return start, end


def compute_windows(
    sprint_info: dict, prior_sprint: dict | None
) -> tuple[datetime, datetime, datetime | None, datetime | None]:
    """Datetime collection windows, half-open [since, until).

    Sprint: local midnight of the start day -> sprint close instant
    (completeDate, falling back to endDate). Between: prior sprint close
    instant -> local midnight of the start day; None/None when empty. The
    windows chain without overlap, so no activity is counted twice.
    """
    start_dt = resolve_window_bound(sprint_info["startDate"])
    sprint_since = start_dt.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    sprint_until = resolve_window_bound(sprint_info.get("completeDate") or sprint_info["endDate"])
    between_since = between_until = None
    if prior_sprint:
        raw = prior_sprint.get("completeDate") or prior_sprint.get("endDate")
        if raw:
            prior_close = resolve_window_bound(raw)
            if prior_close < sprint_since:
                between_since, between_until = prior_close, sprint_since
    return sprint_since, sprint_until, between_since, between_until


def template_jql(jql_template: str, variables: dict) -> str:
    """Replace placeholders in a JQL template."""
    result = jql_template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def collect_jira_sprint_info(sprint_dir: Path, sprint_info: dict) -> None:
    """Save sprint info JSON."""
    output_path = sprint_dir / "jira" / "sprint-info.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(sprint_info, f, indent=2)
        f.write("\n")
    print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_jira_issues(sprint_dir: Path, queries: dict, variables: dict) -> None:
    """Run all configured Jira JQL queries."""
    for name, query_config in queries.items():
        raw_jql = query_config["jql"]
        if raw_jql == "TODO":
            print(f"  Skipping '{name}' (JQL is TODO)")
            continue
        jql = template_jql(raw_jql, variables)
        output_file = query_config["output"]
        output_path = sprint_dir / output_file

        print(f"  Jira query '{name}': {jql}")
        try:
            issues = search_issues(jql)
        except Exception as e:
            print(f"  Warning: Jira query '{name}' failed: {e}", file=sys.stderr)
            continue

        if issues:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(issues, f, indent=2)
                f.write("\n")
            print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({len(issues)} issues)")


def collect_github_prs(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    """Collect GitHub PR data."""
    gh_config = config.get("github", {})
    org = os.environ.get("GITHUB_ORG", "")
    output_file = gh_config.get("output", "github/prs.md")
    output_format = gh_config.get("format", "markdown")
    output_path = sprint_dir / output_file

    print(f"  GitHub PRs: org={org}, {start_date} to {end_date}")
    try:
        authored = search_authored_prs(start_date, end_date, org)
        reviewed = search_reviewed_prs(start_date, end_date, org)
    except GhError as e:
        print(f"  Warning: GitHub PR query failed: {e}", file=sys.stderr)
        return

    # Deduplicate: remove from reviewed any PRs also in authored
    authored_urls = {pr.get("url") for pr in authored}
    reviewed = [pr for pr in reviewed if pr.get("url") not in authored_urls]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        content = format_pr_markdown(authored, reviewed)
    else:
        indent = 2
        result = {"authored": authored, "reviewed": reviewed}
        content = json.dumps(result, indent=indent) + "\n"
    with open(output_path, "w") as f:
        f.write(content)
    print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_git_commits(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    """Collect local git commit data."""
    git_config = config.get("git", {})
    repos_dir = os.path.expanduser(os.environ.get("GIT_REPOS_DIR", "~/git"))
    author = os.environ.get("GIT_AUTHOR", "")
    output_file = git_config.get("output", "git/commit-log.md")
    output_path = sprint_dir / output_file

    print(f"  Git commits: repos_dir={repos_dir}, author={author}")
    if not os.path.isdir(repos_dir):
        print(f"  Warning: {repos_dir} is not a directory, skipping.", file=sys.stderr)
        return

    repos = find_git_repos(repos_dir)
    results: dict[str, list[str]] = {}
    for repo_path in repos:
        repo_name = os.path.basename(repo_path)
        commits = get_commits(repo_path, author, start_date, end_date)
        if commits:
            results[repo_name] = commits

    content = format_git_markdown(results, start_date, end_date, author)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(content)
    print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_claude_code_activity(
    sprint_dir: Path,
    config: dict,
    start_date: str,
    end_date: str,
    raw_prefix: str = "",
    skip_stats_cache: bool = False,
) -> None:
    """Collect Claude Code session activity data."""
    cc_config = config.get("claude_code", {})
    history_path = os.path.expanduser(
        os.environ.get("CLAUDE_HISTORY_PATH", "~/.claude/history.jsonl")
    )
    stats_cache_path = os.path.expanduser(
        os.environ.get("CLAUDE_STATS_CACHE_PATH", "~/.claude/stats-cache.json")
    )
    projects_path = os.path.expanduser(os.environ.get("CLAUDE_PROJECTS_PATH", "~/.claude/projects"))
    work_dirs = [os.path.expanduser(os.environ.get("CLAUDE_WORK_DIRS", "~/git"))]
    output_file = cc_config.get("output", "claude-code/sessions.md")
    docs_output_file = cc_config.get("documents_output", "claude-code/documents.md")
    tokens_output_file = cc_config.get("tokens_output", "claude-code/tokens-by-day.json")
    output_path = sprint_dir / output_file
    docs_output_path = sprint_dir / docs_output_file
    tokens_output_path = sprint_dir / tokens_output_file
    raw_dir = sprint_dir / "claude-code"

    helper_args = [
        "--since",
        start_date,
        "--until",
        end_date,
        "--history-path",
        history_path,
        "--stats-cache-path",
        stats_cache_path,
        "--projects-path",
        projects_path,
        "--copy-raw",
        str(raw_dir),
        "--documents-output",
        str(docs_output_path),
        "--tokens-output",
        str(tokens_output_path),
    ]
    for wd in work_dirs:
        helper_args.extend(["--work-dirs", wd])
    if raw_prefix:
        helper_args.extend(["--raw-prefix", raw_prefix])
    if skip_stats_cache:
        helper_args.append("--skip-stats-cache")

    print(f"  Claude Code activity: {start_date} to {end_date}")
    run_helper(
        "claude_code/collect_activity.py",
        helper_args,
        output_path=output_path,
    )
    if output_path.exists():
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def ensure_sprint_dir(sprint_name: str) -> Path:
    """Return the sprint directory path, erroring if it doesn't exist."""
    sprint_dir = SPRINT_NOTES_DIR / sprint_name
    if not sprint_dir.exists():
        print(
            f"Error: Sprint directory {sprint_dir.relative_to(REPO_ROOT)} does not exist.\n"
            f"Create it first with: uv run python3 src/work_journal/scaffold.py"
            f' sprint {sprint_name} --var sprint_name="YOUR-SPRINT-NAME"',
            file=sys.stderr,
        )
        sys.exit(1)
    return sprint_dir


def main():
    parser = argparse.ArgumentParser(
        description="Collect all sprint data. Reads config.yaml and sprint.yaml.",
    )
    parser.add_argument(
        "sprint",
        help="Sprint directory name (e.g., 2026-02-A)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without running queries",
    )

    args = parser.parse_args()

    config = load_sprint_notes_config()
    sprint_dir = ensure_sprint_dir(args.sprint)

    # Check for sprint.yaml
    sprint_yaml_path = sprint_dir / "sprint.yaml"
    if not sprint_yaml_path.exists():
        print(
            f"Error: No sprint.yaml found in {sprint_dir.relative_to(REPO_ROOT)}.\n"
            f"Create one with at least:\n"
            f'  sprint_name: "your-sprint-name-here"',
            file=sys.stderr,
        )
        sys.exit(1)

    sprint_config = load_sprint_config(sprint_dir)

    # Resolve sprint to get dates and ID
    print(f"Resolving sprint: {sprint_config['sprint_name']}")
    sprint_info, session, board_id = resolve_sprint(sprint_config)
    start_date, end_date = extract_dates(sprint_info)
    sprint_id = sprint_info["id"]
    print(f"  Sprint ID: {sprint_id}")
    print(f"  Dates: {start_date} to {end_date}")

    # Check for a cleaned insights report whose date range overlaps the sprint
    matching_insights = find_matching_insights(start_date, end_date, INSIGHTS_CLEANED_DIR)
    if not matching_insights:
        print(
            f"\nError: No cleaned insights report overlaps {start_date} to {end_date}.\n"
            f"  1. Run /insights in Claude Code to generate a usage report\n"
            f"  2. Copy the HTML to work/shared/insights/raw/ "
            f"(any filename — date range comes from the report)\n"
            f"  3. Run: uv run python3 src/work_journal/insights/cli.py "
            f"<raw filename>\n"
            f"  4. Run: /clean-insights <date-range-id>\n"
            f"Then re-run collect.py.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"  Insights: {', '.join(p.name for p in matching_insights)}")

    # Find previous sprint to capture between-sprints work
    prior_sprint = find_previous_sprint(session, board_id, sprint_info)
    sprint_since, sprint_until, between_since, between_until = compute_windows(
        sprint_info, prior_sprint
    )
    print(f"  Sprint window: {sprint_since.isoformat()} to {sprint_until.isoformat()}")

    # Prior sprint end date (YYYY-MM-DD) is still used in JQL templates
    prior_sprint_end: str | None = None
    if prior_sprint:
        raw = prior_sprint.get("completeDate") or prior_sprint.get("endDate", "")
        prior_sprint_end = raw[:10] if raw else None

    has_gap = between_since is not None and between_until is not None
    if has_gap:
        assert between_since is not None and between_until is not None
        print(
            f"  Prior sprint: {prior_sprint.get('name', '?') if prior_sprint else '?'}"
            f" (between window {between_since.isoformat()} to {between_until.isoformat()})"
        )
    elif prior_sprint:
        print("  Prior sprint leaves no between-sprints window, skipping that collection")
    else:
        print("  No prior sprint found, skipping between-sprints collection")
    print()

    # Build template variables for JQL
    variables = {
        "account_id": os.environ["JIRA_ACCOUNT_ID"],
        "start_date": start_date,
        "end_date": end_date,
        "sprint_id": str(sprint_id),
        "prior_sprint_end": prior_sprint_end or start_date,
    }

    if args.dry_run:
        print("Dry run — would collect:")
        print("  Sprint info -> jira/sprint-info.json")
        if has_gap:
            print("  Prior sprint info -> jira/prior-sprint-info.json")
        for name, qc in config["jira"].get("queries", {}).items():
            raw_jql = qc["jql"]
            if raw_jql == "TODO":
                print(f"  Jira '{name}': TODO (no query yet) -> {qc['output']}")
                continue
            jql = template_jql(raw_jql, variables)
            print(f"  Jira '{name}': {jql} -> {qc['output']}")
        gh = config.get("github", {})
        print(f"  GitHub PRs: org={os.environ.get('GITHUB_ORG')} -> {gh.get('output')}")
        git_cfg = config.get("git", {})
        repos_dir = os.environ.get("GIT_REPOS_DIR")
        print(f"  Git commits: repos_dir={repos_dir} -> {git_cfg.get('output')}")
        cc_cfg = config.get("claude_code", {})
        cc_work = os.environ.get("CLAUDE_WORK_DIRS", "~/git")
        cc_out = cc_cfg.get("output", "claude-code/sessions.md")
        print(f"  Claude Code activity: work_dirs={cc_work} -> {cc_out}")
        if has_gap:
            assert between_since is not None and between_until is not None
            print(
                f"  Between-sprints ({between_since.isoformat()} to {between_until.isoformat()}):"
            )
            print("    GitHub PRs -> github/between-sprints-prs.md")
            print("    Git commits -> git/between-sprints-commit-log.md")
            print("    Claude Code -> claude-code/between-sprints-sessions.md")
        return

    # Collect everything
    print("Collecting sprint info...")
    collect_jira_sprint_info(sprint_dir, sprint_info)
    if prior_sprint and has_gap:
        prior_path = sprint_dir / "jira" / "prior-sprint-info.json"
        prior_path.parent.mkdir(parents=True, exist_ok=True)
        with open(prior_path, "w") as f:
            json.dump(prior_sprint, f, indent=2)
            f.write("\n")
        print(f"  Wrote {prior_path.relative_to(REPO_ROOT)}")
    print()

    print("Collecting Jira issues...")
    collect_jira_issues(sprint_dir, config["jira"].get("queries", {}), variables)
    print()

    print("Collecting GitHub PRs...")
    collect_github_prs(sprint_dir, config, sprint_since.isoformat(), sprint_until.isoformat())
    print()

    print("Collecting git commits...")
    collect_git_commits(sprint_dir, config, sprint_since.isoformat(), sprint_until.isoformat())
    print()

    print("Collecting Claude Code activity...")
    collect_claude_code_activity(
        sprint_dir, config, sprint_since.isoformat(), sprint_until.isoformat()
    )
    print()

    # Between-sprints collection (prior sprint close → current sprint start day)
    if has_gap:
        assert between_since is not None and between_until is not None
        since_iso = between_since.isoformat()
        until_iso = between_until.isoformat()
        print(f"Collecting between-sprints data ({since_iso} to {until_iso})...")

        print("  GitHub PRs (between sprints)...")
        collect_github_prs(
            sprint_dir,
            {"github": {**config.get("github", {}), "output": "github/between-sprints-prs.md"}},
            since_iso,
            until_iso,
        )

        print("  Git commits (between sprints)...")
        collect_git_commits(
            sprint_dir,
            {"git": {**config.get("git", {}), "output": "git/between-sprints-commit-log.md"}},
            since_iso,
            until_iso,
        )

        print("  Claude Code activity (between sprints)...")
        collect_claude_code_activity(
            sprint_dir,
            {
                "claude_code": {
                    **config.get("claude_code", {}),
                    "output": "claude-code/between-sprints-sessions.md",
                    "documents_output": "claude-code/between-sprints-documents.md",
                    "tokens_output": "claude-code/between-sprints-tokens-by-day.json",
                }
            },
            since_iso,
            until_iso,
            raw_prefix="between-sprints-",
            skip_stats_cache=True,
        )
        print()

    print("Done. Next steps:")
    print(f"  1. Edit work/sprint-notes/{args.sprint}/manual-notes.md with additional context")
    print(f"  2. Run /draft-sprint-notes {args.sprint}")


if __name__ == "__main__":
    main()
