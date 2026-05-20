# B-011 OOS Metrics Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic in-sample/out-of-sample metric reporting to the B-011 backtest harness and use OOS metrics for acceptance gates.

**Architecture:** Keep the split logic in pure `src/backtest.py`. A new helper computes full-period, in-sample, and out-of-sample metrics from an existing `BacktestResult` using a default `2015-01-01` OOS boundary. The manual runner uses those split metrics for reporting and acceptance gates while preserving the existing report/equity artifact flow.

**Tech Stack:** Python, pandas, pytest, existing pandas/numpy backtest core.

---

## File Structure

- Modify `tests/test_backtest.py`: tests for OOS metric split and report table rendering.
- Modify `src/backtest.py`: add `split_backtest_metrics()` and an optional report table section.
- Modify `tests/test_run_backtest_script.py`: assert the manual runner report includes the OOS section.
- Modify `scripts/run_backtest.py`: compute split metrics for strategy and benchmarks, use OOS strategy/equal-weight metrics for gates, and pass window metrics into the report.
- Modify `README.md` and `docs/BACKLOG.md`: document that acceptance gates now use OOS metrics.

---

### Task 1: Pure OOS Metric Split

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing test**

Add `test_split_backtest_metrics_uses_2015_boundary_for_oos()` with a synthetic one-asset backtest whose returns cross `2015-01-01`.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_split_backtest_metrics_uses_2015_boundary_for_oos -q
```

Expected: fails because `split_backtest_metrics()` does not exist.

- [ ] **Step 3: Implement helper**

Add `split_backtest_metrics(result, oos_start="2015-01-01", periods_per_year=TRADING_DAYS_PER_YEAR)` to return:

- `"Full period"`
- `"In-sample"`
- `"Out-of-sample"`

Each value is a normal metrics dictionary from `performance_metrics()` over the relevant return/turnover slice.

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_split_backtest_metrics_uses_2015_boundary_for_oos -q
```

Expected: pass.

---

### Task 2: Report And Runner Wiring

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `tests/test_run_backtest_script.py`
- Modify: `src/backtest.py`
- Modify: `scripts/run_backtest.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Write failing report tests**

Add assertions that `format_backtest_report()` can render an `## In-Sample / Out-of-Sample` table and the manual runner report includes that heading.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_format_backtest_report_includes_benchmarks_costs_and_gates tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q
```

Expected: fails because `format_backtest_report()` has no `window_metrics` argument and the runner does not pass split metrics.

- [ ] **Step 3: Implement report/runner changes**

In `src/backtest.py`, add an optional `window_metrics` argument to `format_backtest_report()` and render the table before acceptance gates.

In `scripts/run_backtest.py`, compute split metrics for the methodology, 60/40, and sector benchmark results. Use `"Out-of-sample"` strategy metrics plus `"Out-of-sample"` equal-weight metrics for `evaluate_acceptance_gates()`, while still showing full-period strategy metrics in the top table.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
python -m compileall app.py src scripts
git diff --check
```

Expected: pass, allowing normal CRLF warnings from Git on Windows.

- [ ] **Step 5: Commit**

```powershell
git add src/backtest.py tests/test_backtest.py scripts/run_backtest.py tests/test_run_backtest_script.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-20-b011-oos-metrics-report.md
git commit -m "feat: add oos backtest metrics"
```

---

### Task 3: Full QA And Review

**Files:** no planned edits unless review finds issues.

- [ ] **Step 1: Run full verification**

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 2: Request review**

Ask a reviewer to inspect OOS boundary handling, report wording, acceptance-gate wiring, and deterministic tests.
