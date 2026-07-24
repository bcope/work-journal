"""Tests for claude_code/collect_activity.py."""

import json

from work_journal.claude_code.collect_activity import (
    aggregate_tokens_by_day,
    analyze_conversation,
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

    metrics = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "sess1")

    assert metrics["tokens"] == {
        "2026-06-15": {"claude-opus-4-8": usage_a},
        "2026-06-16": {"claude-haiku-4-5": usage_b},
    }


def test_analyze_conversation_missing_file_has_empty_tokens(tmp_path):
    metrics = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "nope")
    assert metrics["tokens"] == {}


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
