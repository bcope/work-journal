"""Snapshot daily notes and standup completed-work sections for a sprint.

Copies work/shared/daily-note/ files and extracts completed-work sections
from work/standup/ files into work/sprint-notes/{sprint}/daily-log/raw/.
See docs/process/plans/2026-07-09-daily-notes-integration-design.md.

Usage: uv run python3 src/work_journal/daily_log.py 2026-07-A
"""

from datetime import date


def compute_window(sprint_info: dict, prior_sprint_info: dict | None) -> tuple[date, date]:
    """Window from prior sprint's close day (inclusive — sprints close midway
    into a day, so the rest of that day is sprintless) through sprint end."""
    if prior_sprint_info is not None:
        start = date.fromisoformat(prior_sprint_info["completeDate"][:10])
    else:
        start = date.fromisoformat(sprint_info["startDate"][:10])
    end = date.fromisoformat(sprint_info["endDate"][:10])
    return start, end
