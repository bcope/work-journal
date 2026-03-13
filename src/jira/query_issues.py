"""Query Jira issues via JQL and output JSON.

Simplified port of JiraClient.search_issues from jira_maintenance.
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
API_V3 = f"{JIRA_URL}/rest/api/3"


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    session.auth = (JIRA_USER, JIRA_API_TOKEN)
    return session


def _paginate_jql(
    session: requests.Session,
    jql: str,
    max_results: int | None = None,
    page_size: int = 100,
    fields: list[str] | None = None,
) -> list[dict]:
    """Paginate through /search/jql using continuation tokens.

    Returns minimal issue objects (id + key) unless fields are specified.
    """
    collected: list[dict] = []
    next_token: str | None = None

    while True:
        body: dict = {"jql": jql, "maxResults": page_size}
        if next_token:
            body["nextPageToken"] = next_token
        if fields:
            body["fields"] = fields

        resp = session.post(f"{API_V3}/search/jql", json=body)
        resp.raise_for_status()
        data = resp.json()

        issues = data.get("issues", [])
        if not issues:
            break

        for issue in issues:
            collected.append(issue)
            if max_results is not None and len(collected) >= max_results:
                return collected

        next_token = data.get("nextPageToken")
        if not next_token:
            break

    return collected


def _bulk_fetch(
    session: requests.Session,
    ids_or_keys: list[str],
    fields: list[str] | None = None,
    chunk_size: int = 100,
) -> list[dict]:
    """Fetch full issue data using /issue/bulkfetch in chunks of up to 100."""
    results: list[dict] = []

    for i in range(0, len(ids_or_keys), chunk_size):
        batch = ids_or_keys[i : i + chunk_size]
        body: dict = {"issueIdsOrKeys": batch}
        if fields:
            body["fields"] = fields

        resp = session.post(f"{API_V3}/issue/bulkfetch", json=body)
        resp.raise_for_status()
        results.extend(resp.json().get("issues", []))

    return results


def search_issues(
    jql: str,
    fields: list[str] | None = None,
    max_results: int | None = None,
    page_size: int = 100,
) -> list[dict]:
    """Search for issues matching a JQL query and return full results.

    Always uses the two-step approach: collect issue ids via /search/jql, then
    fetch field data via /issue/bulkfetch. The bulkfetch endpoint returns all
    fields by default when none are specified, so --fields acts as a filter to
    limit the response rather than enable field retrieval.
    """
    session = _make_session()

    minimal = _paginate_jql(session, jql, max_results=max_results, page_size=page_size)
    keys = [i.get("key") or i.get("id") for i in minimal if i.get("key") or i.get("id")]
    if not keys:
        return []
    return _bulk_fetch(session, keys, fields=fields)


def main():
    parser = argparse.ArgumentParser(
        description="Query Jira issues via JQL. Outputs JSON to stdout.",
    )
    parser.add_argument("jql", help="JQL query string")
    parser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=None,
        help="Issue fields to retrieve (e.g. summary status assignee)",
    )
    parser.add_argument(
        "--max-results", "-m",
        type=int,
        default=None,
        help="Maximum number of issues to return (default: all)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Number of issues per API page (default: 100)",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print JSON output",
    )

    args = parser.parse_args()

    if not JIRA_USER or not JIRA_API_TOKEN:
        print("Error: JIRA_USER and JIRA_API_TOKEN environment variables must be set.", file=sys.stderr)
        sys.exit(1)

    try:
        issues = search_issues(
            jql=args.jql,
            fields=args.fields,
            max_results=args.max_results,
            page_size=args.page_size,
        )
    except requests.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        if e.response is not None:
            print(e.response.text, file=sys.stderr)
        sys.exit(1)

    indent = 2 if args.pretty else None
    json.dump(issues, sys.stdout, indent=indent)
    print()


if __name__ == "__main__":
    main()
