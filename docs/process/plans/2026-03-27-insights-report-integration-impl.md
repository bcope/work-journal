# Insights Report Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a two-stage pipeline (Python script + Claude Code skill) that parses and cleans Claude Code `/insights` HTML reports for use as inputs to sprint notes and progress briefs.

**Architecture:** Raw HTML goes into `work/shared/insights/raw/`, a Python script parses it into classified JSON in `parsed/`, a Claude Code skill makes judgment calls on flagged content and writes cleaned markdown to `cleaned/`. `collect.py` gates on the cleaned file existing. The draft-sprint-notes and draft-progress-brief skills read from the cleaned directory.

**Tech Stack:** Python 3 (BeautifulSoup4 for HTML parsing), pytest, existing config/paths infrastructure.

---

## Tasks

### Task 1: Add path constants and dependency

**Files:**

- Modify: `src/work_journal/paths.py:26-30`
- Modify: `pyproject.toml:7-13`

**Step 1: Add SHARED_DIR and INSIGHTS_DIR to paths.py**

Add after line 30 (`STANDUP_DIR = WORK_DIR / "standup"`):

```python
SHARED_DIR = WORK_DIR / "shared"
INSIGHTS_DIR = SHARED_DIR / "insights"
INSIGHTS_RAW_DIR = INSIGHTS_DIR / "raw"
INSIGHTS_PARSED_DIR = INSIGHTS_DIR / "parsed"
INSIGHTS_CLEANED_DIR = INSIGHTS_DIR / "cleaned"
```

**Step 2: Add beautifulsoup4 dependency**

```bash
uv add beautifulsoup4
```

**Step 3: Verify import works**

```bash
uv run python3 -c "from work_journal.paths import INSIGHTS_DIR; print(INSIGHTS_DIR)"
```

Expected: prints the absolute path ending in `work/shared/insights`

**Step 4: Commit**

```bash
git add src/work_journal/paths.py pyproject.toml uv.lock
git commit -m "add shared insights path constants and beautifulsoup4 dep"
```

---

### Task 2: Add insights keywords to shared config

**Files:**

- Modify: `config/shared.yaml`

**Step 1: Add the insights key to shared.yaml**

Append after the `google_drive` block:

```yaml
insights:
  work_keywords:
    - compliance
    - disbursement
    - "jira workflow"
    - standup
    - "sprint notes"
    - redesignation
    - netsuite
    - "financial automation"
    - "developer productivity"
    - "repo maintenance"
  personal_keywords:
    - "company evaluation"
    - "product category"
    - "audience profile"
    - "conversation strategy"
    - "obsidian clip"
```

**Step 2: Verify config loads**

```bash
uv run python3 -c "
from work_journal.config import load_shared_config
cfg = load_shared_config()
print(cfg['insights']['work_keywords'][:3])
"
```

Expected: prints first 3 work keywords. If `load_shared_config` doesn't exist, check
`config.py` for how shared config is loaded and adapt. The config module may only load
it as part of another loader -- if so, load it directly with PyYAML:

```bash
uv run python3 -c "
import yaml
from work_journal.paths import SHARED_CONFIG_PATH
cfg = yaml.safe_load(SHARED_CONFIG_PATH.read_text())
print(cfg['insights']['work_keywords'][:3])
"
```

**Step 3: Commit**

```bash
git add config/shared.yaml
git commit -m "add insights keyword config for work/personal classification"
```

---

### Task 3: Write the HTML parser with tests (TDD)

**Files:**

- Create: `src/work_journal/insights/__init__.py`
- Create: `src/work_journal/insights/parse.py`
- Create: `tests/test_parse_insights.py`

**Step 1: Create the package directory**

```bash
mkdir -p src/work_journal/insights
touch src/work_journal/insights/__init__.py
```

**Step 2: Write the test file**

Create `tests/test_parse_insights.py`. The tests use a minimal HTML fixture that
mirrors the real insights report structure. Each test targets one extraction function.

