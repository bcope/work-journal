"""Parse Claude Code /insights HTML reports into structured, classified JSON."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def extract_date_range(html: str) -> tuple[str, str] | None:
    """Extract the (start_date, end_date) tuple from the report subtitle.

    The subtitle reads like "1,570 messages across 158 sessions (197 total) |
    2026-03-16 to 2026-04-15". Returns None if the range cannot be located.
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", html)
    if not match:
        return None
    return match.group(1), match.group(2)


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
            [li.get_text(strip=True) for li in examples_el.find_all("li")] if examples_el else []
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
    date_range = extract_date_range(html)

    return {
        "date_range": {"start": date_range[0], "end": date_range[1]} if date_range else None,
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
