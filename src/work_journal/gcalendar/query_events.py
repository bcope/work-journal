"""Query Google Calendar events by date range and keywords.

Reuses OAuth credentials from the gdocs-mcp server. The credentials
directory is configured via the GDOCS_MCP_DIR environment variable.
The calendar.readonly scope is already granted in the existing token.

Usage:
    uv run python3 src/work_journal/gcalendar/query_events.py \
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

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GDOCS_MCP_DIR = Path(
    os.path.expanduser(os.environ.get("GDOCS_MCP_DIR", "~/git/ai-toolkit/mcp/gdocs-mcp"))
)
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
    return [e for e in events if any(kw in e.get("summary", "").lower() for kw in lower_keywords)]


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