```python
"""Tests for insights HTML parser."""

import json

import pytest

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
      <div class="glance-section"><strong>What's working:</strong> Compliance automation is saving hours.</div>
      <div class="glance-section"><strong>What's hindering you:</strong> Credential failures block Jira.</div>
      <div class="glance-section"><strong>Quick wins to try:</strong> Add a preflight hook.</div>
      <div class="glance-section"><strong>Ambitious workflows:</strong> Batch processing pipelines.</div>
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
      <ul class="friction-examples"><li>JIRA_USER token expired</li><li>OBSIDIAN_CLIP_PATH unset</li></ul>
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
        assert classify_item("Company evaluation pipeline", WORK_KEYWORDS, PERSONAL_KEYWORDS) == "drop"

    def test_classify_unknown(self):
        assert classify_item("Improved error handling in scripts", WORK_KEYWORDS, PERSONAL_KEYWORDS) == "review"

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
```

**Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_parse_insights.py -v
```

Expected: all tests FAIL with `ModuleNotFoundError` or `ImportError` (module doesn't
exist yet).

**Step 4: Implement the parser module**

Create `src/work_journal/insights/parse.py`:

```python
"""Parse Claude Code /insights HTML reports into structured, classified JSON."""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup


def extract_project_areas(html: str) -> list[dict]:
    """Extract project area items from the 'What You Work On' section."""
    soup = BeautifulSoup(html, "html.parser")
    areas = []
    for div in soup.select(".project-area"):
        name_el = div.select_one(".area-name")
        count_el = div.select_one(".area-count")
        desc_el = div.select_one(".area-desc")
        areas.append(
            {
                "name": name_el.get_text(strip=True) if name_el else "",
                "session_count": count_el.get_text(strip=True) if count_el else "",
                "description": desc_el.get_text(strip=True) if desc_el else "",
            }
        )
    return areas


def extract_big_wins(html: str) -> list[dict]:
    """Extract big win items from the 'Impressive Things You Did' section."""
    soup = BeautifulSoup(html, "html.parser")
    wins = []
    for div in soup.select(".big-win"):
        title_el = div.select_one(".big-win-title")
        desc_el = div.select_one(".big-win-desc")
        wins.append(
            {
                "title": title_el.get_text(strip=True) if title_el else "",
                "description": desc_el.get_text(strip=True) if desc_el else "",
            }
        )
    return wins


