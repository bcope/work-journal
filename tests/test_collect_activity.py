"""Tests for claude_code/collect_activity.py."""

import json
from datetime import UTC, datetime, timedelta, timezone

from work_journal.claude_code.collect_activity import (
    _format_count,
    aggregate_tokens_by_day,
    analyze_conversation,
    format_markdown,
    load_history,
    write_tokens_json,
)


def _usage(n):
    return {
        "input_tokens": n,
        "output_tokens": n,
        "cache_read_input_tokens": n,
        "cache_creation_input_tokens": n,
    }


def _assistant_line(msg_id, model, ts, usage):
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {"id": msg_id, "model": model, "usage": usage, "content": []},
        }
    )


def _write_transcript(projects_path, project_path, session_id, lines):
    slug = project_path.replace("/", "-")
    session_dir = projects_path / slug
    session_dir.mkdir(parents=True)
    (session_dir / f"{session_id}.jsonl").write_text("\n".join(lines) + "\n")


# A window wide enough to include every entry in the legacy tests
WIDE_SINCE = datetime(2026, 1, 1, tzinfo=UTC)
WIDE_UNTIL = datetime(2027, 1, 1, tzinfo=UTC)


def _turn(ts, ms):
    return json.dumps(
        {"type": "system", "subtype": "turn_duration", "timestamp": ts, "durationMs": ms}
    )


def _tool_line(msg_id, ts, tool_id, name="Bash", inp=None):
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": inp or {}}
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {
                "id": msg_id,
                "model": "claude-fable-5",
                "usage": _usage(1),
                "content": [block],
            },
        }
    )


def test_analyze_conversation_filters_all_metrics_to_window(tmp_path):
    win_since = datetime(2026, 7, 15, tzinfo=UTC)
    win_until = datetime(2026, 7, 16, tzinfo=UTC)
    lines = [
        _turn("2026-07-10T10:00:00Z", 300_000),  # out
        _turn("2026-07-15T10:00:00Z", 60_000),  # in
        # out: tool call + Write doc + tokens
        _tool_line(
            "m1",
            "2026-07-10T10:01:00Z",
            "t1",
            "Write",
            {"file_path": "/Users/x/git/repo/a.md", "content": "xy"},
        ),
        # in
        _tool_line(
            "m2",
            "2026-07-15T10:01:00Z",
            "t2",
            "Write",
            {"file_path": "/Users/x/git/repo/b.md", "content": "xyz"},
        ),
        json.dumps({"type": "user", "timestamp": "2026-07-10T10:02:00Z"}),  # out
        json.dumps({"type": "user", "timestamp": "2026-07-15T10:02:00Z"}),  # in
    ]
    _write_transcript(tmp_path, "/Users/x/git/repo", "s1", lines)

    m = analyze_conversation(
        str(tmp_path), "/Users/x/git/repo", "s1", win_since, win_until, day_tz=UTC
    )

    assert m["thinking_time_ms"] == 60_000
    assert m["turn_count"] == 1
    assert sum(m["tool_calls"].values()) == 1
    assert list(m["documents"]) == ["/Users/x/git/repo/b.md"]
    assert m["user_messages"] == 1
    assert m["assistant_messages"] == 1
    assert list(m["tokens"]) == ["2026-07-15"]


def test_analyze_conversation_fully_out_of_window_is_empty(tmp_path):
    win_since = datetime(2026, 7, 15, tzinfo=UTC)
    win_until = datetime(2026, 7, 16, tzinfo=UTC)
    lines = [_turn("2026-07-10T10:00:00Z", 300_000)]
    _write_transcript(tmp_path, "/Users/x/git/repo", "s1", lines)

    m = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "s1", win_since, win_until)

    assert m["turn_count"] == 0
    assert m["thinking_time_ms"] == 0
    assert m["duration_ms"] == 0


def test_analyze_conversation_buckets_token_days_in_day_tz(tmp_path):
    # 00:30 UTC on 6/16 is still 6/15 in UTC-5
    tz = timezone(timedelta(hours=-5))
    lines = [_tool_line("m1", "2026-06-16T00:30:00Z", "t1")]
    _write_transcript(tmp_path, "/Users/x/git/repo", "s1", lines)

    m = analyze_conversation(
        str(tmp_path), "/Users/x/git/repo", "s1", WIDE_SINCE, WIDE_UNTIL, day_tz=tz
    )

    assert list(m["tokens"]) == ["2026-06-15"]


def test_analyze_conversation_tokens_by_model_by_date(tmp_path):
    usage_a = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 200,
    }
    usage_b = {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    lines = [
        # Same message id repeated: must count once
        _assistant_line("msg_1", "claude-opus-4-8", "2026-06-15T10:00:00.000Z", usage_a),
        _assistant_line("msg_1", "claude-opus-4-8", "2026-06-15T10:00:01.000Z", usage_a),
        # Different model, next UTC day
        _assistant_line("msg_2", "claude-haiku-4-5", "2026-06-16T00:30:00.000Z", usage_b),
        # No usage: skipped
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-06-16T01:00:00.000Z",
                "message": {"id": "msg_3", "model": "claude-opus-4-8", "content": []},
            }
        ),
        # Synthetic model: skipped
        _assistant_line("msg_4", "<synthetic>", "2026-06-16T02:00:00.000Z", usage_b),
        # Non-assistant entry: ignored
        json.dumps({"type": "user", "timestamp": "2026-06-16T03:00:00.000Z"}),
    ]
    _write_transcript(tmp_path, "/Users/x/git/repo", "sess1", lines)

    metrics = analyze_conversation(
        str(tmp_path), "/Users/x/git/repo", "sess1", WIDE_SINCE, WIDE_UNTIL, day_tz=UTC
    )

    assert metrics["tokens"] == {
        "2026-06-15": {"claude-opus-4-8": usage_a},
        "2026-06-16": {"claude-haiku-4-5": usage_b},
    }


