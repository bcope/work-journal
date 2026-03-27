"""Tests for insights HTML parser."""

import json

from work_journal.insights.parse import (
    classify_item,
    extract_at_a_glance,
    extract_big_wins,
    extract_friction_categories,
    extract_narrative,
    extract_project_areas,
    extract_stats,
    parse_insights_html,
)

# --- Fixtures ---

MINIMAL_HTML = """\
<!DOCTYPE html>
<html><head><title>Claude Code Insights</title></head>
<body><div class="container">
  <h1>Claude Code Insights</h1>
  <p class="subtitle">100 messages across 20 sessions | 2026-03-10 to 2026-03-26</p>

  <div class="at-a-glance">
    <div class="glance-title">At a Glance</div>
    <div class="glance-sections">
      <div class="glance-section">
        <strong>What's working:</strong> Compliance automation is saving hours.
      </div>
      <div class="glance-section">
        <strong>What's hindering you:</strong> Credential failures block Jira.
      </div>
      <div class="glance-section">
        <strong>Quick wins to try:</strong> Add a preflight hook.
      </div>
      <div class="glance-section">
        <strong>Ambitious workflows:</strong> Batch processing pipelines.
      </div>
    </div>
  </div>

  <h2 id="section-work">What You Work On</h2>
  <div class="project-areas">
    <div class="project-area">
      <div class="area-header">
        <span class="area-name">Compliance &amp; Financial Automation</span>
        <span class="area-count">~8 sessions</span>
      </div>
      <div class="area-desc">Building compliance redesignation pipelines.</div>
    </div>
    <div class="project-area">
      <div class="area-header">
        <span class="area-name">Company Evaluations</span>
        <span class="area-count">~16 sessions</span>
      </div>
      <div class="area-desc">Evaluating companies for personal research.</div>
    </div>
  </div>

  <div class="charts-row">
    <div class="chart-card">
      <div class="chart-title">What You Wanted</div>
      <div class="bar-row">
        <div class="bar-label">Bug Fixing</div>
        <div class="bar-track"><div class="bar-fill" style="width:100%"></div></div>
        <div class="bar-value">7</div>
      </div>
    </div>
  </div>

  <h2 id="section-usage">How You Use Claude Code</h2>
  <div class="narrative">
    <p>You delegate complex workflows to Claude.</p>
    <div class="key-insight"><strong>Key pattern:</strong> Workflow engine usage.</div>
  </div>

  <h2 id="section-wins">Impressive Things You Did</h2>
  <div class="big-wins">
    <div class="big-win">
      <div class="big-win-title">Jira Workflow Automation</div>
      <div class="big-win-desc">Automated watcher propagation using native Jira features.</div>
    </div>
    <div class="big-win">
      <div class="big-win-title">Company Evaluation Pipeline</div>
      <div class="big-win-desc">Built structured multi-phase evaluation skill.</div>
    </div>
  </div>

  <h2 id="section-friction">Where Things Go Wrong</h2>
  <div class="friction-categories">
    <div class="friction-category">
      <div class="friction-title">Credential Failures</div>
      <div class="friction-desc">Missing env vars block tool execution.</div>
      <ul class="friction-examples">
        <li>JIRA_USER token expired</li>
        <li>OBSIDIAN_CLIP_PATH unset</li>
      </ul>
    </div>
  </div>

  <h2 id="section-features">Existing CC Features to Try</h2>
  <div class="features-section"><p>Use hooks for preflight checks.</p></div>

  <h2 id="section-patterns">New Ways to Use Claude Code</h2>
  <div class="patterns-section"><p>Try headless mode.</p></div>

  <h2 id="section-horizon">On the Horizon</h2>
  <div class="horizon-section"><p>Autonomous batch processing.</p></div>
</div></body></html>
"""

WORK_KEYWORDS = ["compliance", "jira workflow", "standup", "sprint notes"]
PERSONAL_KEYWORDS = ["company evaluation", "audience profile"]


# --- Tests ---