def extract_friction_categories(html: str) -> list[dict]:
    """Extract friction category items from 'Where Things Go Wrong'."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for div in soup.select(".friction-category"):
        title_el = div.select_one(".friction-title")
        desc_el = div.select_one(".friction-desc")
        examples_el = div.select_one(".friction-examples")
        examples = (
            [li.get_text(strip=True) for li in examples_el.find_all("li")]
            if examples_el
            else []
        )
        items.append(
            {
                "title": title_el.get_text(strip=True) if title_el else "",
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "examples": examples,
            }
        )
    return items


def extract_narrative(html: str) -> str:
    """Extract the 'How You Use Claude Code' narrative text."""
    soup = BeautifulSoup(html, "html.parser")
    narrative_div = soup.select_one(".narrative")
    if not narrative_div:
        return ""
    parts = []
    for p in narrative_div.find_all("p"):
        parts.append(p.get_text(strip=True))
    key_insight = narrative_div.select_one(".key-insight")
    if key_insight:
        parts.append(key_insight.get_text(strip=True))
    return "\n\n".join(parts)


def extract_at_a_glance(html: str) -> dict:
    """Extract the At a Glance summary sections."""
    soup = BeautifulSoup(html, "html.parser")
    glance = soup.select_one(".at-a-glance")
    if not glance:
        return {
            "whats_working": "",
            "whats_hindering": "",
            "quick_wins": "",
            "ambitious_workflows": "",
        }
    sections = glance.select(".glance-section")
    keys = ["whats_working", "whats_hindering", "quick_wins", "ambitious_workflows"]
    result = {}
    for i, key in enumerate(keys):
        if i < len(sections):
            # Get text after the <strong> label
            text = sections[i].get_text(strip=True)
            # Remove the label prefix (e.g., "What's working:")
            strong = sections[i].find("strong")
            if strong:
                label = strong.get_text(strip=True)
                text = text[len(label) :].strip()
            # Remove trailing "see more" link text
            see_more = sections[i].select_one(".see-more")
            if see_more:
                link_text = see_more.get_text(strip=True)
                if text.endswith(link_text):
                    text = text[: -len(link_text)].strip()
            result[key] = text
        else:
            result[key] = ""
    return result


def extract_stats(html: str) -> list[dict]:
    """Extract aggregate chart bar data (label/value pairs)."""
    soup = BeautifulSoup(html, "html.parser")
    stats = []
    for row in soup.select(".bar-row"):
        label_el = row.select_one(".bar-label")
        value_el = row.select_one(".bar-value")
        if label_el and value_el:
            chart_title = ""
            chart_card = row.find_parent(class_="chart-card")
            if chart_card:
                title_el = chart_card.select_one(".chart-title")
                if title_el:
                    chart_title = title_el.get_text(strip=True)
            stats.append(
                {
                    "chart": chart_title,
                    "label": label_el.get_text(strip=True),
                    "value": value_el.get_text(strip=True),
                }
            )
    return stats


def classify_item(text: str, work_keywords: list[str], personal_keywords: list[str]) -> str:
    """Classify text as 'keep', 'drop', or 'review' based on keyword match."""
    text_lower = text.lower()
    has_work = any(kw.lower() in text_lower for kw in work_keywords)
    has_personal = any(kw.lower() in text_lower for kw in personal_keywords)
    if has_work and not has_personal:
        return "keep"
    if has_personal and not has_work:
        return "drop"
    if has_work and has_personal:
        return "review"
    return "review"


def parse_insights_html(
    html: str,
    work_keywords: list[str],
    personal_keywords: list[str],
) -> dict:
    """Parse insights HTML and classify all extractable content.

    Drops the Features, Patterns, and Horizon sections entirely.
    Returns a dict ready for JSON serialization.
    """
    # Extract sections that contain droppable content
    soup = BeautifulSoup(html, "html.parser")

    # Remove sections we don't want before extracting anything else
    # We need to remove them from the HTML to avoid their content
    # appearing in stats extraction
    drop_ids = ["section-features", "section-patterns", "section-horizon"]
    for section_id in drop_ids:
        heading = soup.find("h2", id=section_id)
        if heading:
            # Remove everything from this h2 until the next h2 or end
            to_remove = [heading]
            for sibling in heading.find_next_siblings():
                if sibling.name == "h2":
                    break
                to_remove.append(sibling)
            for el in to_remove:
                el.decompose()

    # Also remove feedback and fun-ending sections
    for cls in ["feedback-header", "feedback-section", "fun-ending"]:
        for el in soup.select(f".{cls}"):
            el.decompose()

    cleaned_html = str(soup)

    # Extract and classify
    project_areas = extract_project_areas(cleaned_html)
    for area in project_areas:
        area["classification"] = classify_item(
            f"{area['name']} {area['description']}",
            work_keywords,
            personal_keywords,
        )

    big_wins = extract_big_wins(cleaned_html)
    for win in big_wins:
        win["classification"] = classify_item(
            f"{win['title']} {win['description']}",
            work_keywords,
            personal_keywords,
        )

    friction_categories = extract_friction_categories(cleaned_html)
    for item in friction_categories:
        examples_text = " ".join(item["examples"])
        item["classification"] = classify_item(
            f"{item['title']} {item['description']} {examples_text}",
            work_keywords,
            personal_keywords,
        )

    narrative_text = extract_narrative(cleaned_html)
    at_a_glance = extract_at_a_glance(cleaned_html)
    stats = extract_stats(cleaned_html)

    return {
        "project_areas": project_areas,
        "big_wins": big_wins,
        "friction_categories": friction_categories,
        "narrative": {
            "text": narrative_text,
            "classification": "review",
        },
        "at_a_glance": {
            **at_a_glance,
            "classification": "review",
        },
        "stats": {
            "items": stats,
            "classification": "stats",
        },
    }
```

**Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_parse_insights.py -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/work_journal/insights/ tests/test_parse_insights.py
git commit -m "add insights HTML parser with keyword classification"
```

---

### Task 4: Write the CLI entry point with tests (TDD)

**Files:**

- Create: `src/work_journal/insights/cli.py`
- Create: `tests/test_insights_cli.py`

**Step 1: Write CLI tests**

Create `tests/test_insights_cli.py`:

```python
"""Tests for insights CLI (clean_insights.py)."""

import json
from pathlib import Path
from unittest.mock import patch

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


class TestRunParse:
    def test_creates_parsed_json(self, insights_dirs):
        raw_dir, parsed_dir, _ = insights_dirs
        (raw_dir / "2026-03-A.html").write_text(MINIMAL_HTML)
        keywords = {"work_keywords": ["compliance"], "personal_keywords": ["evaluation"]}

        run_parse("2026-03-A", raw_dir, parsed_dir, keywords)

        output = parsed_dir / "2026-03-A.json"
        assert output.exists()
        data = json.loads(output.read_text())
        assert "project_areas" in data
        assert data["project_areas"][0]["classification"] == "keep"

    def test_missing_raw_file_raises(self, insights_dirs):
        raw_dir, parsed_dir, _ = insights_dirs
        keywords = {"work_keywords": [], "personal_keywords": []}

        with pytest.raises(FileNotFoundError):
            run_parse("2026-03-A", raw_dir, parsed_dir, keywords)
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_insights_cli.py -v
```

Expected: FAIL with `ImportError`.

**Step 3: Implement the CLI module**

Create `src/work_journal/insights/cli.py`:

```python
"""CLI entry point for parsing insights HTML reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from work_journal.insights.parse import parse_insights_html
from work_journal.paths import (
    INSIGHTS_PARSED_DIR,
    INSIGHTS_RAW_DIR,
    SHARED_CONFIG_PATH,
)


