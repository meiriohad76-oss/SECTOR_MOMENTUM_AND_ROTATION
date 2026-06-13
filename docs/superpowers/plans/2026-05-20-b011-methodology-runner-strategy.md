# B-011 Methodology Runner Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the manual B-011 runner use methodology target weights as the strategy under test, instead of using the 60/40 benchmark as a placeholder strategy.

**Architecture:** Keep `scripts/run_backtest.py` as the only live-data entry point. Fetch the sector universe plus `SPY`, `BIL`, and `AGG`; build historical methodology targets from the preloaded OHLCV; run the strategy against those targets; compare it to 60/40 and equal-weight sectors; write the same report/equity/metadata artifact set.

**Tech Stack:** Python, pandas, pytest, existing `src.backtest` helpers.

---

## File Structure

- Modify `tests/test_run_backtest_script.py`: assert the runner fetches `BIL`, invokes `build_historical_methodology_targets()`, and writes `Methodology` in report/equity/metadata.
- Modify `scripts/run_backtest.py`: build methodology targets and use those results as `strategy_metrics`.
- Modify `README.md`: clarify that the manual strategy is now the methodology smoke path.
- Modify `docs/BACKLOG.md`: update the B-011 latest-slice status.

---

### Task 1: Runner Uses Methodology Targets

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`

- [ ] **Step 1: Write failing test**

Update the successful runner test to:

- include `BIL` in `expected_tickers`
- monkeypatch `backtest.build_historical_methodology_targets()`
- return target weights for `XLK`
- assert the builder was called
- assert the report and equity artifact contain `Methodology`
- assert metadata `equity_columns` contains `Methodology`

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q`

Expected: fails because the runner does not fetch `BIL`, does not call the methodology target builder, and does not include `Methodology` in artifacts.

- [ ] **Step 3: Implement methodology strategy**

In `scripts/run_backtest.py`:

- add `BIL` to `REQUIRED_TICKERS`
- call `backtest.build_historical_methodology_targets(ohlcv, rebalance_dates=rebalance_dates, phase="MID")`
- derive `strategy_prices = prices[strategy_targets.target_weights.columns]`
- run `backtest.run_weight_backtest(strategy_prices, strategy_targets.target_weights, transaction_cost_bps=5.0)`
- run cost scenarios on the methodology target weights
- use `"Methodology"` as the strategy name in report and equity artifacts
- keep `60/40 SPY/AGG` and `Equal-weight sectors` as benchmarks

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q`

Expected: focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts/run_backtest.py tests/test_run_backtest_script.py
git commit -m "feat: use methodology targets in backtest runner"
```

---

### Task 2: Docs And QA

**Files:**
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update docs**

Document that the manual report now treats the methodology target path as the strategy and compares it to 60/40 plus equal-weight sectors.

- [ ] **Step 2: Run verification**

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

- [ ] **Step 3: Request review**

Ask a reviewer to inspect strategy/benchmark separation, no-network tests, artifact metadata, and docs wording.

