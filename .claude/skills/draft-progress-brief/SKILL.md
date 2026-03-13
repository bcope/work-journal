---
name: draft-progress-brief
description: Draft a quarterly progress brief or performance review self-assessment from sprint notes, OKRs, and work artifacts. Use when the user says "draft progress brief", "progress brief", or "/draft-progress-brief".
---

# Skill: Draft Progress Brief

## When to use

Use this skill when the user asks to draft a quarterly progress brief, performance review, or similar self-assessment document.

## Process

1. **Read the form(s)** in `work/progress-briefs/<YEAR>-<QUARTER>/format/` to understand the questions and instructions.
2. **Read the evidence:**
   - Parse Jira CSV exports in `work/progress-briefs/<YEAR>-<QUARTER>/jira-issues/` using `src/work_journal/jira/parse_jira_csv.py` or by reading the CSV directly. The CSV format is the most structured; the RSS XML is an alternative.
   - Read all documents in `work/progress-briefs/<YEAR>-<QUARTER>/docs/`. These are authored memos, sprint notes, and investigation notes that provide narrative context for the work.
   - Note: Some files may contain embedded base64 images making them very large. Use `cut -c1-2000` via Bash to truncate long lines when the Read tool fails due to file size.
3. **Synthesize the evidence** into answers for each form question:
   - Use bullet points for clarity (the forms request this).
   - Be honest and concise -- focus on impactful accomplishments, challenges, and learnings.
   - Highlight completed goals, major deliverables, and wins.
   - Include collaboration, teamwork, and leadership examples.
   - Share how challenges or setbacks were handled.
   - Note skills or knowledge developed.
   - Quantify impact wherever possible (percentages, dollar amounts, issue counts).
4. **Save the draft** as a Markdown file in the `work/progress-briefs/<YEAR>-<QUARTER>/` directory.

## Form structure (as of Q4 2025)

There are two forms in Paylocity:

### Form 1: Brief overview of where things stand

- **What is working for you?**
- **What isn't working for you?**
- **Where do you need support to meet your OKRs?**
- **Additional Comments (Employee):** (optional)

### Form 2: Professional Development

- **Professional Development / Training** (1-3 focus areas, with resources to be utilized)

## Directory structure

```
work/progress-briefs/
  <YEAR>-<QUARTER>/
    format/              # PDF screenshots of the web forms
    jira-issues/         # Jira exports (CSV, XML, RSS XML)
    docs/                # Authored documents from the period
    <draft output>.md    # The generated draft
```

## Tips

- The Jira CSV has very wide rows with many columns. The most useful columns are: Summary, Issue key, Issue Type, Status, Project key, Created, Updated, Resolved.
- Sprint notes docs contain the most curated narrative of accomplishments and are the best source for "what is working" content.
- Memos (project plans, analysis memos, methodology docs) demonstrate leadership, analytical thinking, and initiative.
- Investigation notes show problem-solving and cross-functional collaboration.
- Count total completed issues as a quantitative data point.
