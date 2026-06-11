# Project Status Updates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a collect-then-draft pipeline for generating project status update documents from GitHub, Jira, and Google Calendar data.

**Architecture:** Mirrors the sprint notes pipeline. A Python collection script gathers raw data into a timestamped run directory. A Claude Code skill invokes the collection script, reads the output, and drafts an audience-tailored markdown document.

**Tech Stack:** Python 3.12+, PyYAML, requests, google-api-python-client, google-auth. Claude Code skill (SKILL.md). Existing helpers: `src/jira/query_issues.py`, `src/github/query_github_prs.py`.

---

## Task 1: Add Google API Python dependencies

**Files:**

- Modify: `pyproject.toml`

**Step 1: Add dependencies**

Add `google-api-python-client` and `google-auth` to `pyproject.toml`:

```toml
dependencies = [
    "pyyaml>=6.0.3",
    "requests>=2.32.5",
    "google-api-python-client>=2.150.0",
    "google-auth>=2.36.0",
]
```

**Step 2: Install**

Run: `uv sync`
Expected: Clean install, lock file updated.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "add google-api-python-client and google-auth dependencies"
```

---

## Task 2: Create the Google Calendar query script

**Files:**

- Create: `src/calendar/__init__.py` (empty)
- Create: `src/calendar/query_events.py`

This script reuses OAuth tokens from the gdocs-mcp server. The token and credentials files are in the directory configured via `calendar.credentials_dir` in the project-status config. The `calendar.readonly` scope is already granted.

**Step 1: Write the test**

Create: `tests/calendar/test_query_events.py`

```python
"""Tests for calendar event querying."""

import json
from unittest.mock import MagicMock, patch

from src.calendar.query_events import filter_events_by_keywords, format_event


def test_filter_events_by_keywords_matches():
    events = [
        {"summary": "GGDisburse sync", "start": {}, "end": {}},
        {"summary": "Team lunch", "start": {}, "end": {}},
        {"summary": "Disbursement migration review", "start": {}, "end": {}},
    ]
    result = filter_events_by_keywords(events, ["GGDisburse", "disbursement"])
    assert len(result) == 2
    assert result[0]["summary"] == "GGDisburse sync"
    assert result[1]["summary"] == "Disbursement migration review"


def test_filter_events_by_keywords_case_insensitive():
    events = [{"summary": "your-project-name SYNC", "start": {}, "end": {}}]
    result = filter_events_by_keywords(events, ["GGDisburse"])
    assert len(result) == 1


def test_filter_events_by_keywords_no_match():
    events = [{"summary": "Team lunch", "start": {}, "end": {}}]
    result = filter_events_by_keywords(events, ["GGDisburse"])
    assert len(result) == 0


def test_filter_events_by_keywords_empty_keywords_returns_all():
    events = [
        {"summary": "Meeting A", "start": {}, "end": {}},
        {"summary": "Meeting B", "start": {}, "end": {}},
    ]
    result = filter_events_by_keywords(events, [])
    assert len(result) == 2


def test_format_event():
    event = {
        "summary": "GGDisburse sync",
        "start": {"dateTime": "2026-03-01T10:00:00-05:00"},
        "end": {"dateTime": "2026-03-01T11:00:00-05:00"},
        "attendees": [
            {"email": "alice@example.com", "displayName": "Alice"},
            {"email": "bob@example.com"},
        ],
        "htmlLink": "https://calendar.google.com/event?eid=abc",
    }
    formatted = format_event(event)
    assert formatted["summary"] == "GGDisburse sync"
    assert formatted["start"] == "2026-03-01T10:00:00-05:00"
    assert len(formatted["attendees"]) == 2
    assert formatted["link"] == "https://calendar.google.com/event?eid=abc"
