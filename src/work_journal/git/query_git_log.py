"""Query local git repos for commits by a specific author within a date range.

Walks directories in --repos-dir, finds git repos, and outputs a markdown
summary of commits grouped by repository.
"""

import argparse
import os
import subprocess
import sys

from work_journal.dates import window_bounds_iso

DEFAULT_REPOS_DIR = os.path.expanduser(os.environ.get("GIT_REPOS_DIR", "~/git"))
DEFAULT_AUTHOR = os.environ.get("GIT_AUTHOR", "")


def find_git_repos(repos_dir: str) -> list[str]:
    """Find all directories in repos_dir that contain a .git directory."""
    repos = []
    for entry in sorted(os.listdir(repos_dir)):
        full_path = os.path.join(repos_dir, entry)
        if os.path.isdir(full_path) and os.path.isdir(os.path.join(full_path, ".git")):
            repos.append(full_path)
    return repos


def get_commits(
    repo_path: str,
    author: str,
    since: str,
    until: str,
) -> list[str]:
    """Run git log in a repo and return list of oneline commit strings."""
    since_iso, until_iso = window_bounds_iso(since, until)
    result = subprocess.run(
        [
            "git",
            "log",
            f"--author={author}",
            f"--after={since_iso}",
            f"--before={until_iso}",
            "--oneline",
            "--no-merges",
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    lines = result.stdout.strip().splitlines()
    return [line for line in lines if line]


def format_markdown(results: dict[str, list[str]], since: str, until: str, author: str) -> str:
    """Format commit data as markdown grouped by repo."""
    lines: list[str] = []
    lines.append(f"# Git Commits ({since} to {until})")
    lines.append("")
    lines.append(f"Author: `{author}`")
    lines.append("")

    total_commits = sum(len(commits) for commits in results.values())
    lines.append(f"Total: {total_commits} commits across {len(results)} repos")
    lines.append("")

    for repo_name in sorted(results):
        commits = results[repo_name]
        lines.append(f"## {repo_name} ({len(commits)} commits)")
        lines.append("")
        for commit in commits:
            lines.append(f"- {commit}")
        lines.append("")

    if not results:
        lines.append("No commits found in the given date range.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Query local git repos for commits. Outputs markdown to stdout.",
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
        "--repos-dir",
        default=DEFAULT_REPOS_DIR,
        help=f"Directory containing git repos (default: {DEFAULT_REPOS_DIR})",
    )
    parser.add_argument(
        "--author",
        default=DEFAULT_AUTHOR,
        help=f"Git author to filter by (default: {DEFAULT_AUTHOR})",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.repos_dir):
        print(f"Error: {args.repos_dir} is not a directory.", file=sys.stderr)
        sys.exit(1)

    repos = find_git_repos(args.repos_dir)
    results: dict[str, list[str]] = {}

    for repo_path in repos:
        repo_name = os.path.basename(repo_path)
        commits = get_commits(repo_path, args.author, args.since, args.until)
        if commits:
            results[repo_name] = commits

    print(format_markdown(results, args.since, args.until, args.author))


if __name__ == "__main__":
    main()
