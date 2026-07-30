"""Query GitHub PR activity via the gh CLI.

Finds PRs authored and reviewed by the current user within a date range.
Auth is handled by the gh CLI (must be logged in via `gh auth login`).
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

from work_journal.dates import resolve_window_bound, window_bounds_iso

PR_JSON_FIELDS = "number,title,url,state,createdAt,updatedAt,closedAt,repository"


class GhError(Exception):
    """Raised when a gh CLI command fails."""


def _run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout.

    Raises GhError on non-zero exit code.
    """
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GhError(f"gh {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def search_authored_prs(since: str, until: str, org: str) -> list[dict]:
    """Search for PRs authored by the current user in the date range."""
    since_iso, until_iso = window_bounds_iso(since, until)
    output = _run_gh(
        [
            "search",
            "prs",
            "--author=@me",
            f"--created={since_iso}..{until_iso}",
            f"--owner={org}",
            "--limit=200",
            f"--json={PR_JSON_FIELDS}",
        ]
    )
    return json.loads(output) if output.strip() else []


def search_reviewed_prs(since: str, until: str, org: str) -> list[dict]:
    """Search for PRs reviewed by the current user in the date range."""
    since_iso, until_iso = window_bounds_iso(since, until)
    output = _run_gh(
        [
            "search",
            "prs",
            "--reviewed-by=@me",
            f"--updated={since_iso}..{until_iso}",
            f"--owner={org}",
            "--limit=200",
            f"--json={PR_JSON_FIELDS}",
        ]
    )
    return json.loads(output) if output.strip() else []


def search_repo_prs(repo: str, since: str, until: str) -> list[dict]:
    """Search for all PRs in a specific repo within the date range.

    Unlike search_authored_prs/search_reviewed_prs, this returns PRs from
    all contributors — useful for project-scoped status updates.

    Returns an empty list on error instead of exiting, so the caller
    can continue collecting data from other repos.
    """
    since_iso, until_iso = window_bounds_iso(since, until)
    result = subprocess.run(
        [
            "gh",
            "search",
            "prs",
            f"--repo={repo}",
            f"--updated={since_iso}..{until_iso}",
            "--limit=200",
            f"--json={PR_JSON_FIELDS}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Warning: gh search for {repo} failed:", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        return []
    return json.loads(result.stdout) if result.stdout.strip() else []


def search_merged_prs(since: str, until: str, org: str, author: str | None = None) -> list[dict]:
    """Search for PRs merged in the date range.

    Returns an empty list on error instead of exiting.
    """
    author_flag = f"--author={author}" if author else "--author=@me"
    since_iso, until_iso = window_bounds_iso(since, until)
    result = subprocess.run(
        [
            "gh",
            "search",
            "prs",
            author_flag,
            f"--merged-at={since_iso}..{until_iso}",
            f"--owner={org}",
            "--limit=50",
            f"--json={PR_JSON_FIELDS}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Warning: gh search merged PRs failed:", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        return []
    return json.loads(result.stdout) if result.stdout.strip() else []


def search_closed_prs(since: str, until: str, org: str, author: str | None = None) -> list[dict]:
    """Search for PRs closed (but not merged) in the date range.

    Uses the --closed date filter to find PRs closed in the range, then
    filters out merged PRs (state == "MERGED") since GitHub considers
    merged PRs as closed too.

    Returns an empty list on error instead of exiting.
    """
    author_flag = f"--author={author}" if author else "--author=@me"
    since_iso, until_iso = window_bounds_iso(since, until)
    result = subprocess.run(
        [
            "gh",
            "search",
            "prs",
            author_flag,
            f"--closed={since_iso}..{until_iso}",
            f"--owner={org}",
            "--limit=50",
            f"--json={PR_JSON_FIELDS}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Warning: gh search closed PRs failed:", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        return []
    prs = json.loads(result.stdout) if result.stdout.strip() else []
    # Exclude merged PRs — only keep truly closed (not merged)
    return [pr for pr in prs if pr.get("state", "").upper() != "MERGED"]


def search_open_prs(org: str, author: str | None = None, since: str | None = None) -> list[dict]:
    """Search for open PRs owned by the author.

    When *since* is provided (YYYY-MM-DD), only PRs updated since that date
    are returned.  Returns an empty list on error instead of exiting.
    """
    author_flag = f"--author={author}" if author else "--author=@me"
    cmd = [
        "gh",
        "search",
        "prs",
        author_flag,
        "--state=open",
        f"--owner={org}",
        "--limit=50",
        f"--json={PR_JSON_FIELDS}",
    ]
    if since:
        cmd.insert(-1, f"--updated={resolve_window_bound(since).isoformat()}..")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Warning: gh search open PRs failed:", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        return []
    return json.loads(result.stdout) if result.stdout.strip() else []


def _repo_name(pr: dict) -> str:
    """Extract repository name from a PR object."""
    repo = pr.get("repository", {})
    return repo.get("nameWithOwner", repo.get("name", "unknown"))


_STATE_ORDER = {"MERGED": 0, "OPEN": 1, "CLOSED": 2}


def _sort_prs_by_state(prs: list[dict]) -> list[dict]:
    """Sort PRs by state (merged first, then open, then closed), then by number."""
    return sorted(
        prs,
        key=lambda p: (_STATE_ORDER.get(p.get("state", "").upper(), 9), p.get("number", 0)),
    )


def _format_markdown(authored: list[dict], reviewed: list[dict]) -> str:
    """Format PR data as markdown grouped by repo."""
    lines: list[str] = []

    if authored:
        lines.append("## PRs Authored")
        lines.append("")
        by_repo: dict[str, list[dict]] = defaultdict(list)
        for pr in authored:
            by_repo[_repo_name(pr)].append(pr)

        for repo in sorted(by_repo):
            lines.append(f"### {repo}")
            lines.append("")
            for pr in _sort_prs_by_state(by_repo[repo]):
                state = pr.get("state", "").upper()
                title = pr.get("title", "")
                url = pr.get("url", "")
                num = pr.get("number", "")
                lines.append(f"- [#{num} {title}]({url}) — {state}")
            lines.append("")

    if reviewed:
        lines.append("## PRs Reviewed")
        lines.append("")
        by_repo = defaultdict(list)
        for pr in reviewed:
            by_repo[_repo_name(pr)].append(pr)

        for repo in sorted(by_repo):
            lines.append(f"### {repo}")
            lines.append("")
            for pr in _sort_prs_by_state(by_repo[repo]):
                state = pr.get("state", "").upper()
                title = pr.get("title", "")
                url = pr.get("url", "")
                num = pr.get("number", "")
                lines.append(f"- [#{num} {title}]({url}) — {state}")
            lines.append("")

    if not authored and not reviewed:
        lines.append("No PR activity found in the given date range.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query GitHub PR activity. Outputs JSON or markdown to stdout.",
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--until",
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--org",
        default=os.environ.get("GITHUB_ORG", ""),
        help="GitHub org/owner to search (default: $GITHUB_ORG)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        dest="output_format",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON output (ignored for markdown)",
    )

    args = parser.parse_args()

    try:
        authored = search_authored_prs(args.since, args.until, args.org)
        reviewed = search_reviewed_prs(args.since, args.until, args.org)
    except GhError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Deduplicate: remove from reviewed any PRs also in authored
    authored_urls = {pr.get("url") for pr in authored}
    reviewed = [pr for pr in reviewed if pr.get("url") not in authored_urls]

    if args.output_format == "markdown":
        print(_format_markdown(authored, reviewed))
    else:
        indent = 2 if args.pretty else None
        result = {"authored": authored, "reviewed": reviewed}
        json.dump(result, sys.stdout, indent=indent)
        print()


if __name__ == "__main__":
    main()
