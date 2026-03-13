from collections.abc import Callable


def format_quarter(quarter_str: str) -> str:
    return quarter_str


def format_sprint_short_name(sprint_name: str) -> str:
    # Example: "2026-01-A-Project-January" -> "2026-01-A"
    parts = sprint_name.split("-")
    return "-".join(parts[:3])


TEMPLATE_DIR_NAME_TO_FORMAT_FUNCTION: dict[str, Callable] = {
    "template-dir-quarter": format_quarter,
    "template-dir-sprint-short-name": format_sprint_short_name,
}
