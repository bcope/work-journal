"""Tests for insights CLI (cli.py)."""

import json

import pytest

from work_journal.insights.cli import run_parse


@pytest.fixture()
def insights_dirs(tmp_path):
    """Create the raw/parsed/cleaned directory structure."""
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"
    cleaned_dir = tmp_path / "cleaned"
    raw_dir.mkdir()
    parsed_dir.mkdir()
    cleaned_dir.mkdir()
    return raw_dir, parsed_dir, cleaned_dir


MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><div class="container">
  <p class="subtitle">100 messages | 2026-03-16 to 2026-04-15</p>
  <div class="at-a-glance">
    <div class="glance-sections">
      <div class="glance-section"><strong>What's working:</strong> Good stuff.</div>
      <div class="glance-section"><strong>What's hindering you:</strong> Bad stuff.</div>
      <div class="glance-section"><strong>Quick wins to try:</strong> Try this.</div>
      <div class="glance-section"><strong>Ambitious workflows:</strong> Do that.</div>
    </div>
  </div>
  <div class="project-areas">
    <div class="project-area">
      <div class="area-header">
        <span class="area-name">Compliance Work</span>
        <span class="area-count">~5 sessions</span>
      </div>
      <div class="area-desc">Building compliance tools.</div>
    </div>
  </div>
</div></body></html>
"""

HTML_WITHOUT_DATE_RANGE = """\
<!DOCTYPE html>
<html><body><div class="container">
  <p class="subtitle">No dates here</p>
</div></body></html>
"""


class TestRunParse:
    def test_creates_parsed_json_named_by_date_range(self, insights_dirs):
        raw_dir, parsed_dir, _ = insights_dirs
        (raw_dir / "anything.html").write_text(MINIMAL_HTML)
        keywords = {"work_keywords": ["compliance"], "personal_keywords": ["evaluation"]}

        run_parse(raw_dir / "anything.html", parsed_dir, keywords)

        output = parsed_dir / "2026-03-16-to-2026-04-15.json"
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["date_range"] == {"start": "2026-03-16", "end": "2026-04-15"}
        assert "project_areas" in data
        assert data["project_areas"][0]["classification"] == "keep"

    def test_missing_raw_file_raises(self, insights_dirs):
        raw_dir, parsed_dir, _ = insights_dirs
        keywords = {"work_keywords": [], "personal_keywords": []}

        with pytest.raises(FileNotFoundError):
            run_parse(raw_dir / "missing.html", parsed_dir, keywords)

    def test_missing_date_range_raises(self, insights_dirs):
        raw_dir, parsed_dir, _ = insights_dirs
        (raw_dir / "no-dates.html").write_text(HTML_WITHOUT_DATE_RANGE)
        keywords = {"work_keywords": [], "personal_keywords": []}

        with pytest.raises(ValueError, match="Could not extract date range"):
            run_parse(raw_dir / "no-dates.html", parsed_dir, keywords)
