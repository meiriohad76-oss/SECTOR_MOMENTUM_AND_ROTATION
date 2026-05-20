# B-011 Backtest Dashboard Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface B-011 manual backtest artifacts in the dashboard without running live backtests during Streamlit page load.

**Architecture:** Keep artifact creation in `scripts/run_backtest.py`, add a pure equity-frame helper in `src/backtest.py`, and add a read-only Streamlit section that displays `docs/backtest_report.md` plus an equity chart when `docs/backtest_equity.csv` exists. Missing artifacts render an operator-friendly command instead of failing.

**Tech Stack:** Python, pandas, Streamlit, pytest.

---

## File Structure

- Modify `src/backtest.py`: add `equity_frame()` to combine named `BacktestResult.equity` series.
- Modify `tests/test_backtest.py`: add an offline equity-frame test.
- Modify `scripts/run_backtest.py`: write `docs/backtest_equity.csv` next to the Markdown report.
- Modify `tests/test_run_backtest_script.py`: patch/report both artifact paths and assert CSV output on success.
- Create `tests/test_backtest_dashboard_static.py`: static checks for app artifact paths and chart rendering.
- Modify `app.py`: add a `render_backtest_lab()` section after portfolio analyzer and before the full table.
- Modify `README.md` and `docs/BACKLOG.md`: document report plus equity-chart artifact and remaining full historical work.

---

### Task 1: Equity Artifact Helper

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_backtest.py`:

```python
def test_equity_frame_combines_named_results_on_date_index():
    dates = pd.bdate_range("2024-01-01", periods=3)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])
    result = backtest.run_weight_backtest(prices, weights, initial_capital=100.0)

    frame = backtest.equity_frame({"Strategy": result})

    assert list(frame.columns) == ["Strategy"]
    assert frame.index.name == "date"
    assert frame.iloc[0, 0] == pytest.approx(100.0)
    assert frame.iloc[-1, 0] == pytest.approx(121.0)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_backtest.py::test_equity_frame_combines_named_results_on_date_index -q`

Expected: fails because `equity_frame()` does not exist.

- [ ] **Step 3: Implement helper**

Add `equity_frame(results: dict[str, BacktestResult]) -> pd.DataFrame` to `src/backtest.py`. It should concatenate named equity series, sort by date, set `index.name = "date"`, and reject an empty mapping.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_backtest.py::test_equity_frame_combines_named_results_on_date_index -q`

Expected: test passes.

---

### Task 2: Runner Equity CSV Artifact

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`

- [ ] **Step 1: Write failing runner assertions**

Patch `run_backtest.EQUITY_PATH` to `tmp_path / "backtest_equity.csv"` in every runner test. In the successful runner test, assert the CSV exists and contains `60/40 SPY/AGG` plus `Equal-weight sectors`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q`

Expected: fails because the runner has no `EQUITY_PATH` and writes no CSV.

- [ ] **Step 3: Implement CSV write**

Add `EQUITY_PATH = Path("docs/backtest_equity.csv")` to `scripts/run_backtest.py`. After report creation, write:

```python
equity = backtest.equity_frame(
    {
        "60/40 SPY/AGG": sixty_forty_result,
        "Equal-weight sectors": sector_result,
    }
)
equity.to_csv(EQUITY_PATH)
```

Only write after all validation succeeds.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q`

Expected: focused tests pass.

- [ ] **Step 5: Commit helper and runner artifact**

```powershell
git add src/backtest.py tests/test_backtest.py scripts/run_backtest.py tests/test_run_backtest_script.py
git commit -m "feat: write backtest equity artifact"
```

---

### Task 3: Dashboard Artifact Surface

**Files:**
- Create: `tests/test_backtest_dashboard_static.py`
- Modify: `app.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Write failing static tests**

Create `tests/test_backtest_dashboard_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_backtest_artifacts_without_running_backtest():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'BACKTEST_REPORT_PATH = Path("docs/backtest_report.md")' in app_source
    assert 'BACKTEST_EQUITY_PATH = Path("docs/backtest_equity.csv")' in app_source
    assert "def render_backtest_lab():" in app_source
    assert "python scripts/run_backtest.py" in app_source
    assert "pd.read_csv(BACKTEST_EQUITY_PATH" in app_source
    assert "st.line_chart(" in app_source
    assert "run_backtest.main(" not in app_source


def test_backtest_lab_renders_before_full_table():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "render_portfolio_analyzer()\nrender_backtest_lab()\nrender_full_table()" in app_source
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_backtest_dashboard_static.py -q`

Expected: fails because app has no backtest lab.

- [ ] **Step 3: Implement app section**

In `app.py`, define artifact path constants near static paths. Add `render_backtest_lab()`:

- render section head `Backtest lab`
- if report exists, render its Markdown text
- if report missing, render a small HTML panel with `python scripts/run_backtest.py`
- if equity CSV exists, read it with `pd.read_csv(..., index_col="date", parse_dates=True)` and display `st.line_chart()`
- if equity CSV missing, show a muted message
- never call the runner from app code

Call it after `render_portfolio_analyzer()` and before `render_full_table()`.

- [ ] **Step 4: Update docs**

README and backlog should say the dashboard now displays manual report/equity artifacts when present, while full historical methodology simulation remains follow-up.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py tests/test_backtest_dashboard_static.py -q
```

Expected: focused tests pass.

- [ ] **Step 6: Commit dashboard slice**

```powershell
git add app.py tests/test_backtest_dashboard_static.py README.md docs/BACKLOG.md
git commit -m "feat: surface backtest artifacts in dashboard"
```

---

### Task 4: QA And Review

**Files:**
- No planned edits.

- [ ] **Step 1: Run verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py tests/test_backtest_dashboard_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected:

- focused tests pass
- full suite passes
- compileall exits 0
- diff check exits 0, allowing only normal CRLF warnings

- [ ] **Step 2: Request review**

Ask a reviewer to inspect artifact generation, dashboard rendering behavior, and that the app does not run live backtests on load.
