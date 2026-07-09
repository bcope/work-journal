"""Snapshot daily notes and standup completed-work sections for a sprint.

Copies work/shared/daily-note/ files and extracts completed-work sections
from work/standup/ files into work/sprint-notes/{sprint}/daily-log/raw/.
See docs/process/plans/2026-07-09-daily-notes-integration-design.md.

Usage: uv run python3 src/work_journal/daily_log.py 2026-07-A
"""

import re
from datetime import date, timedelta

SINCE_RE = re.compile(
    r"^## What I did since the last working day \(\w+, (\d{4}-\d{2}-\d{2})\)",
    re.MULTILINE,
)

WHAT_I_DID_PREFIX = "## What I did since the last working day"
TOP_SECTION_PREFIXES = (
    WHAT_I_DID_PREFIX,
    "## What I'm doing today",
    "## Injected into sprint",
    "## Status check",
    "## Blockers",
    "## Data collection warnings",
)
DROP_SUBSECTIONS = ("### Recently closed (recent activity)", "### Claude Code")
COMPLETED_TODAY = "### Completed today"


def compute_window(sprint_info: dict, prior_sprint_info: dict | None) -> tuple[date, date]:
    """Window from prior sprint's close day (inclusive — sprints close midway
    into a day, so the rest of that day is sprintless) through sprint end."""
    if prior_sprint_info is not None:
        start = date.fromisoformat(prior_sprint_info["completeDate"][:10])
    else:
        start = date.fromisoformat(sprint_info["startDate"][:10])
    end = date.fromisoformat(sprint_info["endDate"][:10])
    return start, end


def parse_coverage(text: str, file_date: date) -> tuple[date, date]:
    """Coverage window of a standup file: [since-date, file-date].

    The 'since' date comes from the section header the standup script emits.
    If the header can't be parsed, fall back to a 3-day lookback rather than
    dropping the file.
    """
    match = SINCE_RE.search(text)
    if match:
        return date.fromisoformat(match.group(1)), file_date
    return file_date - timedelta(days=3), file_date


def extract_completed_sections(text: str) -> str:
    """Keep only completed-work evidence from a standup markdown file.

    Keeps the title, the 'What I did' section (minus the Recently-closed and
    Claude Code subsections), and the 'Completed today' subsection. Drops
    everything else. Boundaries are the exact section literals the standup
    script emits — the Commits body embeds its own #/## headers, so generic
    header matching would truncate it.
    """
    out: list[str] = []
    current_top: str | None = None
    keeping = False
    for line in text.splitlines():
        if line.startswith("# Stand-up"):
            out.append(line)
            continue
        top = next((p for p in TOP_SECTION_PREFIXES if line.startswith(p)), None)
        if top is not None:
            current_top = top
            keeping = top == WHAT_I_DID_PREFIX
            if keeping:
                out.append(line)
            continue
        if current_top == WHAT_I_DID_PREFIX:
            if line.startswith("### "):
                keeping = not line.startswith(DROP_SUBSECTIONS)
            if keeping:
                out.append(line)
        elif current_top == "## What I'm doing today":
            if line.startswith("### "):
                keeping = line.startswith(COMPLETED_TODAY)
            if keeping:
                out.append(line)
    return "\n".join(out).strip() + "\n"
