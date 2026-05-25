# B-112 Drill Time-Range Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a custom chart range selector to the per-ticker drill-down.

**Architecture:** Keep data loading unchanged. Add a pure `src.visuals.filter_ohlcv_lookback()` helper that derives the selected visible window from an existing daily OHLCV frame by the latest available timestamp. Wire `app.py` to expose a Streamlit range selector and pass `visible_since` to the existing price, CMF, and OBV charts so rolling indicators keep full loaded-history warmup.

**Tech Stack:** pandas, Plotly, Streamlit, pytest pure helper and static app coverage.

---

### Task 1: Pure OHLCV Lookback Helper

**Files:**
- Modify: `src/visuals.py`
- Modify: `tests/test_visuals.py`

- [ ] **Step 1: Write failing tests**

Add tests for `filter_ohlcv_lookback()`:

```python
def test_filter_ohlcv_lookback_uses_latest_available_date():
    dates = pd.date_range("2025-01-01", "2025-08-01", freq="MS")
    frame = _ohlcv(range(len(dates)), dates)

    filtered = filter_ohlcv_lookback(frame, "3M")

    assert filtered.index.min() == pd.Timestamp("2025-05-01")
    assert filtered.index.max() == pd.Timestamp("2025-08-01")
```

```python
def test_filter_ohlcv_lookback_max_keeps_all_rows_sorted():
    dates = pd.to_datetime(["2025-03-01", "2025-01-01", "2025-02-01"])
    frame = _ohlcv([3, 1, 2], dates)

    filtered = filter_ohlcv_lookback(frame, "MAX")

    assert list(filtered.index) == sorted(dates)
```

```python
def test_filter_ohlcv_lookback_invalid_range_uses_one_year_default():
    dates = pd.date_range("2024-01-01", "2025-08-01", freq="MS")
    frame = _ohlcv(range(len(dates)), dates)

    filtered = filter_ohlcv_lookback(frame, "BAD")

    assert filtered.index.min() == pd.Timestamp("2024-08-01")
```

Add a regression test for preserving 30-week SMA warmup on short visible ranges:

```python
def test_price_chart_with_30wma_visible_since_preserves_sma_warmup():
    dates = pd.bdate_range("2024-01-01", periods=420)
    frame = _ohlcv(list(range(100, 520)), dates)
    visible_since = dates[-63]

    fig = price_chart_with_30wma(frame, "XLK", visible_since=visible_since)

    close_trace, sma_trace = fig.data
    assert min(close_trace.x) >= visible_since
    assert min(sma_trace.x) >= visible_since
    assert any(pd.notna(value) for value in sma_trace.y)
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_visuals.py::test_filter_ohlcv_lookback_uses_latest_available_date tests/test_visuals.py::test_filter_ohlcv_lookback_max_keeps_all_rows_sorted tests/test_visuals.py::test_filter_ohlcv_lookback_invalid_range_uses_one_year_default -q`

Expected: FAIL because `filter_ohlcv_lookback` is not implemented or imported yet.

- [ ] **Step 3: Implement helper**

Add `filter_ohlcv_lookback(df_daily, range_key)` in `src/visuals.py`. Use calendar offsets from the latest available index date, support `3M`, `6M`, `1Y`, `3Y`, and `MAX`, sort the returned frame by index, return a copy, and fall back to `1Y` for unknown keys.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: PASS.

### Task 2: Drill-Down UI Wiring

**Files:**
- Modify: `app.py`
- Create: `tests/test_drill_range_app_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to define `DRILL_RANGE_OPTIONS = ("3M", "6M", "1Y", "3Y", "MAX")`, initialize `st.session_state.drill_range` to `1Y`, import `filter_ohlcv_lookback`, render `st.radio("CHART RANGE", ...)` without a duplicate widget `index`, compute `drill_ohlcv = filter_ohlcv_lookback(ohlcv[sel], selected_range)`, derive `visible_since = drill_ohlcv.index.min()`, and pass full `ohlcv[sel]` plus `visible_since` to price, CMF, and OBV charts.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_drill_range_app_static.py -q`

Expected: FAIL because the selector is not wired yet.

- [ ] **Step 3: Implement UI**

Add `DRILL_RANGE_OPTIONS` near app constants, initialize/reset the session key, place the selector directly under the ticker selectbox, and use the filtered frame for all drill charts.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_visuals.py tests/test_drill_range_app_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b112-drill-time-range-selector.md`

- [ ] **Step 1: Update docs and backlog**

Move B-112 from Ideas into implemented status. Document that `MAX` means all currently loaded OHLCV, not an expanded provider fetch.

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

Commit as `feat: add drill time-range selector`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
