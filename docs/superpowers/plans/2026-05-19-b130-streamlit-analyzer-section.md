# B-130.3 Streamlit Analyzer Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Streamlit section where users can analyze one ticker or upload a CSV/XLS/XLSX portfolio against the existing methodology snapshot.

**Architecture:** Keep Streamlit as an input/render layer only. Add small, tested formatting helpers in `src/portfolio.py` that turn `PortfolioAnalysis` into tables for display, then call the existing parser and analyzer helpers from `app.py`. The UI must not save uploads, mutate the scored DataFrame, fetch new data, or recompute scoring.

**Tech Stack:** Python 3, Streamlit, pandas, pytest, existing B-130 parser/analyzer helpers.

---

## Files

- Modify: `src/portfolio.py`
- Modify: `tests/test_portfolio.py`
- Modify: `app.py`
- Modify: `static/style.css`
- Modify: `requirements.txt`

---

### Task 1: UI Formatting Helpers

**Files:**
- Modify: `src/portfolio.py`
- Modify: `tests/test_portfolio.py`

- [x] **Step 1: Write failing table-helper tests**

Append tests asserting that `analysis_rows_frame()` returns display-ready rows with percent weights, state/class/score columns, and missing rows, and that `exposure_frame()` sorts exposure descending.

- [x] **Step 2: Run helper tests and verify they fail**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: fail because the helper functions do not exist.

- [x] **Step 3: Implement helper functions**

Add `analysis_rows_frame(analysis)` and `exposure_frame(exposures, label)` to `src/portfolio.py`. They should return pandas DataFrames and avoid Streamlit imports.

- [x] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_portfolio.py -q
```

Expected: all portfolio tests pass.

---

### Task 2: Streamlit Section

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`

- [x] **Step 1: Import portfolio helpers**

Add parser/analyzer/format helper imports from `src.portfolio`.

- [x] **Step 2: Add `render_portfolio_analyzer()`**

Add a section after `render_drill()` and before `render_full_table()`. It should use a horizontal mode selector for "Ticker" vs "Portfolio", `st.text_input()` for a single ticker, and `st.file_uploader()` for `.csv`, `.xlsx`, `.xls`.

- [x] **Step 3: Render validation and analysis output**

Use `parse_single_ticker()`, `parse_holdings_csv()`, `parse_holdings_excel()`, and `analyze_holdings()`. Display validation errors, missing tickers, state/class exposure tables, action ticker lists, and per-holding methodology rows. Keep uploads in memory only.

- [x] **Step 4: Add minimal CSS**

Add layout CSS for portfolio summary/action rows using the existing color variables and table/card patterns.

---

### Task 3: QA Gate And Review

Run:

```bash
python -m pytest tests/test_portfolio.py tests/test_scoring.py -q
python -m pytest -q
python -m compileall app.py src
git diff --check
streamlit run app.py --server.headless true --server.port 8502
```

Expected: tests and compile pass; Streamlit starts without import/runtime errors. Browser verification should be attempted with the Browser plugin if the required Node REPL tool is available; if it is not available, record that limitation and use the local server smoke check as fallback.