class TestExtractProjectAreas:
    def test_extracts_all_areas(self):
        areas = extract_project_areas(MINIMAL_HTML)
        assert len(areas) == 2

    def test_area_fields(self):
        areas = extract_project_areas(MINIMAL_HTML)
        assert areas[0]["name"] == "Compliance & Financial Automation"
        assert areas[0]["session_count"] == "~8 sessions"
        assert "redesignation" in areas[0]["description"]

    def test_area_has_no_extra_keys(self):
        areas = extract_project_areas(MINIMAL_HTML)
        assert set(areas[0].keys()) == {"name", "session_count", "description"}


class TestExtractBigWins:
    def test_extracts_wins(self):
        wins = extract_big_wins(MINIMAL_HTML)
        assert len(wins) == 2
        assert wins[0]["title"] == "Jira Workflow Automation"

    def test_win_fields(self):
        wins = extract_big_wins(MINIMAL_HTML)
        assert set(wins[0].keys()) == {"title", "description"}


class TestExtractFrictionCategories:
    def test_extracts_friction(self):
        items = extract_friction_categories(MINIMAL_HTML)
        assert len(items) == 1
        assert items[0]["title"] == "Credential Failures"

    def test_friction_examples(self):
        items = extract_friction_categories(MINIMAL_HTML)
        assert len(items[0]["examples"]) == 2
        assert "JIRA_USER" in items[0]["examples"][0]


class TestExtractNarrative:
    def test_extracts_narrative(self):
        narrative = extract_narrative(MINIMAL_HTML)
        assert "delegate complex workflows" in narrative

    def test_includes_key_insight(self):
        narrative = extract_narrative(MINIMAL_HTML)
        assert "Workflow engine" in narrative


class TestExtractAtAGlance:
    def test_extracts_all_sections(self):
        glance = extract_at_a_glance(MINIMAL_HTML)
        assert "Compliance automation" in glance["whats_working"]
        assert "Credential failures" in glance["whats_hindering"]
        assert "preflight hook" in glance["quick_wins"]
        assert "Batch processing" in glance["ambitious_workflows"]


class TestExtractStats:
    def test_extracts_chart_data(self):
        stats = extract_stats(MINIMAL_HTML)
        assert len(stats) > 0
        bug_fixing = [s for s in stats if s["label"] == "Bug Fixing"]
        assert len(bug_fixing) == 1
        assert bug_fixing[0]["value"] == "7"


class TestClassifyItem:
    def test_classify_work(self):
        assert classify_item("Compliance pipeline work", WORK_KEYWORDS, PERSONAL_KEYWORDS) == "keep"

    def test_classify_personal(self):
        result = classify_item("Company evaluation pipeline", WORK_KEYWORDS, PERSONAL_KEYWORDS)
        assert result == "drop"

    def test_classify_unknown(self):
        result = classify_item(
            "Improved error handling in scripts",
            WORK_KEYWORDS,
            PERSONAL_KEYWORDS,
        )
        assert result == "review"

    def test_case_insensitive(self):
        assert classify_item("COMPLIANCE automation", WORK_KEYWORDS, PERSONAL_KEYWORDS) == "keep"


class TestParseInsightsHtml:
    def test_full_parse_returns_all_sections(self):
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        assert "project_areas" in result
        assert "big_wins" in result
        assert "friction_categories" in result
        assert "narrative" in result
        assert "at_a_glance" in result
        assert "stats" in result

    def test_items_are_classified(self):
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        compliance_area = result["project_areas"][0]
        assert compliance_area["classification"] == "keep"
        eval_area = result["project_areas"][1]
        assert eval_area["classification"] == "drop"

    def test_dropped_sections_excluded(self):
        """Features, patterns, and horizon sections should not appear."""
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        full_json = json.dumps(result)
        assert "preflight checks" not in full_json  # from features section
        assert "headless mode" not in full_json  # from patterns section
        assert "Autonomous batch" not in full_json  # from horizon section

    def test_narrative_tagged_review(self):
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        assert result["narrative"]["classification"] == "review"

    def test_at_a_glance_tagged_review(self):
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        assert result["at_a_glance"]["classification"] == "review"

    def test_stats_tagged(self):
        result = parse_insights_html(MINIMAL_HTML, WORK_KEYWORDS, PERSONAL_KEYWORDS)
        assert result["stats"]["classification"] == "stats"
