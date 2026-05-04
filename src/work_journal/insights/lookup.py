"""Find cleaned insights files whose date range overlaps a sprint.

Cleaned insights files are named `{start}-to-{end}.md` where start and end are
YYYY-MM-DD. A file is considered relevant to a sprint if its date range overlaps
the sprint's date range.
"""

from __future__ import annotations

import re
from pathlib import Path

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-to-(\d{4}-\d{2}-\d{2})\.md$")


def parse_filename(name: str) -> tuple[str, str] | None:
    """Return (start, end) date strings from a cleaned insights filename."""
    match = FILENAME_RE.match(name)
    if not match:
        return None
    return match.group(1), match.group(2)


def find_matching_insights(
    start_date: str,
    end_date: str,
    cleaned_dir: Path,
) -> list[Path]:
    """Find all cleaned insights files whose date range overlaps [start, end].

    Returns paths sorted by the file's end date (most recent last). YYYY-MM-DD
    string comparison works because the format sorts lexicographically.
    """
    if not cleaned_dir.exists():
        return []

    matches: list[tuple[str, Path]] = []
    for path in cleaned_dir.glob("*.md"):
        parsed = parse_filename(path.name)
        if not parsed:
            continue
        file_start, file_end = parsed
        # Overlap test: file ends on/after sprint start AND file starts on/before sprint end
        if file_end >= start_date and file_start <= end_date:
            matches.append((file_end, path))

    matches.sort(key=lambda x: x[0])
    return [path for _, path in matches]
