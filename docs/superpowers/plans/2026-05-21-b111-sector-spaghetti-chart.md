# B-111 Sector Spaghetti Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 12-month overlaid relative-strength line chart for all US sector ETFs.

**Architecture:** Keep data fetching unchanged. Add pure chart helpers in `src/visuals.py` that consume the existing `ohlcv` dictionary, compute each sector's adjusted-close ratio versus SPY, normalize every line to 100 at the start of the lookback, and render one Plotly trace per available sector. Wire `app.py` to show the chart after the RRG section using already-loaded `ohlcv`.

**Tech Stack:** pandas, Plotly, Streamlit, pytest static and pure helper coverage.

---

### Task 1: Pure Relative-Strength Frame And Chart

**Files:**
- Modify: `src/visuals.py`
- Modify: `tests/test_visuals.py`

- [ ] **Step 1: Write failing tests**

Add tests requiring:

```python
def test_relative_strength_lines_frame_normalizes_each_sector_to_100():
    dates = pd.date_range("2025-01-01", periods=4, freq="D")
    ohlcv = {
        "SPY": _ohlcv([100, 100, 100, 100], dates),
        "XLK": _ohlcv([50, 55, 60, 65], dates),
        "XLF": _ohlcv([20, 18, 22, 24], dates),
    }

    frame = relative_strength_lines_frame(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert list(frame.columns) == ["XLK", "XLF"]
    assert frame.iloc[0].to_dict() == {"XLK": 100.0, "XLF": 100.0}
    assert frame.iloc[-1]["XLK"] == pytest.approx(130.0)
    assert frame.iloc[-1]["XLF"] == pytest.approx(120.0)
```

```python
def test_sector_spaghetti_chart_adds_one_trace_per_available_sector():
    fig = sector_spaghetti_chart(ohlcv, ["XLK", "XLF"], bench_ticker="SPY", lookback_days=4)

    assert [trace.name for trace in fig.data] == ["XLK", "XLF"]
    assert fig.layout.yaxis.title.text == "Relative strength vs SPY, start = 100"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: FAIL because helpers do not exist yet.

- [ ] **Step 3: Implement helpers**

Implement `relative_strength_lines_frame()` and `sector_spaghetti_chart()` in `src/visuals.py`. Use `src.data.close_price()`, skip missing/invalid tickers, sort columns by ending value descending, and keep empty input as an empty chart.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: PASS.

### Task 2: Dashboard Section

**Files:**
- Modify: `app.py`
- Create: `tests/test_sector_spaghetti_app_static.py`

- [ ] **Step 1: Write failing static tests**

Require `app.py` to import `sector_spaghetti_chart`, import `US_SECTORS`, define `render_sector_spaghetti()`, call `sector_spaghetti_chart(ohlcv, US_SECTORS, BENCH["US"])`, and render it between `render_rrg()` and `render_drill()`.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_sector_spaghetti_app_static.py -q`

Expected: FAIL because the section is not wired yet.

- [ ] **Step 3: Implement UI section**

Add a compact section headed `Sector spaghetti chart` with right label `12M RELATIVE STRENGTH VS SPY`, render `st.plotly_chart(..., use_container_width=True)`, and show an info message if no traces are available.

- [ ] **Step 4: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_visuals.py tests/test_sector_spaghetti_app_static.py -q
```

Expected: PASS.

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/PRODUCT_DESIGN.md`
- Modify: `docs/superpowers/plans/2026-05-21-b111-sector-spaghetti-chart.md`

- [ ] **Step 1: Update docs and backlog**

Move B-111 from Ideas into completed status with files, behavior, safety, evidence, and screenshot/browser QA residual risk.

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

Commit as `feat: add sector spaghetti chart`, push to GitHub, verify remote SHA, deploy to Pi, run focused tests, full Pi pytest, and dashboard HTTP smoke.
