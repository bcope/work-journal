"""Tests for collect_progress_brief.py."""

import json

from work_journal.collect_progress_brief import (
    format_char_count,
    format_duration_minutes,
    load_token_usage,
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


def _usage(n):
    return {
        "input_tokens": n,
        "output_tokens": n,
        "cache_read_input_tokens": n,
        "cache_creation_input_tokens": n,
    }


def test_load_token_usage_sums_files_days_models(tmp_path):
    cc_dir = tmp_path / "claude-code"
    cc_dir.mkdir()
    (cc_dir / "tokens-by-day.json").write_text(
        json.dumps(
            {
                "days": [
                    {"date": "2026-06-15", "models": {"claude-opus-4-8": _usage(10)}},
                    {"date": "2026-06-16", "models": {"claude-haiku-4-5": _usage(1)}},
                ]
            }
        )
    )
    (cc_dir / "between-sprints-tokens-by-day.json").write_text(
        json.dumps({"days": [{"date": "2026-06-11", "models": {"claude-opus-4-8": _usage(5)}}]})
    )
    totals = load_token_usage(tmp_path)
    assert totals == _usage(16)


def test_load_token_usage_missing_files(tmp_path):
    assert load_token_usage(tmp_path) == _usage(0)


def test_parse_claude_code_stats_missing_files(tmp_path):
    totals = parse_claude_code_stats(tmp_path)
    assert totals == {
        "sessions": 0,
        "thinking_minutes": 0,
        "turns": 0,
        "chars_written": 0,
    }