def test_analyze_conversation_missing_file_has_empty_tokens(tmp_path):
    metrics = analyze_conversation(
        str(tmp_path), "/Users/x/git/repo", "nope", WIDE_SINCE, WIDE_UNTIL
    )
    assert metrics["tokens"] == {}


def test_load_history_filters_by_datetime_window(tmp_path):
    hist = tmp_path / "history.jsonl"
    base = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    entries = [
        {
            "display": "in",
            "timestamp": int(base.timestamp() * 1000),
            "project": "/Users/x/git/repo",
            "sessionId": "s1",
        },
        {
            "display": "before",
            "timestamp": int((base - timedelta(days=2)).timestamp() * 1000),
            "project": "/Users/x/git/repo",
            "sessionId": "s2",
        },
        # Exactly at the until bound: excluded (half-open window)
        {
            "display": "at-until",
            "timestamp": int(datetime(2026, 7, 16, tzinfo=UTC).timestamp() * 1000),
            "project": "/Users/x/git/repo",
            "sessionId": "s3",
        },
        # Non-work project: excluded
        {
            "display": "elsewhere",
            "timestamp": int(base.timestamp() * 1000),
            "project": "/Users/x/other/repo",
            "sessionId": "s4",
        },
    ]
    hist.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    sessions = load_history(
        str(hist),
        datetime(2026, 7, 15, tzinfo=UTC),
        datetime(2026, 7, 16, tzinfo=UTC),
        ["/Users/x/git"],
    )

    assert set(sessions) == {"s1"}


def test_aggregate_tokens_by_day_merges_sessions():
    sessions_by_project = {
        "/Users/x/git/a": [
            {"metrics": {"tokens": {"2026-06-15": {"claude-opus-4-8": _usage(10)}}}},
            {"metrics": {"tokens": {"2026-06-15": {"claude-opus-4-8": _usage(5)}}}},
        ],
        "/Users/x/git/b": [
            {"metrics": {"tokens": {"2026-06-15": {"claude-haiku-4-5": _usage(1)}}}},
        ],
    }
    days = aggregate_tokens_by_day(sessions_by_project)
    assert days == {
        "2026-06-15": {
            "claude-opus-4-8": _usage(15),
            "claude-haiku-4-5": _usage(1),
        }
    }


def test_format_count_suffixes():
    assert _format_count(1_500_000_000) == "1.5B"
    assert _format_count(4_224_400) == "4.2M"
    assert _format_count(361_000) == "361.0K"
    assert _format_count(532) == "532"


def test_format_markdown_token_line():
    session = {
        "session_id": "s1",
        "timestamp": 1750000000000,
        "display": "hello",
        "metrics": {
            "duration_ms": 0,
            "user_messages": 1,
            "assistant_messages": 1,
            "tool_calls": {},
            "tool_categories": {},
            "first_timestamp": None,
            "last_timestamp": None,
            "thinking_time_ms": 60000,
            "turn_count": 1,
            "documents": {},
            "tokens": {
                "2026-06-15": {
                    "claude-opus-4-8": {
                        "input_tokens": 1000,
                        "output_tokens": 2000,
                        "cache_read_input_tokens": 3000,
                        "cache_creation_input_tokens": 4000,
                    }
                }
            },
        },
    }
    md = format_markdown({"/Users/x/git/a": [session]}, WIDE_SINCE, WIDE_UNTIL)
    assert "- **Token usage:** 1.0K in / 2.0K out / 3.0K cache read / 4.0K cache write" in md


def test_format_markdown_no_token_line_when_absent():
    md = format_markdown({}, WIDE_SINCE, WIDE_UNTIL)
    assert "Token usage" not in md


def test_write_tokens_json(tmp_path):
    sessions_by_project = {
        "/Users/x/git/a": [
            {
                "metrics": {
                    "tokens": {
                        "2026-06-16": {"claude-opus-4-8": _usage(2)},
                        "2026-06-15": {"claude-opus-4-8": _usage(1)},
                    }
                }
            }
        ]
    }
    out = tmp_path / "sub" / "tokens-by-day.json"
    write_tokens_json(out, sessions_by_project, WIDE_SINCE, WIDE_UNTIL)
    data = json.loads(out.read_text())
    assert data["since"] == WIDE_SINCE.isoformat()
    assert data["until"] == WIDE_UNTIL.isoformat()
    assert [d["date"] for d in data["days"]] == ["2026-06-15", "2026-06-16"]
    assert data["days"][0]["models"] == {"claude-opus-4-8": _usage(1)}
