"""Tests for collect_progress_brief.py."""

from work_journal.collect_progress_brief import (
    format_char_count,
    format_duration_minutes,
    parse_char_count,
    parse_claude_code_stats,
    parse_duration_minutes,
)


def test_parse_duration_minutes():
    assert parse_duration_minutes("17h 52m") == 1072
    assert parse_duration_minutes("52m") == 52
    assert parse_duration_minutes("15h 0m") == 900
    assert parse_duration_minutes("") == 0


def test_format_duration_minutes():
    assert format_duration_minutes(1072) == "17h 52m"
    assert format_duration_minutes(52) == "52m"
    assert format_duration_minutes(900) == "15h 0m"
    assert format_duration_minutes(0) == "0m"


def test_parse_char_count():
    assert parse_char_count("361.0K") == 361000
    assert parse_char_count("1.2M") == 1200000
    assert parse_char_count("532") == 532


def test_format_char_count():
    assert format_char_count(4224400) == "4.2M"
    assert format_char_count(361000) == "361.0K"
    assert format_char_count(532) == "532"


def test_parse_claude_code_stats_sums_both_files(tmp_path):
    cc_dir = tmp_path / "claude-code"
    cc_dir.mkdir()
    (cc_dir / "sessions.md").write_text(
        "- **Total sessions:** 30\n"
        "- **Claude thinking time:** 17h 52m\n"
        "- **Total turns:** 173\n"
        "- **Total chars written:** 633.5K\n"
    )
    (cc_dir / "between-sprints-sessions.md").write_text(
        "- **Total sessions:** 5\n"
        "- **Claude thinking time:** 1h 17m\n"
        "- **Total turns:** 24\n"
        "- **Total chars written:** 210.4K\n"
    )
    totals = parse_claude_code_stats(tmp_path)
    assert totals == {
        "sessions": 35,
        "thinking_minutes": 1149,
        "turns": 197,
        "chars_written": 843900,
    }


def test_parse_claude_code_stats_missing_files(tmp_path):
    totals = parse_claude_code_stats(tmp_path)
    assert totals == {
        "sessions": 0,
        "thinking_minutes": 0,
        "turns": 0,
        "chars_written": 0,
    }
