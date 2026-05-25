# B-153.4 Debrief Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the run-journal debrief engine in the Streamlit dashboard without adding network calls or blocking page load.

**Architecture:** Keep forward-outcome calculations in `src/run_debrief.py`. `app.py` will add a small Debrief lab section after the Backtest lab, using the already-loaded `ohlcv` dictionary and the local `DEFAULT_JOURNAL_PATH`. It will show summary rows and threshold-review candidates when mature outcomes exist, otherwise a clear empty state.

**Tech Stack:** Streamlit, pandas, existing `src.run_debrief` helpers, pytest static checks.

---

### Task 1: Static Dashboard Wiring

**Files:**
- Create: `tests/test_run_debrief_dashboard_static.py`
- Modify: `app.py`
- Modify: `docs/BACKLOG.md`

- [x] **Step 1: Write failing static tests**

Assert that `app.py` imports `debrief_journal`, `summarize_debriefs`, and `threshold_review_candidates`; defines `render_debrief_lab()`; calls it between `render_backtest_lab()` and `render_full_table()`; uses `DEFAULT_JOURNAL_PATH`; and does not call `fetch_ohlcv()` inside the debrief lab.

- [x] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_run_debrief_dashboard_static.py -q
```

Observed: failure because `render_debrief_lab()` and the compose call were not present.

- [x] **Step 3: Implement dashboard surface**

Add `render_debrief_lab()` near `render_backtest_lab()`.

Behavior:
- Render section heading `Debrief lab`.
- Call `debrief_journal(DEFAULT_JOURNAL_PATH, ohlcv, limit=100)`.
- Build summary and threshold candidate frames from `summarize_debriefs()` and `threshold_review_candidates()`.
- If no rows are available, render a chart-help empty state explaining that forward windows need time to mature.
- Catch exceptions and render `st.warning()` so debrief issues do not block the dashboard.

- [x] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_run_debrief_dashboard_static.py -q
```

Observed: `2 passed`.

- [x] **Step 5: Run QA**

Run:

```powershell
python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:
- `python -m pytest tests/test_backtest_dashboard_static.py tests/test_run_debrief_dashboard_static.py -q` -> `4 passed`
- `python -m pytest tests/test_run_debrief.py tests/test_run_debrief_dashboard_static.py tests/test_run_journal.py -q` -> `17 passed`
- `python -m pytest -q` -> `175 passed`
- `python -m compileall app.py src scripts` -> exit 0
- `git diff --check` -> exit 0

- [x] **Step 6: Review and commit**

Request review, fix findings, then commit:

```powershell
git add app.py tests/test_run_debrief_dashboard_static.py docs/BACKLOG.md docs/superpowers/plans/2026-05-21-b153-debrief-dashboard.md
git commit -m "feat: surface run debrief dashboard"
```

Review found no issues. Residual risk: dashboard surfacing tests are static and do not exercise Streamlit runtime rendering for empty/corrupt/matured journal states.
