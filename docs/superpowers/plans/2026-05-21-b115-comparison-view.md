# B-115 Comparison View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only comparison view for 2-4 tickers.

**Architecture:** Keep data loading and scoring unchanged. Add a pure `src.comparison_view` helper that chooses sensible default tickers and converts selected scored rows into display-ready card rows. Wire `app.py` to expose a capped Streamlit multiselect and render side-by-side metric cards from the existing `scored` snapshot.

**Tech Stack:** pandas, Streamlit, HTML/CSS, pytest pure helper and static app/CSS coverage.

---

### Task 1: Pure Comparison Helper

**Files:**
- Create: `src/comparison_view.py`
- Create: `tests/test_comparison_view.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring:

```python
def test_comparison_default_tickers_starts_with_current_then_active_picks():
    scored = pd.DataFrame(
        {
            "selected": [True, True, False, True],
            "S_score": [0.2, 1.4, 2.0, 0.5],
            "rank_in_class": [2, 1, 1, 3],
        },
        index=["XLK", "XLF", "NVDA", "XLI"],
    )

    assert comparison_default_tickers(scored, current_ticker="NVDA") == ["NVDA", "XLF", "XLK", "XLI"]
```

```python
def test_comparison_rows_limit_dedup_and_format_metrics():
    scored = pd.DataFrame(
        {
            "state": ["STAGE_2_BULLISH", "WARNING"],
            "class": ["US Sectors", "US Sectors"],
            "S_score": [1.234, -0.456],
            "F_score": [0.25, -0.5],
            "mom_12_1": [0.123, -0.045],
            "stage": [2, 4],
            "rrg_quadrant": ["Leading", "Lagging"],
            "rank_in_class": [1, 9],
            "selected": [True, False],
            "veto": [False, True],
        },
        index=["XLK", "XLF"],
    )

    rows = comparison_card_rows(scored, ["XLK", "XLK", "BAD", "XLF"])

    assert [row["ticker"] for row in rows] == ["XLK", "XLF"]
    assert rows[0]["s_score"] == "+1.23"
    assert rows[0]["momentum"] == "+12.3%"
    assert rows[1]["veto"] == "VETO"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_comparison_view.py -q`

Expected: FAIL because `src.comparison_view` does not exist.

- [ ] **Step 3: Implement helper**

Implement `comparison_default_tickers()` and `comparison_card_rows()`. Deduplicate inputs, cap at four tickers, ignore unknown tickers, and format numeric metrics defensively.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_comparison_view.py -q`

Expected: PASS.

### Task 2: Dashboard Comparison Section

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Create: `tests/test_comparison_view_app_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to import comparison helpers, initialize `st.session_state.comparison_tickers`, define `render_comparison_view()`, render `st.multiselect("COMPARE TICKERS", ...)`, cap selections to four tickers, call `comparison_card_rows(scored, selected_compare)`, and compose the page as `render_drill()` then `render_comparison_view()` then `render_portfolio_analyzer()`.

Require `static/style.css` to define `.comparison-grid`, `.comparison-card`, `.comparison-metrics`, and responsive mobile stacking.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_comparison_view_app_static.py -q`

Expected: FAIL because the section is not wired yet.

- [ ] **Step 3: Implement UI**

Add the comparison section after the drill-down. Use a max-four warning if the user selects more than four, render an info message until at least two valid tickers are selected, and render cards with state, class, S/F, momentum, stage, RRG, rank, selection, and veto.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_comparison_view.py tests/test_comparison_view_app_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b115-comparison-view.md`

- [ ] **Step 1: Update docs and backlog**

Move B-115 from Ideas into implemented status. Document that the comparison view is read-only and uses the current scored snapshot.

- [ ] **Step 2: Full local QA**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Local HTTP smoke**

Run Streamlit temporarily and verify HTTP `200` on `/?ticker=XLK`.

- [ ] **Step 4: Review**

Request focused review. Fix Critical/Important feedback and rerun QA.

- [ ] **Step 5: Commit, push, and deploy**

Commit as `feat: add ticker comparison view`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
