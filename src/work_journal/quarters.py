"""Quarter-sprint mapping utilities.

Maps between quarter identifiers (e.g., '2026-Q1') and sprint directory names
(e.g., '2026-01-A'). Sprint naming convention: YYYY-MM-[A|B], two sprints per
month, six per quarter.
"""


def quarter_sprints(quarter: str) -> list[str]:
    """Return the 6 sprint directory names for a quarter.

    >>> quarter_sprints("2026-Q1")
    ['2026-01-A', '2026-01-B', '2026-02-A', '2026-02-B', '2026-03-A', '2026-03-B']
    """
    year, q_str = quarter.split("-Q")
    q = int(q_str)
    months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}[q]
    return [f"{year}-{m:02d}-{half}" for m in months for half in ("A", "B")]


def sprint_to_quarter(sprint: str) -> str:
    """Map a sprint directory name to its quarter identifier.

    >>> sprint_to_quarter("2026-03-B")
    '2026-Q1'
    >>> sprint_to_quarter("2026-12-A")
    '2026-Q4'
    """
    parts = sprint.split("-")
    year = parts[0]
    month = int(parts[1])
    q = (month - 1) // 3 + 1
    return f"{year}-Q{q}"
