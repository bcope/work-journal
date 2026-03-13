"""Generate daily stand-up notes from Jira, GitHub, and git data.

Reads shared config from work/sprint-notes/config.yaml and queries each source
for yesterday's completed work, today's in-progress work, and blockers. Outputs
markdown (default) or JSON to stdout.

Usage:
    uv run python3 src/work_journal/standup.py
    uv run python3 src/work_journal/standup.py --yesterday 2026-03-03
    uv run python3 src/work_journal/standup.py --json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta

from work_journal.config import load_config
from work_journal.paths import SRC_DIR


def resolve_dates(yesterday_override: str | None) -> tuple[date, date]:
    """Return (yesterday, today) dates, handling weekends.

    If today is Monday and no override is given, yesterday defaults to Friday.
    """
    today = date.today()
    if yesterday_override:
        yesterday = date.fromisoformat(yesterday_override)
    elif today.weekday() == 0:  # Monday
        yesterday = today - timedelta(days=3)  # Friday
    else:
        yesterday = today - timedelta(days=1)
    return yesterday, today


def run_helper(script: str, args: list[str]) -> str:
    """Run a helper script and return stdout."""
    cmd = [sys.executable, str(SRC_DIR / script), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Warning: {script} failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout


def run_command(cmd: list[str]) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"  Warning: {' '.join(cmd[:3])}... failed (exit {result.returncode})", file=sys.stderr
        )
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout


def template_jql(jql_template: str, variables: dict) -> str:
    """Replace placeholders in a JQL template."""
    result = jql_template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def query_jira(jql: str) -> list[dict]:
    """Run a Jira query via the helper script, return parsed issues."""
    output = run_helper("jira/query_issues.py", [jql, "--pretty"])
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return []


def query_github_prs(args: list[str]) -> str:
    """Run a gh search command and return raw output."""
    cmd = ["gh", "search", "prs", *args]
    return run_command(cmd)


def query_git_log(config: dict, since: str, until: str) -> str:
    """Query local git commits via the helper script."""
    git_config = config.get("git", {})
    repos_dir = os.path.expanduser(git_config.get("repos_dir", "~/git"))
    author = git_config.get("author", os.environ.get("GIT_AUTHOR", ""))
    return run_helper(
        "git/query_git_log.py",
        ["--since", since, "--until", until, "--repos-dir", repos_dir, "--author", author],
    )


def collect_data(config: dict, yesterday: date, today: date) -> dict:
    """Collect all stand-up data from Jira, GitHub, and git."""
    account_id = config["jira"]["account_id"]
    org = config.get("github", {}).get("org", os.environ.get("GITHUB_ORG", ""))
    git_author = config.get("git", {}).get("author", os.environ.get("GIT_AUTHOR", ""))
    standup_queries = config.get("standup", {}).get("queries", {})

    yesterday_str = yesterday.isoformat()
    today_str = today.isoformat()

    variables = {
        "account_id": account_id,
        "yesterday": yesterday_str,
        "today": today_str,
    }

    data = {
        "yesterday": yesterday_str,
        "today": today_str,
        "completed": {"jira": [], "prs": "", "commits": ""},
        "in_progress": {"jira": [], "prs": ""},
        "blocked": {"jira": []},
    }

    # --- Yesterday: completed Jira issues ---
    completed_jql_template = standup_queries.get("completed_yesterday", {}).get(
        "jql",
        'assignee = {account_id} AND updated >= "{yesterday}"'
        ' AND updated < "{today}" AND statusCategory = Done',
    )
    completed_jql = template_jql(completed_jql_template, variables)
    data["completed"]["jira"] = query_jira(completed_jql)

    # --- Yesterday: merged PRs ---
    data["completed"]["prs"] = query_github_prs(
        [
            f"--author={git_author}",
            f"--merged={yesterday_str}..{today_str}",
            f"--owner={org}",
            "--limit=50",
            "--json=number,title,url,repository",
        ]
    )

    # --- Yesterday: git commits ---
    data["completed"]["commits"] = query_git_log(config, yesterday_str, today_str)

    # --- Today: in-progress Jira issues ---
    in_progress_jql_template = standup_queries.get("in_progress", {}).get(
        "jql",
        'assignee = {account_id} AND status = "In Progress"',
    )
    in_progress_jql = template_jql(in_progress_jql_template, variables)
    data["in_progress"]["jira"] = query_jira(in_progress_jql)

    # --- Today: open PRs ---
    data["in_progress"]["prs"] = query_github_prs(
        [
            f"--author={git_author}",
            "--state=open",
            f"--owner={org}",
            "--limit=50",
            "--json=number,title,url,repository,state",
        ]
    )

    # --- Blocked ---
    blocked_jql_template = standup_queries.get("blocked", {}).get("jql", "")
    if blocked_jql_template:
        blocked_jql = template_jql(blocked_jql_template, variables)
        data["blocked"]["jira"] = query_jira(blocked_jql)

    return data


def format_jira_issue(issue: dict, project_names: dict) -> str:
    """Format a single Jira issue as a markdown bullet."""
    key = issue.get("key", "???")
    project_key = key.split("-")[0] if "-" in key else ""
    project_label = project_names.get(project_key, project_key)

    summary = issue.get("fields", {}).get("summary", "(no summary)")
    status = issue.get("fields", {}).get("status", {}).get("name", "")

    parts = [f"[{key}]"]
    if project_label:
        parts.append(f"({project_label})")
    parts.append(summary)
    if status:
        parts.append(f"— {status}")

    return "- " + " ".join(parts)


def format_github_prs(raw_json: str, label: str) -> list[str]:
    """Parse gh JSON output and return formatted markdown lines."""
    if not raw_json.strip():
        return []
    try:
        prs = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    lines = []
    for pr in prs:
        repo = pr.get("repository", {}).get("name", "")
        owner = pr.get("repository", {}).get("owner", {}).get("login", "")
        number = pr.get("number", "")
        title = pr.get("title", "")
        if owner and repo:
            lines.append(f"- {owner}/{repo}#{number} — {title}")
        else:
            lines.append(f"- #{number} — {title}")
    return lines


def format_markdown(data: dict, project_names: dict) -> str:
    """Format collected data as markdown stand-up notes."""
    yesterday_str = data["yesterday"]
    today_str = data["today"]

    lines = [f"# Stand-up — {today_str}", ""]
    lines.append(f"## What I did yesterday ({yesterday_str})")
    lines.append("")

    # Jira
    completed_jira = data["completed"]["jira"]
    if completed_jira:
        lines.append("### Jira")
        lines.append("")
        for issue in completed_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")

    # Merged PRs
    merged_lines = format_github_prs(data["completed"]["prs"], "merged")
    if merged_lines:
        lines.append("### Pull requests")
        lines.append("")
        lines.extend(merged_lines)
        lines.append("")

    # Git commits
    commits = data["completed"]["commits"].strip()
    if commits:
        lines.append("### Commits")
        lines.append("")
        lines.append(commits)
        lines.append("")

    # Check if yesterday section is empty
    has_yesterday = completed_jira or merged_lines or commits
    if not has_yesterday:
        lines.append("Nothing tracked.")
        lines.append("")

    # --- Today ---
    lines.append("## What I'm doing today")
    lines.append("")

    in_progress_jira = data["in_progress"]["jira"]
    if in_progress_jira:
        lines.append("### Jira")
        lines.append("")
        for issue in in_progress_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")

    open_pr_lines = format_github_prs(data["in_progress"]["prs"], "open")
    if open_pr_lines:
        lines.append("### Open PRs")
        lines.append("")
        lines.extend(open_pr_lines)
        lines.append("")

    has_today = in_progress_jira or open_pr_lines
    if not has_today:
        lines.append("Nothing tracked.")
        lines.append("")

    # --- Blockers ---
    lines.append("## Blockers")
    lines.append("")

    blocked_jira = data["blocked"]["jira"]
    if blocked_jira:
        for issue in blocked_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")
    else:
        lines.append("None")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate daily stand-up notes from Jira, GitHub, and git.",
    )
    parser.add_argument(
        "--yesterday",
        help="Override the 'yesterday' date (YYYY-MM-DD). Default: previous weekday.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON instead of markdown.",
    )

    args = parser.parse_args()

    config = load_config()
    yesterday, today = resolve_dates(args.yesterday)

    print(f"Collecting stand-up data (yesterday={yesterday}, today={today})...", file=sys.stderr)

    data = collect_data(config, yesterday, today)

    if args.output_json:
        print(json.dumps(data, indent=2))
    else:
        project_names = config.get("project_names", {})
        print(format_markdown(data, project_names))


if __name__ == "__main__":
    main()
