"""Query Jira sprint metadata via the Agile API.

Port of JiraClient.get_all_sprints_by_board_id and get_sprint from jira_maintenance.
Reads credentials from environment variables JIRA_USER and JIRA_API_TOKEN.
"""

import argparse
import json
import os
import sys

import requests

JIRA_USER = os.environ.get("JIRA_USER", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_URL = os.environ.get("JIRA_URL", "")
AGILE_API = f"{JIRA_URL}/rest/agile/1.0"

DEFAULT_BOARD_ID = int(os.environ.get("JIRA_BOARD_ID", "0"))
JIRA_SPRINT_START_ID = int(os.environ.get("JIRA_SPRINT_START_ID", "0"))


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    session.auth = (JIRA_USER, JIRA_API_TOKEN)
    return session


def list_sprints(
    session: requests.Session,
    board_id: int,
    state: str = "active,closed",
    page_size: int = 50,
    start_at: int = JIRA_SPRINT_START_ID,
) -> list[dict]:
    """List all sprints for a board, paginating through results.

    See docs: https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-sprint-get

    Args:
        board_id: The Jira board ID.
        state: Comma-separated sprint states to filter by.
            Valid values: future, active, closed.
        start_at: Starting sprint index for pagination (default: $JIRA_SPRINT_START_ID).
    """
    sprints: list[dict] = []

    while True:
        resp = session.get(
            f"{AGILE_API}/board/{board_id}/sprint",
            params={"maxResults": page_size, "state": state, "startAt": start_at},
        )
        resp.raise_for_status()
        data = resp.json()

        values = data.get("values", [])
        sprints.extend(values)

        if data.get("isLast", True):
            break
        start_at += page_size

    return sprints


def get_sprint(session: requests.Session, sprint_id: int) -> dict:
    """Get a single sprint by ID."""
    resp = session.get(f"{AGILE_API}/sprint/{sprint_id}")
    resp.raise_for_status()
    return resp.json()


def find_previous_sprint(
    session: requests.Session, board_id: int, current_sprint: dict
) -> dict | None:
    """Find the most recent closed sprint that ended before the current one started.

    Returns None if no prior sprint is found.
    """
    current_start = current_sprint.get("startDate", "")
    if not current_start:
        return None

    closed = list_sprints(session, board_id, state="closed")
    # Sort by endDate descending so the most recent is first
    closed.sort(key=lambda s: s.get("endDate", ""), reverse=True)

    for sprint in closed:
        if sprint.get("id") == current_sprint.get("id"):
            continue
        end = sprint.get("endDate", "")
        if end and end < current_start:
            return sprint

    return None


def find_sprint_by_name(session: requests.Session, board_id: int, name: str) -> dict | None:
    """Search all sprints on a board for one matching the given name.

    Searches across all states (future, active, closed) and returns the
    first sprint whose name contains the search string (case-insensitive).
    """
    all_sprints = list_sprints(session, board_id, state="future,active,closed")
    name_lower = name.lower()
    for sprint in all_sprints:
        if name_lower in sprint.get("name", "").lower():
            return sprint
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Query Jira sprint metadata. Outputs JSON to stdout.",
    )

    # Lookup modes (mutually exclusive in practice, but argparse handles priority)
    parser.add_argument(
        "--sprint-id",
        type=int,
        default=None,
        help="Get a specific sprint by its ID",
    )
    parser.add_argument(
        "--sprint-name",
        default=None,
        help="Search for a sprint by name on the given board",
    )
    parser.add_argument(
        "--board-id",
        type=int,
        default=DEFAULT_BOARD_ID,
        help="Board ID to query (default: $JIRA_BOARD_ID)",
    )
    parser.add_argument(
        "--state",
        default=None,
        help="List sprints filtered by state: future, active, closed (comma-separated)",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="Pretty-print JSON output",
    )

    args = parser.parse_args()

    if not JIRA_USER or not JIRA_API_TOKEN:
        print(
            "Error: JIRA_USER and JIRA_API_TOKEN environment variables must be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    session = _make_session()
    indent = 2 if args.pretty else None

    try:
        if args.sprint_id:
            result = get_sprint(session, args.sprint_id)
        elif args.sprint_name:
            result = find_sprint_by_name(session, args.board_id, args.sprint_name)
            if result is None:
                print(
                    f"Error: No sprint matching '{args.sprint_name}'"
                    f" found on board {args.board_id}.",
                    file=sys.stderr,
                )
                sys.exit(1)
        elif args.state:
            result = list_sprints(session, args.board_id, state=args.state)
        else:
            # Default: list active sprints on the board
            result = list_sprints(session, args.board_id, state="active")
    except requests.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        if e.response is not None:
            print(e.response.text, file=sys.stderr)
        sys.exit(1)

    json.dump(result, sys.stdout, indent=indent)
    print()


if __name__ == "__main__":
    main()
