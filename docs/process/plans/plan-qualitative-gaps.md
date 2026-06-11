# Plan: Qualitative Gaps in Sprint Notes Data

Assessment of what's missing from the current automated pipeline, based on the
2026-02-A dry run and comparison with the manually-authored 2025-12-A/B notes.

## What the dry run produced well

The automated pipeline captured the **what** effectively:

- Jira issues gave us a complete inventory of work touched (40 issues, 7 projects)
- GitHub PRs connected code changes to Jira issues via branch naming
- Git commits corroborated the PR data with local history
- Google Docs search found relevant documents modified during the sprint
- Jira issue descriptions provided technical context for key items
- The counterfactual analysis doc gave rich narrative for the CA AB 488 theme

## What's missing

### 1. Stakeholder context and collaboration narrative

The 2025-12-A/B notes mention working "with Josh" on FXecute improvements and
coordinating with Jacob on the Nike/Benevity change. The automated data tells us
*what* was done but not *who was involved* or *who requested it*.

**Where this context lives:**
- Email threads (requests from stakeholders, coordination)
- Calendar events (1:1s, meetings where decisions were made)
- Slack messages (ad-hoc requests, sharing results)
- Jira comments (sometimes — but often the real conversation is elsewhere)

**Gap severity:** High. Sprint notes that read "I did X" are weaker than "I
worked with Y on X because Z asked for it." The collaboration narrative is what
makes sprint notes useful for performance reviews.

### 2. Decision context — the "why now"

The draft explains *what* was built but doesn't always explain *why this sprint*.
For example: Who requested the Jira user pruning? Was the Confluence cost analysis
prompted by a budget review? Was the Gift Aid conversion code change requested by
Andy in the UK?

