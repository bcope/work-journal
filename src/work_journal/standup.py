"""Generate daily stand-up notes from Jira, GitHub, and git data.

Reads config from config/standup.yaml and config/shared.yaml and queries each source
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
import sys
from datetime import date, timedelta

from work_journal.claude_code.collect_activity import (
    DEFAULT_HISTORY_PATH,
    DEFAULT_PROJECTS_PATH,
    DEFAULT_WORK_DIRS,
    analyze_conversation,
    format_duration,
    load_history,
    repo_name,
)
from work_journal.config import load_shared_config, load_standup_config
from work_journal.git.query_git_log import find_git_repos, get_commits
from work_journal.git.query_git_log import format_markdown as format_git_markdown
from work_journal.github.query_github_prs import (
    search_closed_prs,
    search_merged_prs,
    search_open_prs,
)
from work_journal.jira.query_issues import search_issues
from work_journal.jira.query_sprint_info import DEFAULT_BOARD_ID, _make_session, list_sprints
from work_journal.paths import STANDUP_DIR


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


def template_jql(jql_template: str, variables: dict) -> str:
    """Replace placeholders in a JQL template."""
    result = jql_template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def build_date_label_filter(prefix: str, start: date, end: date) -> str:
    """Build a JQL OR clause matching date-stamped labels for each day in [start, end].

    Example: build_date_label_filter("added_to_sprint-date-", fri, mon)
    returns: (labels = "added_to_sprint-date-2026-03-20" or ...)
    """
    clauses = []
    current = start
    while current <= end:
        clauses.append(f'labels = "{prefix}{current.isoformat()}"')
        current += timedelta(days=1)
    return "(" + " or ".join(clauses) + ")"


def _warn(warnings: list[str], msg: str) -> None:
    """Append a warning and print it to stderr."""
    warnings.append(msg)
    print(f"Warning: {msg}", file=sys.stderr)


def query_jira(
    jql: str,
    warnings: list[str],
    label: str = "Jira query",
    fields: list[str] | None = None,
) -> list[dict]:
    """Run a Jira query, return parsed issues."""
    try:
        return search_issues(jql, fields=fields)
    except Exception as e:
        _warn(warnings, f"{label} failed: {e}")
        return []


def completion_date(issue: dict) -> str | None:
    """Return the YYYY-MM-DD an issue entered its current (Done) status category.

    Uses `statuscategorychangedate` (set when the issue moved into Done),
    falling back to `resolutiondate`. Returns None if neither is present.

    This is the signal for "actually completed", as opposed to `updated`, which
    bumps on any field change (automation touches, comments, label edits).
    """
    fields = issue.get("fields", {})
    raw = fields.get("statuscategorychangedate") or fields.get("resolutiondate")
    return raw[:10] if raw else None


def query_git_log(since: str, until: str, warnings: list[str]) -> str:
    """Query local git commits via direct import."""
    repos_dir = os.path.expanduser(os.environ.get("GIT_REPOS_DIR", "~/git"))
    author = os.environ.get("GIT_AUTHOR", "")

    if not os.path.isdir(repos_dir):
        _warn(warnings, f"Git repos directory not found: {repos_dir}")
        return ""

    try:
        repos = find_git_repos(repos_dir)
        results: dict[str, list[str]] = {}
        for repo_path in repos:
            name = os.path.basename(repo_path)
            commits = get_commits(repo_path, author, since, until)
            if commits:
                results[name] = commits
        return format_git_markdown(results, since, until, author)
    except Exception as e:
        _warn(warnings, f"Git log collection failed: {e}")
        return ""


def collect_claude_activity(
    config: dict, yesterday: date, today: date, warnings: list[str]
) -> dict | None:
    """Collect Claude Code activity for yesterday's sessions.

    Returns per-repo metrics and aggregate totals, or None if no sessions found.
    """
    yesterday_str = yesterday.isoformat()
    today_str = today.isoformat()

    history_path = DEFAULT_HISTORY_PATH
    if not os.path.exists(history_path):
        return None

    sessions = load_history(history_path, yesterday_str, today_str, DEFAULT_WORK_DIRS)
    if not sessions:
        return None

    try:
        # Per-repo aggregation
        repos: dict[str, dict] = {}
        total_thinking_ms = 0
        total_turns = 0
        total_user_messages = 0

        for session_id, entry in sessions.items():
            project_path = entry["project"]
            name = repo_name(project_path)
            metrics = analyze_conversation(DEFAULT_PROJECTS_PATH, project_path, session_id)

            if name not in repos:
                repos[name] = {
                    "session_count": 0,
                    "thinking_time_ms": 0,
                    "user_messages": 0,
                }

            repos[name]["session_count"] += 1
            repos[name]["thinking_time_ms"] += metrics["thinking_time_ms"]
            repos[name]["user_messages"] += metrics["user_messages"]

            total_thinking_ms += metrics["thinking_time_ms"]
            total_turns += metrics["turn_count"]
            total_user_messages += metrics["user_messages"]

        return {
            "session_count": len(sessions),
            "repos": repos,
            "thinking_time_ms": total_thinking_ms,
            "total_turns": total_turns,
            "total_user_messages": total_user_messages,
        }
    except Exception as e:
        _warn(warnings, f"Claude Code activity collection failed: {e}")
        return None


def get_active_sprint_id(warnings: list[str]) -> str:
    """Return the ID of the active sprint, or empty string if unavailable."""
    try:
        session = _make_session()
        sprints = list_sprints(session, DEFAULT_BOARD_ID, state="active")
        if sprints:
            return str(sprints[0]["id"])
    except Exception as e:
        _warn(warnings, f"Active sprint lookup failed: {e}")
    return ""


def collect_data(standup_config: dict, yesterday: date, today: date) -> dict:
    """Collect all stand-up data from Jira, GitHub, and git."""
    account_id = os.environ["JIRA_ACCOUNT_ID"]
    org = os.environ.get("GITHUB_ORG", "")
    git_author = os.environ.get("GIT_AUTHOR", "")
    standup_queries = standup_config.get("queries", {})
    warnings: list[str] = []

    yesterday_str = yesterday.isoformat()
    today_str = today.isoformat()
    sprint_id = get_active_sprint_id(warnings)

    injected_date_filter = build_date_label_filter("added_to_sprint-date-", yesterday, today)

    # For In Progress Epics: only include if in the active sprint OR the user logged
    # work on them during the stand-up period. Worklog-only when no active sprint.
    worklog_clause = f'(worklogAuthor = {account_id} AND worklogDate >= "{yesterday_str}")'
    if sprint_id:
        epic_relevance_filter = f"(sprint = {sprint_id} OR {worklog_clause})"
        today_sprint_filter = f"(sprint IS EMPTY OR sprint = {sprint_id})"
    else:
        epic_relevance_filter = worklog_clause
        # No active sprint — don't filter by sprint.
        today_sprint_filter = "(sprint IS EMPTY OR sprint IS NOT EMPTY)"

    variables = {
        "account_id": account_id,
        "yesterday": yesterday_str,
        "today": today_str,
        "sprint_id": sprint_id,
        "injected_date_filter": injected_date_filter,
        "epic_relevance_filter": epic_relevance_filter,
        "today_sprint_filter": today_sprint_filter,
    }

    data: dict = {
        "yesterday": yesterday_str,
        "today": today_str,
        "completed": {
            "jira": [],
            "recently_closed": [],
            "prs": [],
            "closed_prs": [],
            "commits": "",
        },
        "work_logged": {"jira": []},
        "in_progress": {"jira": [], "prs": []},
        "status_mismatch": {"jira": []},
        "blocked": {"jira": []},
        "injected": {"jira": []},
        "warnings": warnings,
    }

    # --- Yesterday: completed Jira issues ---
    completed_jql_template = standup_queries.get("completed_yesterday", {}).get(
        "jql",
        'assignee = {account_id} AND updated >= "{yesterday}"'
        ' AND updated < "{today}" AND statusCategory = Done',
    )
    completed_jql = template_jql(completed_jql_template, variables)
    completed_issues = query_jira(
        completed_jql,
        warnings,
        "Completed yesterday (Jira)",
        fields=["summary", "status", "statuscategorychangedate", "resolutiondate"],
    )
    # The query keys off `updated`, a broad superset that bumps on any field
    # change. Split by when the issue actually entered Done: transitions within
    # [yesterday, today) are genuine completions; the rest were Done earlier and
    # merely touched yesterday (e.g. by automation).
    for issue in completed_issues:
        changed = completion_date(issue)
        if changed is not None and not (yesterday_str <= changed < today_str):
            data["completed"]["recently_closed"].append(issue)
        else:
            data["completed"]["jira"].append(issue)

    # --- Yesterday: merged PRs ---
    try:
        data["completed"]["prs"] = search_merged_prs(
            yesterday_str, today_str, org, author=git_author
        )
    except Exception as e:
        _warn(warnings, f"Merged PRs query failed: {e}")

    # --- Yesterday: closed (not merged) PRs ---
    try:
        data["completed"]["closed_prs"] = search_closed_prs(
            yesterday_str, today_str, org, author=git_author
        )
    except Exception as e:
        _warn(warnings, f"Closed PRs query failed: {e}")

    # --- Yesterday: git commits ---
    data["completed"]["commits"] = query_git_log(yesterday_str, today_str, warnings)

    # --- Yesterday: issues with worklog entries (excluding those already shown as completed) ---
    work_logged_jql_template = standup_queries.get("work_logged_yesterday", {}).get("jql", "")
    if work_logged_jql_template:
        work_logged_jql = template_jql(work_logged_jql_template, variables)
        work_logged_issues = query_jira(work_logged_jql, warnings, "Work logged yesterday (Jira)")
        completed_keys = {i.get("key") for i in data["completed"]["jira"]}
        data["work_logged"]["jira"] = [
            i for i in work_logged_issues if i.get("key") not in completed_keys
        ]

    # --- Today: in-progress Jira issues ---
    in_progress_jql_template = standup_queries.get("in_progress", {}).get(
        "jql",
        'assignee = {account_id} AND status = "In Progress"',
    )
    in_progress_jql = template_jql(in_progress_jql_template, variables)
    data["in_progress"]["jira"] = query_jira(in_progress_jql, warnings, "In-progress (Jira)")

    # --- Today: open PRs (updated in the last 7 days) ---
    open_since = (yesterday - timedelta(days=7)).isoformat()
    try:
        data["in_progress"]["prs"] = search_open_prs(org, author=git_author, since=open_since)
    except Exception as e:
        _warn(warnings, f"Open PRs query failed: {e}")

    # --- Status mismatch (In Progress but not in the active sprint) ---
    status_mismatch_jql_template = standup_queries.get("status_mismatch", {}).get("jql", "")
    if status_mismatch_jql_template and sprint_id:
        status_mismatch_jql = template_jql(status_mismatch_jql_template, variables)
        data["status_mismatch"]["jira"] = query_jira(
            status_mismatch_jql, warnings, "Status mismatch (Jira)"
        )

    # --- Blocked ---
    blocked_jql_template = standup_queries.get("blocked", {}).get("jql", "")
    if blocked_jql_template:
        blocked_jql = template_jql(blocked_jql_template, variables)
        data["blocked"]["jira"] = query_jira(blocked_jql, warnings, "Blocked (Jira)")

    # --- Injected (added to sprint recently) ---
    injected_jql_template = standup_queries.get("injected", {}).get("jql", "")
    if injected_jql_template and sprint_id:
        injected_jql = template_jql(injected_jql_template, variables)
        data["injected"]["jira"] = query_jira(injected_jql, warnings, "Injected (Jira)")

    # --- Claude Code activity ---
    data["claude_code"] = collect_claude_activity(standup_config, yesterday, today, warnings)

    return data


def format_jira_issue(issue: dict, project_names: dict, show_completion_date: bool = False) -> str:
    """Format a single Jira issue as a markdown bullet.

    When show_completion_date is set, the date the issue entered Done is appended
    after the status (e.g. "— Closed 2026-05-29"), making it clear the issue was
    not completed yesterday.
    """
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
        status_part = f"— {status}"
        if show_completion_date:
            changed = completion_date(issue)
            if changed:
                status_part += f" {changed}"
        parts.append(status_part)

    return "- " + " ".join(parts)


def format_github_prs(prs: list[dict], label: str) -> list[str]:
    """Format PR dicts as markdown lines."""
    if not prs:
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


def format_claude_summary(claude_data: dict | None) -> list[str]:
    """Format Claude Code activity as markdown lines."""
    if not claude_data:
        return []

    lines = ["### Claude Code", ""]
    count = claude_data["session_count"]
    thinking = format_duration(claude_data["thinking_time_ms"])
    turns = claude_data["total_turns"]
    user_msgs = claude_data["total_user_messages"]

    lines.append(
        f"- **Totals:** {count} sessions, {thinking} thinking,"
        f" {turns} turns, {user_msgs} user inputs"
    )

    # Per-repo breakdown
    repos = claude_data.get("repos", {})
    if repos:
        # Sort by session count descending, then alphabetically
        sorted_repos = sorted(repos.items(), key=lambda x: (-x[1]["session_count"], x[0]))
        lines.append("")
        lines.append("| Repo | Sessions | Thinking | User inputs |")
        lines.append("| --- | --- | --- | --- |")
        for name, stats in sorted_repos:
            lines.append(
                f"| {name} | {stats['session_count']}"
                f" | {format_duration(stats['thinking_time_ms'])}"
                f" | {stats['user_messages']} |"
            )

    lines.append("")
    return lines


def with_weekday(date_str: str) -> str:
    """Return an ISO date string prefixed with its weekday, e.g.
    "Wednesday, 2026-06-10". The weekday is computed from the date, never
    inferred, so downstream readers (including the standup skill) can copy it
    verbatim instead of guessing the day of week."""
    return f"{date.fromisoformat(date_str).strftime('%A')}, {date_str}"


def format_markdown(data: dict, project_names: dict) -> str:
    """Format collected data as markdown stand-up notes."""
    yesterday_str = data["yesterday"]
    today_str = data["today"]
    yesterday_label = with_weekday(yesterday_str)
    today_label = with_weekday(today_str)

    lines = [f"# Stand-up — {today_label}", ""]
    lines.append(f"## What I did yesterday ({yesterday_label})")
    lines.append("")

    # Jira
    completed_jira = data["completed"]["jira"]
    if completed_jira:
        lines.append("### Jira")
        lines.append("")
        for issue in completed_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")

    # Done earlier, only touched yesterday (e.g. by automation) — surfaced for
    # context but kept out of the genuine "completed yesterday" list.
    recently_closed = data["completed"].get("recently_closed", [])
    if recently_closed:
        lines.append("### Recently closed (activity yesterday)")
        lines.append("")
        for issue in recently_closed:
            lines.append(format_jira_issue(issue, project_names, show_completion_date=True))
        lines.append("")

    # Work logged on issues (not yet done)
    work_logged_jira = data.get("work_logged", {}).get("jira", [])
    if work_logged_jira:
        lines.append("### Jira (work logged, not closed)")
        lines.append("")
        for issue in work_logged_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")

    # Merged PRs
    merged_lines = format_github_prs(data["completed"]["prs"], "merged")
    if merged_lines:
        lines.append("### Pull requests (merged)")
        lines.append("")
        lines.extend(merged_lines)
        lines.append("")

    # Closed (not merged) PRs
    closed_lines = format_github_prs(data["completed"].get("closed_prs", []), "closed")
    if closed_lines:
        lines.append("### Pull requests (closed, not merged)")
        lines.append("")
        lines.extend(closed_lines)
        lines.append("")

    # Git commits
    commits = data["completed"]["commits"].strip()
    if commits:
        lines.append("### Commits")
        lines.append("")
        lines.append(commits)
        lines.append("")

    # Claude Code activity
    claude_lines = format_claude_summary(data.get("claude_code"))
    if claude_lines:
        lines.extend(claude_lines)

    # Check if yesterday section is empty
    has_yesterday = (
        completed_jira
        or recently_closed
        or work_logged_jira
        or merged_lines
        or closed_lines
        or commits
        or claude_lines
    )
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

    open_prs = data["in_progress"]["prs"]
    yesterday_str = data["yesterday"]
    active_yesterday = [pr for pr in open_prs if pr.get("updatedAt", "")[:10] == yesterday_str]
    other_recent = [pr for pr in open_prs if pr.get("updatedAt", "")[:10] != yesterday_str]

    has_open_prs = bool(active_yesterday or other_recent)
    if has_open_prs:
        lines.append("### Open PRs")
        lines.append("")
        if active_yesterday:
            lines.append(f"**Active yesterday ({yesterday_str}):**")
            lines.append("")
            lines.extend(format_github_prs(active_yesterday, "open"))
            lines.append("")
        if other_recent:
            lines.append("**Other recent:**")
            lines.append("")
            lines.extend(format_github_prs(other_recent, "open"))
            lines.append("")

    has_today = in_progress_jira or has_open_prs
    if not has_today:
        lines.append("Nothing tracked.")
        lines.append("")

    # --- Injected ---
    injected_jira = data["injected"]["jira"]
    if injected_jira:
        lines.append("## Injected into sprint")
        lines.append("")
        for issue in injected_jira:
            lines.append(format_jira_issue(issue, project_names))
        lines.append("")

    # --- Status check (In Progress but not in active sprint) ---
    status_mismatch_jira = data.get("status_mismatch", {}).get("jira", [])
    if status_mismatch_jira:
        lines.append("## Status check (In Progress, not in active sprint)")
        lines.append("")
        for issue in status_mismatch_jira:
            lines.append(format_jira_issue(issue, project_names))
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

    # --- Data collection warnings ---
    warnings = data.get("warnings", [])
    if warnings:
        lines.append("## Data collection warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
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

    standup_config = load_standup_config()
    shared_config = load_shared_config()
    yesterday, today = resolve_dates(args.yesterday)

    print(f"Collecting stand-up data (yesterday={yesterday}, today={today})...", file=sys.stderr)

    data = collect_data(standup_config, yesterday, today)

    if args.output_json:
        output = json.dumps(data, indent=2)
    else:
        project_names = shared_config.get("project_names", {})
        output = format_markdown(data, project_names)

    print(output)

    # Save to file
    STANDUP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STANDUP_DIR / f"{today.isoformat()}.md"
    if args.output_json:
        output_path = output_path.with_suffix(".json")
    output_path.write_text(output + "\n")
    print(f"Saved to {output_path}", file=sys.stderr)

    if data.get("warnings"):
        sys.exit(1)


if __name__ == "__main__":
    main()
