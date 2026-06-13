# B-011 Backtest Report Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the B-011 manual backtest report from a gate-only smoke artifact into a concise benchmark, cost-sensitivity, and acceptance-gate summary.

**Architecture:** Keep all report formatting in pure `src/backtest.py`, then have `scripts/run_backtest.py` assemble deterministic benchmark/cost outputs from already-fetched prices. The Streamlit app remains unchanged in this slice; dashboard chart surfacing follows after the report artifact is useful.

**Tech Stack:** Python, pandas, pytest, existing yfinance data loader.

---

## File Structure

- Modify `src/backtest.py`: add report-summary helpers that format metrics, benchmark tables, cost scenarios, and gates.
- Modify `tests/test_backtest.py`: add offline tests for the richer report text.
- Modify `scripts/run_backtest.py`: compare SPY/AGG 60/40 against equal-weight sector benchmark and write the richer report.
- Modify `tests/test_run_backtest_script.py`: assert the manual runner fetches the required benchmark and sector tickers and writes the richer sections.
- Modify `README.md`: document the richer manual report output.
- Modify `docs/BACKLOG.md`: update the B-011 latest-slice status.

---

### Task 1: Pure Report Formatter

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing report test**

Append to `tests/test_backtest.py`:

```python
def test_format_backtest_report_includes_benchmarks_costs_and_gates():
    strategy_metrics = {
        "total_return": 0.24,
        "cagr": 0.12,
        "sharpe": 0.91,
        "sortino": 1.30,
        "max_drawdown": -0.18,
        "calmar": 0.67,
        "annualized_turnover": 1.20,
    }
    benchmark_metrics = {
        "60/40 SPY/AGG": {"cagr": 0.08, "sharpe": 0.70, "max_drawdown": -0.22},
        "Equal-weight sectors": {"cagr": 0.10, "sharpe": 0.74, "max_drawdown": -0.25},
    }
    cost_scenarios = pd.DataFrame(
        {
            "cagr": [0.121, 0.118],
            "sharpe": [0.91, 0.89],
            "max_drawdown": [-0.18, -0.181],
        },
        index=pd.Index([3.0, 10.0], name="cost_bps"),
    )
    gates = backtest.evaluate_acceptance_gates(
        strategy_metrics={**strategy_metrics, "state_transitions_per_ticker_year": 2.0},
        equal_weight_metrics=benchmark_metrics["Equal-weight sectors"],
    )

    text = backtest.format_backtest_report(
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        cost_scenarios=cost_scenarios,
        gates=gates,
        title="Manual Backtest Smoke Report",
    )

    assert "# Manual Backtest Smoke Report" in text
    assert "## Strategy Metrics" in text
    assert "| CAGR | 12.00% |" in text
    assert "## Benchmark Comparison" in text
    assert "| 60/40 SPY/AGG |" in text
    assert "## Cost Sensitivity" in text
    assert "| 10 bps |" in text
    assert "## Acceptance Gates" in text
    assert "Out-of-sample Sharpe: PASS" in text
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_backtest.py::test_format_backtest_report_includes_benchmarks_costs_and_gates -q`

Expected: fails because `format_backtest_report()` does not exist.

- [ ] **Step 3: Implement report formatter**

Add small formatting helpers and `format_backtest_report()` to `src/backtest.py`. It must render:

- title
- strategy metrics table
- benchmark comparison table
- cost sensitivity table
- acceptance gates

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_backtest.py::test_format_backtest_report_includes_benchmarks_costs_and_gates -q`

Expected: test passes.

- [ ] **Step 5: Run focused B-011 tests**

Run: `python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q`

Expected: focused tests pass.

- [ ] **Step 6: Commit pure formatter**

```powershell
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: add backtest summary report formatter"
```

---

### Task 2: Manual Runner Report Assembly

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Write failing runner test**

Update `test_run_backtest_fetches_required_smoke_tickers_only()` to expect the runner fetches `AGG`, `SPY`, and the 11 SPDR sector ETFs. After `main()` returns 0, read the report and assert it contains:

```python
assert "## Benchmark Comparison" in report
assert "60/40 SPY/AGG" in report
assert "Equal-weight sectors" in report
assert "## Cost Sensitivity" in report
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_run_backtest_script.py::test_run_backtest_fetches_required_smoke_tickers_only -q`

Expected: fails because the runner only fetches `AGG` and `SPY` and writes gate-only text.

- [ ] **Step 3: Implement runner assembly**

In `scripts/run_backtest.py`:

- define the 11 SPDR sector tickers
- fetch `AGG`, `SPY`, and sectors
- build weekly rebalance dates from aligned prices
- run 60/40 benchmark
- run equal-weight sector benchmark
- run cost scenarios for the 60/40 target with `[3, 5, 10]`
- call `format_backtest_report()`

- [ ] **Step 4: Update docs**

In `README.md`, say the manual report includes strategy metrics, benchmark comparison, cost sensitivity, and gates.

In `docs/BACKLOG.md`, update the B-011 latest-slice status to mention richer manual report output; leave dashboard `/backtest` charts as remaining follow-up.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q`

Expected: focused tests pass.

- [ ] **Step 6: Commit runner/docs slice**

```powershell
git add scripts/run_backtest.py tests/test_run_backtest_script.py README.md docs/BACKLOG.md
git commit -m "feat: enrich manual backtest report"
```

---

### Task 3: QA And Review

**Files:**
- No new planned files.

- [ ] **Step 1: Run verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
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

Ask a reviewer to inspect:

- report formatting accuracy
- benchmark and cost-scenario assembly
- no network in tests
- no dashboard/state-machine side effects
- docs wording does not claim live edge

- [ ] **Step 3: Manual runner optional evidence**

Run `python scripts/run_backtest.py` only after deterministic gates pass. If yfinance/network fails, record it as a manual evidence gap. If it succeeds, inspect `docs/backtest_report.md`, decide whether to commit it as a generated evidence artifact or leave it untracked.