```

**Step 2: Run test to verify it fails**

Run: `uv run python3 -m pytest tests/calendar/test_query_events.py -v`
Expected: FAIL — module not found.

**Step 3: Write the calendar query script**

Create `src/calendar/__init__.py` (empty file).

Create `src/calendar/query_events.py`:

```python
"""Query Google Calendar events by date range and keywords.

Reuses OAuth credentials from the gdocs-mcp server. The credentials
directory is configured via the calendar.credentials_dir config key.
The calendar.readonly scope is already granted in the existing token.

Usage:
    uv run python3 src/calendar/query_events.py \
        --since 2026-02-01 --until 2026-03-01 \
        --calendar-id primary \
        --keywords "GGDisburse" "disbursement" \
        --pretty
"""

import argparse
import json
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

GDOCS_MCP_DIR = Path(os.path.expanduser(os.environ.get("GDOCS_MCP_DIR", "~/git/ai-toolkit/mcp/gdocs-mcp")))
TOKEN_PATH = GDOCS_MCP_DIR / "token.json"
CREDENTIALS_PATH = GDOCS_MCP_DIR / "credentials.json"


def _load_credentials() -> Credentials:
    """Load OAuth credentials from the gdocs-mcp token file."""
    if not TOKEN_PATH.exists():
        print(
            f"Error: Token file not found at {TOKEN_PATH}.\n"
            f"Run the gdocs-mcp server first to authenticate.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(TOKEN_PATH) as f:
        token_data = json.load(f)
    with open(CREDENTIALS_PATH) as f:
        creds_data = json.load(f)

    # Handle both "installed" and "web" credential formats
    client_info = creds_data.get("installed") or creds_data.get("web", {})

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_info["client_id"],
        client_secret=client_info["client_secret"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token back
        updated = {**token_data, "access_token": creds.token}
        with open(TOKEN_PATH, "w") as f:
            json.dump(updated, f, indent=2)

    return creds


def query_events(
    calendar_id: str,
    time_min: str,
    time_max: str,
    max_results: int = 500,
) -> list[dict]:
    """Query calendar events in a date range.

    Args:
        calendar_id: Calendar ID (e.g. "primary").
        time_min: Start date as YYYY-MM-DD.
        time_max: End date as YYYY-MM-DD.
        max_results: Maximum events to return.

    Returns:
        List of event dicts from the Calendar API.
    """
    creds = _load_credentials()
    service = build("calendar", "v3", credentials=creds)

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=f"{time_min}T00:00:00Z",
            timeMax=f"{time_max}T23:59:59Z",
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def filter_events_by_keywords(events: list[dict], keywords: list[str]) -> list[dict]:
    """Filter events whose summary matches any keyword (case-insensitive).

    If keywords is empty, returns all events.
    """
    if not keywords:
        return events
    lower_keywords = [k.lower() for k in keywords]
    return [
        e
        for e in events
        if any(kw in e.get("summary", "").lower() for kw in lower_keywords)
    ]


def format_event(event: dict) -> dict:
    """Extract key fields from a calendar event for output."""
    start = event.get("start", {})
    end = event.get("end", {})
    attendees = [
        {
            "email": a.get("email", ""),
            "name": a.get("displayName", ""),
        }
        for a in event.get("attendees", [])
    ]
    return {
        "summary": event.get("summary", ""),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "attendees": attendees,
        "link": event.get("htmlLink", ""),
        "recurring": event.get("recurringEventId") is not None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query Google Calendar events. Outputs JSON to stdout.",
    )
    parser.add_argument("--since", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--calendar-id",
        action="append",
        default=[],
        help="Calendar ID (repeatable, default: primary)",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=[],
        help="Keywords to filter event summaries",
    )
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty-print JSON")

    args = parser.parse_args()
    calendar_ids = args.calendar_id or ["primary"]

    all_events = []
    for cal_id in calendar_ids:
        events = query_events(cal_id, args.since, args.until)
        all_events.extend(events)

    filtered = filter_events_by_keywords(all_events, args.keywords)
    formatted = [format_event(e) for e in filtered]

    indent = 2 if args.pretty else None
    json.dump(formatted, sys.stdout, indent=indent)
    print()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `uv run python3 -m pytest tests/calendar/test_query_events.py -v`
Expected: All 5 tests pass.

**Step 5: Commit**

```bash
git add src/calendar/ tests/calendar/
git commit -m "add Google Calendar event query script"
```

---

## Task 3: Create the project-status directory structure and config files

**Files:**

- Create: `work/project-status/config.yaml`
- Create: `work/project-status/project-configs/.gitkeep`

**Step 1: Create config.yaml**

Model this after `work/sprint-notes/config.yaml`. This file holds repo-level defaults shared across all projects.

```yaml
# Repo-level configuration for project status updates.
# Per-project settings go in project-configs/<project>.yaml.

jira:
  account_id: "${JIRA_ACCOUNT_ID}"

github:
  org: "${GITHUB_ORG}"
  format: markdown

calendar:
  credentials_dir: "${GDOCS_MCP_DIR}"

google_drive:
  project_status_folder: ""
  md_to_gdoc_script: "${MD_TO_GDOC_SCRIPT}"

project_names:
  COMPLY: "Compliance"
  DATA: "Data"
  BSR: "BSR"
  AGILE: "Agile"
  GGL: "GGL"
  VAST: "VAST"
  GGDM: "GGDisburse Migration"
  UPKEEP: "Upkeep"
```

**Step 2: Create project-configs directory**

```bash
mkdir -p work/project-status/project-configs
touch work/project-status/project-configs/.gitkeep
```

**Step 3: Commit**

```bash
git add work/project-status/
git commit -m "add project-status directory structure and config"
```

---

## Task 4: Create a sample project config

**Files:**

- Create: `work/project-status/project-configs/example.yaml`

This gives the user a template to copy when defining new projects. Use a realistic but clearly example project.

**Step 1: Create example config**

```yaml
# Example project configuration for project status updates.
# Copy this file and customize for your project:
#   cp example.yaml my-project.yaml

name: "Example Project"
description: "Brief description of the project"

github:
  repos:
    - your-org/repo-name
  # For overview mode (no --since flag), query PRs from last N days
  default_days: 30

jira:
  queries:
    # "default" is used when no audience-specific query exists
    default: "project = PROJ ORDER BY updated DESC"
    # Audience-specific queries (optional)
    slt: "project = PROJ AND type in (Epic, Story) ORDER BY priority DESC"
    engineering: "project = PROJ ORDER BY updated DESC"

calendar:
  calendar_ids:
    - primary
  keywords:
    - "project keyword"

audience_modes:
  slt:
    tone: "executive summary — outcomes, risks, decisions needed"
  engineering:
    tone: "detailed — PRs, issue breakdowns, blockers, technical decisions"
```

**Step 2: Commit**

```bash
git add work/project-status/project-configs/example.yaml
git commit -m "add example project config for project status updates"
```

---

## Task 5: Create the collection script

**Files:**

- Create: `src/collect_project_status.py`

**Step 1: Write the test**

Create: `tests/test_collect_project_status.py`

```python
"""Tests for collect_project_status.py."""

from pathlib import Path
from unittest.mock import patch

from src.collect_project_status import resolve_run_dir


def test_resolve_run_dir_first_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10"


def test_resolve_run_dir_second_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "2026-03-10").mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10-2"


def test_resolve_run_dir_third_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "2026-03-10").mkdir()
    (project_dir / "2026-03-10-2").mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10-3"
```

**Step 2: Run test to verify it fails**

Run: `uv run python3 -m pytest tests/test_collect_project_status.py -v`
Expected: FAIL — module not found.

**Step 3: Write the collection script**

Create `src/collect_project_status.py`:

```python
"""Collect project status data from GitHub, Jira, and Google Calendar.

Reads work/project-status/config.yaml for repo defaults and
work/project-status/project-configs/<project>.yaml for per-project settings.
Writes output to work/project-status/<project>/<date>[-n]/.

Usage:
    uv run python3 src/collect_project_status.py your-project-name --since 2026-02-01
    uv run python3 src/collect_project_status.py your-project-name
    uv run python3 src/collect_project_status.py your-project-name --dry-run
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
PROJECT_STATUS_DIR = REPO_ROOT / "work" / "project-status"
CONFIG_PATH = PROJECT_STATUS_DIR / "config.yaml"
PROJECT_CONFIGS_DIR = PROJECT_STATUS_DIR / "project-configs"


def load_config() -> dict:
    """Load the repo-level config."""
    if not CONFIG_PATH.exists():
        print(f"Error: Config not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_project_config(project_name: str) -> dict:
    """Load a project-level config."""
    project_yaml = PROJECT_CONFIGS_DIR / f"{project_name}.yaml"
    if not project_yaml.exists():
        print(
            f"Error: Project config not found at {project_yaml}\n"
            f"Available projects:",
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


def run_helper(script: str, args: list[str], output_path: Path | None = None) -> str:
    """Run a helper script via the current Python interpreter and return stdout."""
    cmd = [sys.executable, str(SRC_DIR / script)] + args
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


def collect_github_prs(
    run_dir: Path, project_config: dict, config: dict, since: str, until: str
) -> None:
    """Collect GitHub PR data for each repo in the project config."""
    gh_config = project_config.get("github", {})
    repos = gh_config.get("repos", [])
    org = config.get("github", {}).get("org", os.environ.get("GITHUB_ORG", ""))
    output_format = config.get("github", {}).get("format", "markdown")
    output_path = run_dir / "github" / "prs.md"

    if not repos:
        print("  No GitHub repos configured, skipping.")
        return

    # query_github_prs.py searches across an org. For project-scoped queries,
    # we run per-repo using the --owner flag with the full owner/repo as the
    # repo filter. We collect all results into one file.
    all_lines: list[str] = []
    for repo in repos:
        print(f"  GitHub PRs: {repo}, {since} to {until}")
        # Use gh search prs with --repo flag for repo-specific results
        owner = repo.split("/")[0] if "/" in repo else org
        repo_name = repo.split("/")[1] if "/" in repo else repo
        cmd = [
            sys.executable,
            str(SRC_DIR / "github" / "query_github_prs.py"),
            "--since", since,
            "--until", until,
            "--org", owner,
            "--format", output_format,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Warning: GitHub query for {repo} failed", file=sys.stderr)
            if result.stderr:
                print(f"  {result.stderr.strip()}", file=sys.stderr)
            continue

        # Filter output to only include sections for this specific repo
        output = result.stdout
        if output.strip():
            all_lines.append(output)

    if all_lines:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("\n".join(all_lines))
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def collect_jira_issues(
    run_dir: Path, project_config: dict, since: str | None, until: str | None
) -> None:
    """Run the project's Jira queries."""
    queries = project_config.get("jira", {}).get("queries", {})
    if not queries:
        print("  No Jira queries configured, skipping.")
        return

    for name, jql in queries.items():
        # Inject date placeholders if present
        if since and until:
            jql = jql.replace("{start_date}", since).replace("{end_date}", until)

        output_path = run_dir / "jira" / f"{name}.json"
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


def collect_calendar_events(
    run_dir: Path, project_config: dict, since: str, until: str
) -> None:
    """Collect calendar events matching project keywords."""
    cal_config = project_config.get("calendar", {})
    calendar_ids = cal_config.get("calendar_ids", [])
    keywords = cal_config.get("keywords", [])

    if not calendar_ids:
        print("  No calendar IDs configured, skipping.")
        return

    output_path = run_dir / "calendar" / "events.json"
    args = ["--since", since, "--until", until, "--pretty"]
    for cal_id in calendar_ids:
        args.extend(["--calendar-id", cal_id])
    if keywords:
        args.extend(["--keywords"] + keywords)

    print(f"  Calendar events: {since} to {until}, keywords={keywords}")
    output = run_helper(
        "calendar/query_events.py",
        args,
        output_path=output_path,
    )
    if output:
        try:
            count = len(json.loads(output))
            print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({count} events)")
        except json.JSONDecodeError:
            print(f"  Wrote {output_path.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(
        description="Collect project status data from GitHub, Jira, and Calendar.",
    )
    parser.add_argument(
        "project",
        help="Project config name (e.g., your-project-name — matches project-configs/your-project-name.yaml)",
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
            print(f"  Calendar: ids={cal_config.get('calendar_ids', [])}, keywords={cal_config.get('keywords', [])}")
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
    # In overview mode, don't inject dates into JQL (query all matching issues)
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
    print(f"  Or re-collect with: uv run python3 src/collect_project_status.py {args.project} --since {since}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `uv run python3 -m pytest tests/test_collect_project_status.py -v`
Expected: All 3 tests pass.

**Step 5: Commit**

```bash
git add src/collect_project_status.py tests/test_collect_project_status.py
git commit -m "add project status collection script"
```

---

## Task 6: Adapt GitHub PR collection for repo-scoped queries

The existing `query_github_prs.py` searches by org using `--author=@me`. For project status, we need PRs from all contributors in specific repos.

**Files:**

- Modify: `src/github/query_github_prs.py`

**Step 1: Write the test**

Add to `tests/github/test_query_github_prs.py`:

```python
"""Tests for GitHub PR query repo filtering."""

from src.github.query_github_prs import search_repo_prs


def test_search_repo_prs_builds_correct_command():
    # This is an integration-level test — skip if gh is not available
    import shutil
    import pytest

    if not shutil.which("gh"):
        pytest.skip("gh CLI not available")

    # Use a very narrow date range to minimize API calls
    # Just verify it doesn't crash — actual results depend on repo state
    result = search_repo_prs("your-org/some-repo", "2020-01-01", "2020-01-02")
    assert isinstance(result, list)
```

**Step 2: Add a `search_repo_prs` function to `query_github_prs.py`**

Add this function after the existing `search_reviewed_prs`:

```python
def search_repo_prs(repo: str, since: str, until: str) -> list[dict]:
    """Search for all PRs in a specific repo within the date range.

    Unlike search_authored_prs/search_reviewed_prs, this returns PRs from
    all contributors — useful for project-scoped status updates.
    """
    output = _run_gh([
        "search", "prs",
        f"--repo={repo}",
        f"--updated={since}..{until}",
        "--limit=200",
        f"--json={PR_JSON_FIELDS}",
    ])
    return json.loads(output) if output.strip() else []
```

**Step 3: Run tests**

Run: `uv run python3 -m pytest tests/github/ -v`
Expected: Pass.

**Step 4: Update collect_project_status.py to use search_repo_prs**

Replace the `collect_github_prs` function in `src/collect_project_status.py` with a version that imports and calls `search_repo_prs` directly instead of shelling out per-repo:

```python
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

    from github.query_github_prs import search_repo_prs, _format_markdown, _repo_name

    all_prs: list[dict] = []
    for repo in repos:
        print(f"  GitHub PRs: {repo}, {since} to {until}")
        prs = search_repo_prs(repo, since, until)
        all_prs.extend(prs)

    if all_prs:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "markdown":
            # Format all PRs together — _format_markdown groups by repo already
            content = _format_markdown(all_prs, [])
        else:
            content = json.dumps(all_prs, indent=2) + "\n"
        with open(output_path, "w") as f:
            f.write(content)
        print(f"  Wrote {output_path.relative_to(REPO_ROOT)} ({len(all_prs)} PRs)")
    else:
        print("  No PRs found.")
```

**Step 5: Commit**

```bash
git add src/github/query_github_prs.py src/collect_project_status.py tests/github/
git commit -m "add repo-scoped PR search for project status collection"
```

---

## Task 7: Create the Claude Code drafting skill

**Files:**

- Create: `~/git/ai-toolkit/claude-code/skills/project-status/SKILL.md`

**Step 1: Write the skill**

Create `~/git/ai-toolkit/claude-code/skills/project-status/SKILL.md`:

````markdown
# Skill: Project Status Update

## When to use

Use this skill when the user asks to generate a project status update. The
user will specify a project name that corresponds to a config file in
`work/project-status/project-configs/` in the performance repo.

## Arguments

- **project** (required): Project config name (e.g., `your-project-name`)
- **--since YYYY-MM-DD** (optional): Start date for activity. If omitted,
  uses the project's `default_days` setting (overview mode).
- **--audience slt|engineering** (optional): Drafting lens. Defaults to
  `engineering`.

## Process

### Phase 1: Collect data

Run the collection script:

```bash
uv run python3 src/collect_project_status.py {project} --since {since}
```

Or without `--since` for overview mode:

```bash
uv run python3 src/collect_project_status.py {project}
```

The script prints the run directory path. Note it for Phase 2.

### Phase 2: Load collected data

Read all files from the run directory
(`work/project-status/{project}/{date}[-n]/`):

1. **`run.yaml`** — Run metadata: project name, mode, date range, generation
   timestamp. Cite these dates in the draft.
2. **`jira/*.json`** — Jira issues from each configured query. The query name
   (filename stem) maps to an audience mode or "default".
3. **`github/prs.md`** — GitHub PR activity across the project's repos. All
   contributors, not just one person.
4. **`calendar/events.json`** — Calendar events matching project keywords.
   Only present in date-range mode.

If a file is missing, note it and continue with available data.

### Phase 3: Filter and analyze

#### Select the right Jira query results

If the `--audience` flag was provided, prefer the Jira query matching that
audience (e.g., `jira/slt.json` for `--audience slt`). Fall back to
`jira/default.json` if no audience-specific file exists.

#### Filter calendar events

Review `calendar/events.json` and drop events that are clearly unrelated to
the project despite matching keywords. For example, if a keyword is
"migration" and an event is "Bird Migration Documentary Watch Party," drop it.
Keep events where:

- The title clearly relates to the project
- Attendees overlap with contributors in the Jira/GitHub data
- The event description references project artifacts

Flag recurring events as lower signal than non-recurring ones.

#### Identify themes

Group the data by theme or workstream. Look for:

- Related Jira issues and PRs that form a coherent narrative
- Milestones reached or approaching
- Blockers and risks
- Decisions made (visible in PR merges, issue transitions, calendar meetings)

### Phase 4: Draft

Read the project config to get the `audience_modes` tone guidance for the
selected audience.

#### SLT / Executive audience

Write a concise status update. Structure:

```markdown
# {Project Name} — Status Update

**Period:** {since} to {until}
**Generated:** {today}

## Summary

2-3 sentence executive summary: where the project stands, key milestone
reached or approaching, top risk if any.

## Key Progress

### Milestone or outcome headline

1-2 sentence description of what was accomplished and why it matters.
Business impact, not technical detail.

### Another milestone

...

## Risks & Blockers

- Risk description and mitigation status
- ...

## Upcoming

- What's next in the near term
- Key decisions pending
```

Guidelines:

- No PR links or Jira issue keys unless they represent major milestones
- Lead with outcomes and business impact
- Keep the whole document under 1 page
- Use specific numbers when available

#### Engineering audience

Write a detailed status update. Structure:

```markdown
# {Project Name} — Status Update

**Period:** {since} to {until}
**Generated:** {today}

## Summary

2-3 sentence summary of project status and key activity.

## {Workstream or Theme}

### What happened

Narrative paragraphs with inline links to Jira issues
(`$JIRA_URL/browse/{KEY}`), GitHub PRs, and other
artifacts.

Cover:

- PRs merged and their significance
- Issues completed, in progress, blocked
- Technical decisions made
- Calendar meetings that drove decisions

### Status

Current state of this workstream: on track, at risk, blocked.

## {Another Workstream}

...

## Open Issues & Blockers

| Issue | Status | Owner | Notes |
| --- | --- | --- | --- |
| [KEY-123](url) | Blocked | @person | Waiting on X |

## Upcoming

- Next steps with expected dates if known
- PRs in review
- Decisions needed
```

Guidelines:

- Include Jira links and PR links throughout
- Attribute work to contributors where visible
- Be specific about what's blocked and why
- Include a table for open blockers

### Phase 5: Save

Save the draft to `{run_dir}/draft.md`.

Tell the user:

1. The draft is at `{run_dir}/draft.md`
2. Edit as needed, then upload via:
   `node $MD_TO_GDOC_SCRIPT upload {run_dir}/draft.md --title "{Project Name} Status Update {date}"`

## Tips

- For the SLT audience, less is more. Executives want to know: is this on
  track, what's the top risk, what do I need to do.
- For the engineering audience, thoroughness matters. Include links to
  everything so readers can dig deeper.
- If the Jira data is sparse but GitHub shows lots of PR activity, lean on
  the GitHub data for the narrative.
- If calendar events show a key meeting, mention the decision or outcome from
  that meeting if it's visible in subsequent Jira/GitHub activity.
- Cross-reference: if a PR references a Jira issue, connect them in the
  narrative. If a calendar meeting preceded a burst of PR activity, note the
  connection.
- The `project_names` mapping in `work/project-status/config.yaml` translates
  Jira project keys to readable names.

````

**Step 2: Verify skill location**

Run: `ls ~/git/ai-toolkit/claude-code/skills/project-status/SKILL.md`
Expected: File exists.

**Step 3: Commit (in ai-toolkit repo)**

```bash
cd ~/git/ai-toolkit
git add claude-code/skills/project-status/SKILL.md
git commit -m "add project-status drafting skill"
cd ~/git/performance
```

---

## Task 8: Create a test project config and do an end-to-end dry run

**Files:**

- Create: `work/project-status/project-configs/your-project-name.yaml` (or another real project)

**Step 1: Create a real project config**

Ask the user which project to configure first. Write the YAML based on their answer, following the example.yaml template. For example:

```yaml
name: "GGDisburse Migration"
description: "Migration from legacy disbursement system to GGDisburse"

github:
  repos:
    - your-org/your-project-name
  default_days: 30

jira:
  queries:
    default: "project = GGDM ORDER BY updated DESC"
    slt: "project = GGDM AND type in (Epic, Story) ORDER BY priority DESC"
    engineering: "project = GGDM ORDER BY updated DESC"

calendar:
  calendar_ids:
    - primary
  keywords:
    - "GGDisburse"
    - "disbursement"
    - "GGDM"

audience_modes:
  slt:
    tone: "executive summary — outcomes, risks, decisions needed"
  engineering:
    tone: "detailed — PRs, issue breakdowns, blockers, technical decisions"
```

**Step 2: Dry run**

Run: `uv run python3 src/collect_project_status.py your-project-name --since 2026-02-01 --dry-run`

Expected output showing what would be collected without hitting APIs.

**Step 3: Full collection run**

Run: `uv run python3 src/collect_project_status.py your-project-name --since 2026-02-01`

Expected: Creates `work/project-status/your-project-name/2026-03-10/` with `run.yaml`, `jira/`, `github/`, and `calendar/` data files.

**Step 4: Verify output**

Check that all expected files exist and contain data:

```bash
ls -la work/project-status/your-project-name/2026-03-10/
cat work/project-status/your-project-name/2026-03-10/run.yaml
```

**Step 5: Commit**

```bash
git add work/project-status/project-configs/your-project-name.yaml
git commit -m "add your-project-name project config"
```

---

## Task 9: Update CLAUDE.md with project status workflow documentation

**Files:**

- Modify: `CLAUDE.md`

**Step 1: Add project status section**

Add a new section to `CLAUDE.md` after the "Sprint notes workflow" section:

```markdown
## Project status updates workflow

1. Create project config: `cp work/project-status/project-configs/example.yaml work/project-status/project-configs/{project}.yaml`
2. Edit the project config with repos, JQL queries, calendar settings
3. Collect data: `uv run python3 src/collect_project_status.py {project} --since YYYY-MM-DD`
4. Draft via skill: `/project-status {project} --since YYYY-MM-DD --audience slt`
5. Edit `work/project-status/{project}/{date}/draft.md`
6. Upload to Google Docs via `md-to-gdoc.js`

Overview mode (no dates): omit `--since` to get a general status based on the
project's `default_days` setting. Calendar collection is skipped in this mode.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "document project status updates workflow in CLAUDE.md"
```
