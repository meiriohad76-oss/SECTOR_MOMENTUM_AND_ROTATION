# B-153.5 Exported Debrief Reports Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task.

**Goal:** Add non-secret exports to the B-153 Debrief lab so saved run outcomes can be reviewed outside the dashboard.

**Architecture:** Keep export generation pure in `src/run_debrief.py`. The Streamlit section reuses the already-loaded journal and OHLCV debrief records, then exposes a flat CSV plus Markdown report with download buttons. No provider fetches, secrets, scoring changes, state-machine writes, or alert behavior changes are part of this slice.

**Tech Stack:** Python, pandas, Streamlit download buttons, pytest.

---

### Task 1: Pure Export Helpers

**Files:**
- Modify: `src/run_debrief.py`
- Test: `tests/test_run_debrief.py`

- [x] **Step 1: Write failing tests**

Add tests requiring `debrief_outcome_rows()` to flatten each decision/horizon into CSV-ready rows, and `build_debrief_markdown_report()` to render summary, macro, and threshold-review sections.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_run_debrief.py::test_debrief_outcome_rows_flatten_records_for_report_export tests/test_run_debrief.py::test_build_debrief_markdown_report_includes_summary_and_candidates -q
```

Expected: import failure because the export helpers do not exist.

- [x] **Step 3: Implement helpers**

Add pure helpers that format outcome rows and Markdown tables without importing Streamlit or reading secrets.

- [x] **Step 4: Verify GREEN**

Run the same focused tests and require both to pass.

### Task 2: Dashboard Download Buttons

**Files:**
- Modify: `app.py`
- Test: `tests/test_run_debrief_dashboard_static.py`

- [x] **Step 1: Write failing static test**

Require the Debrief lab to call `debrief_outcome_rows(records)`, `build_debrief_markdown_report(...)`, and `st.download_button(...)` without adding `fetch_ohlcv()` inside the section.

- [x] **Step 2: Wire dashboard exports**

Build raw summary rows before display formatting, create the CSV and Markdown payloads, and expose two download buttons inside the Debrief lab.

- [x] **Step 3: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_run_debrief.py::test_debrief_outcome_rows_flatten_records_for_report_export tests/test_run_debrief.py::test_build_debrief_markdown_report_includes_summary_and_candidates tests/test_run_debrief_dashboard_static.py::test_app_surfaces_run_debrief_without_fetching_data_inside_section -q
```

Expected: `3 passed`.

### Task 3: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/specs/2026-05-21-b153-run-journal-debrief-engine-design.md`

- [x] **Step 1: Record the completed slice**

Document B-153.5 as analysis-only export capability and remove the previous "future polish" note for richer exported reports.
