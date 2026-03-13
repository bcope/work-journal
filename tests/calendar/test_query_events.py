"""Tests for calendar event querying."""

from work_journal.calendar.query_events import filter_events_by_keywords, format_event


def test_filter_events_by_keywords_matches():
    events = [
        {"summary": "GGDisburse sync", "start": {}, "end": {}},
        {"summary": "Team lunch", "start": {}, "end": {}},
        {"summary": "Disbursement migration review", "start": {}, "end": {}},
    ]
    result = filter_events_by_keywords(events, ["GGDisburse", "disbursement"])
    assert len(result) == 2
    assert result[0]["summary"] == "GGDisburse sync"
    assert result[1]["summary"] == "Disbursement migration review"


def test_filter_events_by_keywords_case_insensitive():
    events = [{"summary": "GGDISBURSE SYNC", "start": {}, "end": {}}]
    result = filter_events_by_keywords(events, ["GGDisburse"])
    assert len(result) == 1


def test_filter_events_by_keywords_no_match():
    events = [{"summary": "Team lunch", "start": {}, "end": {}}]
    result = filter_events_by_keywords(events, ["GGDisburse"])
    assert len(result) == 0


def test_filter_events_by_keywords_empty_keywords_returns_all():
    events = [
        {"summary": "Meeting A", "start": {}, "end": {}},
        {"summary": "Meeting B", "start": {}, "end": {}},
    ]
    result = filter_events_by_keywords(events, [])
    assert len(result) == 2


def test_format_event():
    event = {
        "summary": "GGDisburse sync",
        "start": {"dateTime": "2026-03-01T10:00:00-05:00"},
        "end": {"dateTime": "2026-03-01T11:00:00-05:00"},
        "attendees": [
            {"email": "alice@example.com", "displayName": "Alice"},
            {"email": "bob@example.com"},
        ],
        "htmlLink": "https://calendar.google.com/event?eid=abc",
    }
    formatted = format_event(event)
    assert formatted["summary"] == "GGDisburse sync"
    assert formatted["start"] == "2026-03-01T10:00:00-05:00"
    assert len(formatted["attendees"]) == 2
    assert formatted["link"] == "https://calendar.google.com/event?eid=abc"
    assert formatted["recurring"] is False


def test_format_event_recurring():
    event = {
        "summary": "Weekly standup",
        "start": {"date": "2026-03-01"},
        "end": {"date": "2026-03-01"},
        "recurringEventId": "abc123",
    }
    formatted = format_event(event)
    assert formatted["recurring"] is True
    assert formatted["start"] == "2026-03-01"