**Where this context lives:**
- Email (requests, escalations, executive asks)
- Calendar (meeting titles hint at what prompted work)
- Slack (original request messages — we captured one via Jira's "created from Slack")
- Jira comments (decision rationale, stakeholder sign-off)

**Gap severity:** Medium. The current draft has some of this from Jira descriptions
(e.g., Andy's Slack message in BSR-2220), but it's inconsistent.

### 3. Impact observed vs. impact projected

The draft cites "projected 78% reduction in redesignations" — but the 2025-12-A/B
notes cite actual observed results with a Slack link as evidence. The difference
is significant: projected impact is a promise, observed impact is proof.

**Where this context lives:**
- Slack (sharing results, celebrating wins, team reactions)
- Email (reporting results to stakeholders)
- Google Sheets (dashboards, metrics tracking)
- Jira comments (post-deployment verification)

**Gap severity:** High. The most compelling sprint notes entries are the ones with
"this change led to a 75% reduction" backed by evidence.

### 4. Cross-functional work and meetings

The GGL time tracking issues show categories like "Meetings," "Sprint Planning,"
"Code Review," and "Performance Management Trainings." But the draft doesn't
reflect any of this. What happened in those meetings? What was decided?

**Where this context lives:**
- Calendar events (meeting titles, attendees, attached agendas)
- Google Docs (meeting notes, shared agendas)
- Email (follow-up action items)

**Gap severity:** Low-medium for sprint notes specifically (meetings are usually
not headline material), but high for quarterly progress briefs where leadership
and collaboration matter.

### 5. Work-in-progress narrative and carryover

VAST-1345 (disbursement policy changes) is "in sign-off" — but the draft doesn't
explain what happened this sprint to advance it. GGDM-293 and BSR-1982 are open.
AGILE-375 is an open bug investigation. What progress was made? What's blocked?

**Where this context lives:**
- Jira comments (status updates, blockers)
- Prior sprint notes (what was the state at end of last sprint?)
- Email/Slack (discussions about blockers)

**Gap severity:** Medium. Carryover items are important for showing sustained
effort on long-running initiatives.

### 6. The DAFPay discovery meeting doc

The Google Docs search found "2025-09-15 - DAFPay discovery planning meeting -
Notes" was modified during this sprint but the draft doesn't mention it. Was this
a meaningful update or just a drive-by edit?

**Gap severity:** Low — but illustrative of the problem. The skill needs a way to
distinguish "I edited this doc substantively" from "I fixed a typo."

## Ideas for filling the gaps

### Email (Gmail) — available via MCP

**Current state:** The gdocs MCP server now has Gmail tools (`search_emails`,
`read_email`). These can be used during enrichment.

**How to use:**

- **Search sent mail by date range** to find outgoing communications. Sent mail is
  higher signal than inbox — it shows what *you* communicated, not what was sent to
  you. Use `mcp__gdocs__search_emails` with query `from:me after:YYYY/MM/DD before:YYYY/MM/DD`.
- **Search for threads with key stakeholders** during the sprint period. If Jira
  issues reference people (reporter, commenters), search for email threads with
  those people.
- **Search by subject keywords** matching Jira issue summaries or project names.
  Example: search for "Gift Aid" or "Confluence" in the sprint date range.
- **Read full email content** with `mcp__gdocs__read_email` for threads that
  contain decisions, requests, or impact evidence.
- **Extract action items and decisions** from email bodies — look for phrases like
  "let's go with," "approved," "please proceed," "next steps."

**What to collect:** A summary file (`email/highlights.md`) with:
- Thread subject, date, participants
- Key decisions or requests
- Gmail message IDs for reference

### Calendar — available via MCP

**Current state:** The gdocs MCP server now has Google Calendar tools
(`list_events`, `search_events`, `get_event`). These can be used during enrichment.

**How to use:**

- **List events in the sprint date range** using `mcp__gdocs__list_events` with
  `timeMin` and `timeMax` set to sprint start/end dates in RFC3339 format.
- **Identify recurring vs. one-off meetings** — recurring events have recurrence
  data; one-off meetings often signal something noteworthy happened.
- **Extract attendees** to understand collaboration patterns — who did you meet
  with most this sprint?
- **Search for project-specific meetings** using `mcp__gdocs__search_events` with
  project names or Jira keys as queries — a meeting titled "GGDisburse UAT Review"
  directly connects to the UAT work.
- **Get event details** with `mcp__gdocs__get_event` for events that appear
  relevant — check for attached docs, conference links, and full attendee lists.

**What to collect:** A summary file (`calendar/events.md`) with:
- Event title, date, attendees
- Flagging of non-recurring events as potentially noteworthy

### Jira comments — available now, underutilized

The current skill fetches issue details but doesn't systematically read comments.
Comments often contain:

- Stakeholder requests and context
- Post-deployment verification ("confirmed this is working")
- Decision rationale ("going with approach B because...")
- Links to Slack threads or documents

**Improvement:** For any non-recurring issue, fetch comments via
`mcp__jira__get_comments` and scan for impact language, stakeholder names, and
links. This is the highest-ROI improvement available today.

### Slack — no API, but better manual capture

Slack remains manual, but the `manual-notes.md` template could be more structured
to prompt for the specific types of context that are missing:

- Results shared (with links)
- Requests received (who asked for what)
- Decisions made in threads
- Shout-outs or recognition received

### Google Docs — better filtering

The current search returns docs modified during the sprint, but doesn't
distinguish between substantial edits and minor touch-ups. Ideas:

- Compare doc `size` from search results against a threshold — very small docs
  or very small size changes are likely minor edits.
- Read the doc and check if content references the sprint's date range or Jira
  issues to establish relevance.
- Search for docs created (not just modified) in the date range — new docs are
  higher signal.

### Google Sheets — available now via MCP

The dry run showed that spreadsheets (Jira Savings analysis) contain important
quantitative data. The current pipeline found the spreadsheet via search but
couldn't read it until the Sheets API was enabled.

**Improvement:** The skill should attempt to read any spreadsheets found during
the Google Docs/Drive search phase, since spreadsheets often contain the
quantitative evidence that makes sprint notes compelling.

## Priority ranking

| Gap | Available now? | Impact | Effort |
|---|---|---|---|
| Jira comments for key issues | Yes | High | Low |
| Google Sheets reading | Yes | Medium | Low |
| Better manual-notes.md prompts | Yes | Medium | Low |
| Google Docs relevance filtering | Yes | Medium | Medium |
| Prior sprint continuity check | Yes | Medium | Low |
| Gmail integration | Yes | High | Medium |
| Calendar integration | Yes | Medium | Medium |
| Slack integration | Blocked (no API) | High | High |
