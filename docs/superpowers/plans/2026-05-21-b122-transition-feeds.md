# B-122 RSS And iCal Transition Feeds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate RSS and iCal feed artifacts from the persisted state-transition log.

**Architecture:** Add pure feed-formatting helpers in `src.transition_feeds` and a cron-friendly script that reads `state.json` through `recent_transitions()`, writes generated artifacts under `data/feeds/`, and prints the output paths. Generated feed files stay local and gitignored; no dashboard load writes feeds.

**Tech Stack:** Python stdlib XML escaping, `email.utils.format_datetime`, `pathlib`, existing state-machine transition log, pytest.

---

### Task 1: Pure RSS And iCal Formatters

**Files:**
- Create: `src/transition_feeds.py`
- Create: `tests/test_transition_feeds.py`

- [ ] **Step 1: Write failing formatter tests**

Add tests requiring `rss_feed_xml()` to escape ticker/state text and include `<rss version="2.0">`, and `ical_calendar()` to emit `VCALENDAR` / `VEVENT` entries with all-day transition dates.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_transition_feeds.py -q`

Expected: FAIL because `src.transition_feeds` does not exist.

- [ ] **Step 3: Implement pure helpers**

Create `TransitionFeedItem`, `feed_items_from_transitions()`, `rss_feed_xml()`, and `ical_calendar()`. Sort items newest first for RSS and chronological for iCal. Use stable event UIDs from ticker/date/from/to.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_transition_feeds.py -q`

Expected: PASS.

### Task 2: Export Script And Docs

**Files:**
- Create: `scripts/export_transition_feeds.py`
- Create: `tests/test_export_transition_feeds_script.py`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b122-transition-feeds.md`

- [ ] **Step 1: Write failing script test**

Add a test that monkeypatches `recent_transitions()`, calls `main(["--output-dir", tmp_path])`, and asserts `transitions.rss` and `transitions.ics` are written.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_export_transition_feeds_script.py -q`

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement script and docs**

Create `scripts/export_transition_feeds.py` with repo-root path bootstrap, default output `data/feeds`, and `--limit`. Document cron usage and mark `data/feeds/` ignored.

- [ ] **Step 4: Full QA, review, commit, push, deploy**

Run:

```powershell
python -m pytest tests/test_transition_feeds.py tests/test_export_transition_feeds_script.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Request focused review, fix Critical/Important feedback, commit as `feat: add transition rss and ical feeds`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, run the export script, and dashboard HTTP smoke.

Implementation evidence captured during development:

```powershell
python -m pytest tests/test_transition_feeds.py tests/test_export_transition_feeds_script.py -q
# 4 passed
python scripts/export_transition_feeds.py
# transition_feeds=written ... items=0
python -m pytest -q
# 272 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0, LF/CRLF warnings only
```

Review result: no Critical or Important issues. Residual polish noted for stricter iCal clients: line folding, corrupted-date hardening, and negative `--limit` validation.
