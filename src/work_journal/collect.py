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
from pathlib import Path

from work_journal.config import load_config, load_sprint_config
from work_journal.paths import REPO_ROOT, SPRINT_NOTES_DIR, SRC_DIR


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


def resolve_sprint(config: dict, sprint_config: dict) -> dict:
    """Resolve sprint name to full sprint metadata via Jira API."""
    board_id = str(sprint_config.get("board_id", config["jira"]["board_id"]))
    sprint_name = sprint_config["sprint_name"]

    output = run_helper(
        "jira/query_sprint_info.py",
        ["--board-id", board_id, "--sprint-name", sprint_name, "--pretty"],
    )
    if not output:
        print(
            f"Error: Could not find sprint '{sprint_name}' on board {board_id}.",
            file=sys.stderr,
        )
        sys.exit(1)

    return json.loads(output)


def extract_dates(sprint_info: dict) -> tuple[str, str]:
    """Extract YYYY-MM-DD start and end dates from sprint info."""
    start = sprint_info["startDate"][:10]
    end = sprint_info["endDate"][:10]
    return start, end


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


def collect_jira_issues(sprint_dir: Path, config: dict, variables: dict) -> None:
    """Run all configured Jira JQL queries."""
    queries = config["jira"].get("queries", {})
    for name, query_config in queries.items():
        raw_jql = query_config["jql"]
        if raw_jql == "TODO":
            print(f"  Skipping '{name}' (JQL is TODO)")
            continue
        jql = template_jql(raw_jql, variables)
        output_file = query_config["output"]
        output_path = sprint_dir / output_file

        print(f"  Jira query '{name}': {jql}")
        output = run_helper(
            "jira/query_issues.py",
            [jql, "--pretty"],
            output_path=output_path,
        )
        if output:
            try:
                count = len(json.loads(output))
                print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({count} issues)")
            except json.JSONDecodeError:
                print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_github_prs(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    """Collect GitHub PR data."""
    gh_config = config.get("github", {})
    org = gh_config.get("org", os.environ.get("GITHUB_ORG", ""))
    output_file = gh_config.get("output", "github/prs.md")
    output_format = gh_config.get("format", "markdown")
    output_path = sprint_dir / output_file

    print(f"  GitHub PRs: org={org}, {start_date} to {end_date}")
    run_helper(
        "github/query_github_prs.py",
        ["--since", start_date, "--until", end_date, "--org", org, "--format", output_format],
        output_path=output_path,
    )
    if output_path.exists():
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_git_commits(sprint_dir: Path, config: dict, start_date: str, end_date: str) -> None:
    """Collect local git commit data."""
    git_config = config.get("git", {})
    repos_dir = os.path.expanduser(git_config.get("repos_dir", "~/git"))
    author = git_config.get("author", os.environ.get("GIT_AUTHOR", ""))
    output_file = git_config.get("output", "git/commit-log.md")
    output_path = sprint_dir / output_file

    print(f"  Git commits: repos_dir={repos_dir}, author={author}")
    run_helper(
        "git/query_git_log.py",
        ["--since", start_date, "--until", end_date, "--repos-dir", repos_dir, "--author", author],
        output_path=output_path,
    )
    if output_path.exists():
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_claude_code_activity(
    sprint_dir: Path, config: dict, start_date: str, end_date: str
) -> None:
    """Collect Claude Code session activity data."""
    cc_config = config.get("claude_code", {})
    history_path = os.path.expanduser(
        cc_config.get(
            "history_path", os.environ.get("CLAUDE_HISTORY_PATH", "~/.claude/history.jsonl")
        )
    )
    stats_cache_path = os.path.expanduser(
        cc_config.get(
            "stats_cache_path",
            os.environ.get("CLAUDE_STATS_CACHE_PATH", "~/.claude/stats-cache.json"),
        )
    )
    projects_path = os.path.expanduser(
        cc_config.get("projects_path", os.environ.get("CLAUDE_PROJECTS_PATH", "~/.claude/projects"))
    )
    work_dirs = [os.path.expanduser(d) for d in cc_config.get("work_dirs", ["~/git"])]
    output_file = cc_config.get("output", "claude-code/sessions.md")
    docs_output_file = cc_config.get("documents_output", "claude-code/documents.md")
    output_path = sprint_dir / output_file
    docs_output_path = sprint_dir / docs_output_file
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
    ]
    for wd in work_dirs:
        helper_args.extend(["--work-dirs", wd])

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

    config = load_config()
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
    sprint_info = resolve_sprint(config, sprint_config)
    start_date, end_date = extract_dates(sprint_info)
    sprint_id = sprint_info["id"]
    print(f"  Sprint ID: {sprint_id}")
    print(f"  Dates: {start_date} to {end_date}")
    print()

    # Build template variables for JQL
    variables = {
        "account_id": config["jira"]["account_id"],
        "start_date": start_date,
        "end_date": end_date,
        "sprint_id": str(sprint_id),
    }

    if args.dry_run:
        print("Dry run — would collect:")
        print("  Sprint info -> jira/sprint-info.json")
        for name, qc in config["jira"].get("queries", {}).items():
            raw_jql = qc["jql"]
            if raw_jql == "TODO":
                print(f"  Jira '{name}': TODO (no query yet) -> {qc['output']}")
                continue
            jql = template_jql(raw_jql, variables)
            print(f"  Jira '{name}': {jql} -> {qc['output']}")
        gh = config.get("github", {})
        print(f"  GitHub PRs: org={gh.get('org')} -> {gh.get('output')}")
        git_cfg = config.get("git", {})
        print(f"  Git commits: repos_dir={git_cfg.get('repos_dir')} -> {git_cfg.get('output')}")
        cc_cfg = config.get("claude_code", {})
        cc_work = cc_cfg.get("work_dirs", ["~/git"])
        cc_out = cc_cfg.get("output", "claude-code/sessions.md")
        print(f"  Claude Code activity: work_dirs={cc_work} -> {cc_out}")
        return

    # Collect everything
    print("Collecting sprint info...")
    collect_jira_sprint_info(sprint_dir, sprint_info)
    print()

    print("Collecting Jira issues...")
    collect_jira_issues(sprint_dir, config, variables)
    print()

    print("Collecting GitHub PRs...")
    collect_github_prs(sprint_dir, config, start_date, end_date)
    print()

    print("Collecting git commits...")
    collect_git_commits(sprint_dir, config, start_date, end_date)
    print()

    print("Collecting Claude Code activity...")
    collect_claude_code_activity(sprint_dir, config, start_date, end_date)
    print()

    print("Done. Next steps:")
    print(f"  1. Edit work/sprint-notes/{args.sprint}/manual-notes.md with additional context")
    print(f"  2. Run /draft-sprint-notes {args.sprint}")


if __name__ == "__main__":
    main()
