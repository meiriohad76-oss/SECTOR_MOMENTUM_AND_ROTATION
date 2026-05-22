# B-154 Expanded FRED Macro Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only expanded FRED macro context to the dashboard and persist the same macro snapshot into the B-153 run journal metadata.

**Architecture:** Keep FRED expansion display-only and out of scoring/veto logic. Add pure formatting helpers to `src/macro_tiles.py`, render those rows from the cached FRED payload in `app.py`, and pass a cleaned snapshot into `_record_dashboard_run()` metadata so debrief/backtest work can analyze macro conditions later.

**Tech Stack:** Python, pandas, Streamlit HTML rendering, SQLite run journal, pytest/static source tests.

---

## File Structure

- Modify `src/macro_tiles.py`: add FRED context groups, pure snapshot formatting, and tile-row helpers.
- Modify `tests/test_macro_tiles.py`: cover FRED tile formatting, missing data, and snapshot values.
- Modify `app.py`: render read-only FRED macro tiles and include `fred_macro_snapshot` in journal metadata.
- Modify `tests/test_macro_tiles_app_static.py`: ensure app renders FRED macro context without changing scoring inputs.
- Modify `tests/test_run_journal_app_static.py`: ensure app passes FRED macro snapshot to `_record_dashboard_run()`.
- Modify `docs/BACKLOG.md`, `README.md`, and `docs/FRED_DATA_OPPORTUNITIES.md`: document B-154 as read-only context plus journal metadata.

---

### Task 1: Pure FRED Context Rows

- [x] Write failing tests in `tests/test_macro_tiles.py` for `fred_macro_snapshot()` and `fred_macro_tile_groups()`.
- [x] Run `python -m pytest tests/test_macro_tiles.py -q` and confirm failures are missing imports/functions.
- [x] Implement pure helpers in `src/macro_tiles.py` using existing `pandas.Series` inputs and no network calls.
- [x] Re-run `python -m pytest tests/test_macro_tiles.py -q`.

### Task 2: Dashboard Rendering And Journal Metadata

- [x] Write static tests that `app.py` imports/renders FRED macro groups and passes `fred_macro_snapshot` into `_record_dashboard_run()`.
- [x] Run the focused static tests and confirm failures.
- [x] Update `app.py` to render grouped read-only FRED context when `_fred_data` exists, preserve proxy/data-pending behavior when it does not, and pass `fred_macro_snapshot` into B-153 metadata.
- [x] Re-run focused app/static tests.

### Task 3: Documentation, QA, And Deploy

- [x] Update docs to describe B-154 and emphasize no scoring changes.
- [ ] Run `python -m pytest -q`, `python -m compileall app.py src scripts`, and `git diff --check`.
- [ ] Commit, push to `origin/backlog-stepwise-qa`, pull on AHADPI5, run focused tests, full tests, FRED live fetch, service smoke, and record any handoff evidence.