def run_parse(
    sprint: str,
    raw_dir: Path,
    parsed_dir: Path,
    keywords: dict,
) -> Path:
    """Parse a raw insights HTML file into classified JSON.

    Returns the path to the output JSON file.
    Raises FileNotFoundError if the raw HTML doesn't exist.
    """
    raw_path = raw_dir / f"{sprint}.html"
    if not raw_path.exists():
        raise FileNotFoundError(f"No raw insights file at {raw_path}")

    html = raw_path.read_text()
    result = parse_insights_html(
        html,
        keywords.get("work_keywords", []),
        keywords.get("personal_keywords", []),
    )

    parsed_dir.mkdir(parents=True, exist_ok=True)
    output_path = parsed_dir / f"{sprint}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a Claude Code insights HTML report into classified JSON.",
    )
    parser.add_argument(
        "sprint",
        help="Sprint identifier (e.g., 2026-03-A)",
    )
    args = parser.parse_args()

    # Load keywords from shared config
    config = yaml.safe_load(SHARED_CONFIG_PATH.read_text())
    keywords = config.get("insights", {})

    output_path = run_parse(args.sprint, INSIGHTS_RAW_DIR, INSIGHTS_PARSED_DIR, keywords)
    print(f"Parsed: {output_path}")
    print(f"Next: run /clean-insights {args.sprint}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_insights_cli.py -v
```

Expected: all tests PASS.

**Step 5: Verify CLI works against real file**

```bash
uv run python3 src/work_journal/insights/cli.py 2026-03-A
```

Expected: creates `work/shared/insights/parsed/2026-03-A.json` and prints next step.
Note: raw file must already exist at `work/shared/insights/raw/2026-03-A.html`. If
not present, rename the existing file:

```bash
cp work/shared/insights/raw/claude-code-insights-2026-03-10-to-2026-03-26.html \
   work/shared/insights/raw/2026-03-A.html
```

**Step 6: Commit**

```bash
git add src/work_journal/insights/cli.py tests/test_insights_cli.py
git commit -m "add CLI entry point for insights parsing"
```

---

### Task 5: Add insights gate to collect.py

**Files:**

- Modify: `src/work_journal/collect.py:271-287`

**Step 1: Add the gate check after sprint dir validation**

In `collect.py`, after the `sprint_yaml_path` check (line 285) and before
`sprint_config = load_sprint_config(sprint_dir)` (line 287), add:

```python
    # Check for cleaned insights report
    from work_journal.paths import INSIGHTS_CLEANED_DIR

    insights_path = INSIGHTS_CLEANED_DIR / f"{args.sprint}.md"
    if not insights_path.exists():
        print(
            f"Error: No cleaned insights report found for {args.sprint}.\n"
            f"  1. Run /insights for the sprint date range\n"
            f"  2. Copy the HTML to work/shared/insights/raw/{args.sprint}.html\n"
            f"  3. Run: uv run python3 src/work_journal/insights/cli.py {args.sprint}\n"
            f"  4. Run: /clean-insights {args.sprint}\n"
            f"Then re-run collect.py.",
            file=sys.stderr,
        )
        sys.exit(1)
```

Note: move the `INSIGHTS_CLEANED_DIR` import to the top of the file with the other
path imports (line 38: `from work_journal.paths import REPO_ROOT, SPRINT_NOTES_DIR, SRC_DIR`).

**Step 2: Verify the gate works**

```bash
# Should fail with instructions (no cleaned file exists yet)
uv run python3 src/work_journal/collect.py 2026-03-A 2>&1 | head -10
```

Expected: prints the "Missing insights report" error and exits 1.

**Step 3: Commit**

```bash
git add src/work_journal/collect.py
git commit -m "gate collect.py on cleaned insights report"
```

---

### Task 6: Create the clean-insights skill

**Files:**

- Create: `.claude/skills/clean-insights/SKILL.md`

**Step 1: Create the skill directory and file**

```bash
mkdir -p .claude/skills/clean-insights
```

Create `.claude/skills/clean-insights/SKILL.md`:

````markdown
---
name: clean-insights
description: Clean a parsed insights report by making judgment calls on flagged content. Use when the user says "clean insights", "clean-insights", or "/clean-insights". Requires the parsing script to have been run first.
---

# Clean Insights Report

Transform a parsed Claude Code insights JSON file into a cleaned markdown document
suitable for use in sprint notes and progress briefs. The parsing script has already
classified items as `keep`, `drop`, `review`, or `stats` -- this skill handles the
judgment calls.

## Input

Read `work/shared/insights/parsed/{sprint}.json` where `{sprint}` is the argument
provided by the user (e.g., `2026-03-A`).

## Rules

### Classification handling

- **`keep` items** -- convert to markdown as-is.
- **`drop` items** -- exclude entirely. Do not mention them.
- **`review` items** -- read the content and decide:
  - **Drop** if entirely about personal projects with no transferable takeaway.
  - **Keep as-is** if actually work-relevant and the script just could not tell.
  - **Reframe** if there is a useful technique or learning embedded in personal
    project context. Extract the takeaway and frame it in terms of the skill,
    tool, or methodology -- not the personal domain. Example: "Built a reliable
    multi-phase automated research pipeline with structured output" rather than
    "Evaluated 12 companies using the evaluation skill."
- **`stats` items** -- include only if the metric is exceptional or trend-worthy.
  "Top tool was Read" is not interesting. Unusually high throughput, notable
  shifts in usage patterns, or strong outcome rates are worth a one-sentence
  callout.

### Content boundaries

Personal projects include: company evaluations, product category assessments,
audience profiles, conversation strategies, and any work in repos outside of
`~/git/`. Work projects include: anything referencing Jira, compliance,
disbursements, sprint notes, standup, developer productivity tooling, or repos
under `~/git/`.

When reframing, the goal is to capture **what was learned or built** without
exposing **what domain it was applied to**. Do not mention company names from
personal evaluations. Do not reference Obsidian or personal knowledge management
unless the technique is directly relevant to work tooling.

### Narrative and at-a-glance blocks

These always mix personal and work content. Rewrite them to:

- Remove personal project references entirely
- Preserve observations about work tools, workflows, and productivity
- Keep the tone factual and first-person-appropriate for sprint notes
- Be concise -- these are inputs to a draft, not the final document

## Output format

Save to `work/shared/insights/cleaned/{sprint}.md`:

```markdown
# Claude Code Insights: {sprint}

## Summary

(Rewritten at-a-glance content -- 2-4 sentences covering what worked,
what hindered, and any notable patterns. Work-relevant only.)

## Work Areas

- **Area Name** (~N sessions) -- Description.
- ...

## Accomplishments

- **Title** -- Description.
- ...

## Friction Points

- **Title** -- Description. Examples if useful.
- ...

## Usage Notes

(Only include this section if aggregate stats revealed something exceptional.
Otherwise omit the section entirely.)
```

## After saving

Print: "Cleaned insights saved. Ready for use by collect.py and draft skills."
````

**Step 2: Commit**

```bash
git add .claude/skills/clean-insights/
git commit -m "add clean-insights skill for LLM-assisted content filtering"
```

---

### Task 7: Update draft-sprint-notes skill to read insights

**Files:**

- Modify: `.claude/skills/draft-sprint-notes/SKILL.md`

**Step 1: Add insights to the input file list**

In the "Phase 1: Load collected data" section, after item 6 (`manual-notes.md`),
add a new item:

```markdown
7. **Claude Code insights** -- `work/shared/insights/cleaned/{sprint}.md`. Pre-cleaned
   insights report covering work areas, accomplishments, friction points, and usage
   notes. Use this to inform the Claude Code / developer productivity sections of the
   sprint notes. This file is always present (collect.py gates on it).
```

**Step 2: Commit**

```bash
git add .claude/skills/draft-sprint-notes/SKILL.md
git commit -m "add cleaned insights as input to draft-sprint-notes skill"
```

---

### Task 8: Update draft-progress-brief skill to read insights

**Files:**

- Modify: `.claude/skills/draft-progress-brief/SKILL.md`

**Step 1: Add insights to the evidence list**

In the "Read the evidence" section (step 2 of the process), add a new bullet:

```markdown
   - Read all cleaned insights reports in `work/shared/insights/cleaned/` whose
     sprint IDs fall within the quarter (up to six files: three months, two sprints
     each). These provide Claude Code usage patterns, productivity insights, and
     friction trends across the quarter. Missing files are expected for sprints
     before this feature was added -- note the gap and continue.
```

**Step 2: Commit**

```bash
git add .claude/skills/draft-progress-brief/SKILL.md
git commit -m "add cleaned insights as input to draft-progress-brief skill"
```

---

### Task 9: Run full checks and verify end-to-end

**Step 1: Run linting**

```bash
uv run ruff check .
uv run ruff format .
```

Fix any issues.

**Step 2: Run type checking**

```bash
uv run mypy src/
```

Fix any issues.

**Step 3: Run all tests**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 4: Run pre-commit hooks**

```bash
uv run pre-commit run --all-files
```

Fix any issues.

**Step 5: End-to-end smoke test**

Rename the sample file if not already done:

```bash
cp work/shared/insights/raw/claude-code-insights-2026-03-10-to-2026-03-26.html \
   work/shared/insights/raw/2026-03-A.html
```

Run the parser:

```bash
uv run python3 src/work_journal/insights/cli.py 2026-03-A
```

Expected: creates `work/shared/insights/parsed/2026-03-A.json`.

Inspect the output:

```bash
uv run python3 -c "
import json
data = json.load(open('work/shared/insights/parsed/2026-03-A.json'))
for area in data['project_areas']:
    print(f\"{area['classification']:6s} | {area['name']}\")
"
```

Expected: compliance/jira/standup items show `keep`, evaluation items show `drop`.

Then run `/clean-insights 2026-03-A` in Claude Code to produce the cleaned markdown.

**Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix lint/type issues from insights integration"
```
