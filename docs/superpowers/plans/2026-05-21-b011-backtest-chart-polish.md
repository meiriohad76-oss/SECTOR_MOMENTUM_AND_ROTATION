# B-011 Backtest Chart Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the dashboard Backtest Lab from a single raw equity chart into explicit normalized equity and drawdown views backed by pure, tested chart-frame helpers.

**Architecture:** Keep all financial transformations in `src/backtest.py`, where tests can verify them without Streamlit. `app.py` remains a read-only artifact viewer: it loads `docs/backtest_equity.csv` only when metadata hashes match, transforms the frame with pure helpers, and renders two charts without running `scripts/run_backtest.py` on page load.

**Tech Stack:** Python, pandas, Streamlit, pytest.

---

## File Structure

- Modify `tests/test_backtest.py`: add chart-frame tests for normalized equity and drawdown.
- Modify `src/backtest.py`: add `normalized_equity_frame()` and `drawdown_frame()` helpers.
- Modify `tests/test_backtest_dashboard_static.py`: assert the dashboard imports/uses the new helpers and renders labeled normalized equity and drawdown charts.
- Modify `app.py`: import the helpers and render two Backtest Lab charts from the verified equity artifact.
- Modify `README.md` and `docs/BACKLOG.md`: document that the dashboard now shows normalized equity and drawdown artifact charts.

---

### Task 1: Pure Chart Frames

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests**

Append tests that call `backtest.normalized_equity_frame()` and `backtest.drawdown_frame()` on a tiny equity frame:

```python
def test_normalized_equity_frame_rebases_each_series_to_one():
    dates = pd.bdate_range("2024-01-01", periods=3)
    equity = pd.DataFrame(
        {
            "Methodology": [100.0, 110.0, 121.0],
            "Benchmark": [50.0, 45.0, 60.0],
        },
        index=dates,
    )

    normalized = backtest.normalized_equity_frame(equity)

    assert normalized.index.name == "date"
    assert normalized.loc[dates[0]].to_dict() == pytest.approx(
        {"Methodology": 1.0, "Benchmark": 1.0}
    )
    assert normalized.loc[dates[-1]].to_dict() == pytest.approx(
        {"Methodology": 1.21, "Benchmark": 1.20}
    )


def test_drawdown_frame_reports_percent_below_running_high():
    dates = pd.bdate_range("2024-01-01", periods=4)
    equity = pd.DataFrame(
        {
            "Methodology": [100.0, 120.0, 90.0, 126.0],
            "Benchmark": [50.0, 40.0, 60.0, 54.0],
        },
        index=dates,
    )

    drawdown = backtest.drawdown_frame(equity)

    assert drawdown.index.name == "date"
    assert drawdown["Methodology"].tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])
    assert drawdown["Benchmark"].tolist() == pytest.approx([0.0, -0.20, 0.0, -0.10])
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_normalized_equity_frame_rebases_each_series_to_one tests/test_backtest.py::test_drawdown_frame_reports_percent_below_running_high -q
```

Expected: fails because the helpers do not exist.

- [ ] **Step 3: Implement minimal helpers**

Add helpers in `src/backtest.py` after `equity_frame()`:

```python
def _clean_equity_artifact(equity: pd.DataFrame) -> pd.DataFrame:
    frame = equity.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index().apply(pd.to_numeric, errors="coerce").dropna(how="all").ffill()
    if frame.empty:
        return frame
    if not np.isfinite(frame.to_numpy(dtype=float)).all() or (frame <= 0).any().any():
        raise ValueError("equity values must be finite and strictly positive")
    frame.index.name = "date"
    return frame


def normalized_equity_frame(equity: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_equity_artifact(equity)
    if frame.empty:
        return frame
    normalized = frame.div(frame.iloc[0])
    normalized.index.name = "date"
    return normalized


def drawdown_frame(equity: pd.DataFrame) -> pd.DataFrame:
    frame = _clean_equity_artifact(equity)
    if frame.empty:
        return frame
    drawdown = frame.div(frame.cummax()).sub(1.0)
    drawdown.index.name = "date"
    return drawdown
```

- [ ] **Step 4: Run GREEN**

Run the same focused command. Expected: both tests pass.

---

### Task 2: Dashboard Wiring

**Files:**
- Modify: `tests/test_backtest_dashboard_static.py`
- Modify: `app.py`

- [ ] **Step 1: Write failing static tests**

Extend `tests/test_backtest_dashboard_static.py` to assert:

```python
assert "from src.backtest import drawdown_frame, normalized_equity_frame" in app_source
assert "normalized_equity_frame(equity)" in app_source
assert "drawdown_frame(equity)" in app_source
assert "Normalized equity" in app_source
assert "Drawdown" in app_source
```

Keep the existing assertion that `run_backtest.main(` is absent.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest_dashboard_static.py -q
```

Expected: fails because `app.py` still renders only `st.line_chart(equity)`.

- [ ] **Step 3: Implement dashboard rendering**

In `app.py`, import:

```python
from src.backtest import drawdown_frame, normalized_equity_frame
```

Replace the single Backtest Lab chart with two labeled chart blocks:

```python
_md('<div class="chart-help"><b>Normalized equity.</b> Each series starts at 1.0 so the methodology and benchmarks can be compared on the same base.</div>')
st.line_chart(normalized_equity_frame(equity), use_container_width=True)
_md('<div class="chart-help"><b>Drawdown.</b> Percent below each series running high; lower readings show the depth of the underwater period.</div>')
st.line_chart(drawdown_frame(equity), use_container_width=True)
```

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_backtest_dashboard_static.py -q
```

Expected: focused tests pass.

---

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update docs**

Update README and B-011 backlog wording to say the dashboard Backtest Lab renders normalized equity and drawdown charts from the verified equity artifact.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_backtest_dashboard_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Request review**

Review scope: chart helper validation, chart interpretation, dashboard still avoids running the backtest on page load, and docs/backlog wording.

- [ ] **Step 4: Commit, push, deploy**

Commit:

```powershell
git add src/backtest.py tests/test_backtest.py app.py tests/test_backtest_dashboard_static.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-21-b011-backtest-chart-polish.md
git commit -m "feat: polish backtest dashboard charts"
git push
```

Deploy to Pi with the established SSH command and non-sudo service restart pattern. Run Pi focused tests and HTTP smoke before moving to the next backlog slice.
