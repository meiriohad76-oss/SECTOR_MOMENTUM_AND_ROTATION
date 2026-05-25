# B-011 Historical Simulation Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual runner's placeholder historical state-transition evidence with a real transition-rate calculation from the simulated weekly methodology states.

**Architecture:** Keep state-transition accounting in pure `src/backtest.py`. The runner already builds historical methodology targets and state rows without writing `state.json`; this slice adds summary helpers, passes the computed transition rate into acceptance gates, and records the simulation summary in the report/metadata artifacts.

**Tech Stack:** Python, pandas, pytest.

---

## File Structure

- Modify `tests/test_backtest.py`: add pure tests for state-transition rate, historical simulation summary, and report rendering.
- Modify `src/backtest.py`: add `state_transition_rate()`, `historical_simulation_summary()`, and a report section for summary evidence.
- Modify `tests/test_run_backtest_script.py`: assert the runner passes real transition evidence into gates and writes it to report/metadata.
- Modify `scripts/run_backtest.py`: compute summary from `HistoricalSignalTargets`, pass the transition rate to `evaluate_acceptance_gates()`, and include summary in artifacts.
- Modify `README.md` and `docs/BACKLOG.md`: document that the historical simulation report includes rebalance/state-transition evidence.

---

### Task 1: Pure Historical State Evidence

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
def test_state_transition_rate_counts_changes_per_ticker_year():
    dates = pd.bdate_range("2024-01-01", periods=4)
    states = pd.DataFrame(
        {
            "AAA": ["HOLD", "HOLD", "WARNING", "WARNING"],
            "BBB": ["EXIT", "HOLD", "HOLD", "STAGE_2_BULLISH"],
        },
        index=dates,
    )

    rate = backtest.state_transition_rate(states, periods_per_year=4)

    assert rate == pytest.approx(2.0)


def test_historical_simulation_summary_reports_rebalance_state_and_selection_evidence():
    dates = pd.bdate_range("2024-01-01", periods=4)
    targets = backtest.HistoricalSignalTargets(
        target_weights=pd.DataFrame(
            {"AAA": [1.0, 0.5, 0.0, 0.0], "BBB": [0.0, 0.5, 1.0, 1.0]},
            index=dates,
        ),
        states=pd.DataFrame(
            {"AAA": ["HOLD", "HOLD", "WARNING", "WARNING"], "BBB": ["EXIT", "HOLD", "HOLD", "HOLD"]},
            index=dates,
        ),
        snapshots={},
    )

    summary = backtest.historical_simulation_summary(targets, periods_per_year=4)

    assert summary["rebalance_count"] == 4
    assert summary["state_ticker_count"] == 2
    assert summary["selected_ticker_count"] == 2
    assert summary["state_transition_count"] == 2
    assert summary["state_transitions_per_ticker_year"] == pytest.approx(4 / 3)
```

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_state_transition_rate_counts_changes_per_ticker_year tests/test_backtest.py::test_historical_simulation_summary_reports_rebalance_state_and_selection_evidence -q
```

Expected: fails because the helpers do not exist.

- [ ] **Step 3: Implement helpers**

Add pure helpers in `src/backtest.py`:

- `state_transition_rate(states, periods_per_year=52)` counts non-null consecutive state changes per ticker and annualizes by observed intervals per ticker.
- `historical_simulation_summary(targets, periods_per_year=52)` returns JSON-friendly counts, dates, and the computed transition rate.

- [ ] **Step 4: Run GREEN**

Run the same focused command. Expected: both tests pass.

---

### Task 2: Report And Runner Wiring

**Files:**
- Modify `tests/test_backtest.py`
- Modify `tests/test_run_backtest_script.py`
- Modify `src/backtest.py`
- Modify `scripts/run_backtest.py`

- [ ] **Step 1: Write failing tests**

Extend the existing report formatter test to pass a `simulation_summary` dict and assert `## Historical Methodology Simulation` plus `State transitions per ticker-year`.

Update the successful runner test so fake historical targets include changing states. Assert:

- `gate_calls[0]["strategy_metrics"]["state_transitions_per_ticker_year"] > 0`
- report contains `## Historical Methodology Simulation`
- metadata contains `simulation_summary` and the transition rate.

- [ ] **Step 2: Run RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_format_backtest_report_includes_benchmarks_costs_and_gates tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q
```

Expected: fails because report/runner do not yet accept simulation summary and runner passes `0.0`.

- [ ] **Step 3: Implement report/runner changes**

In `src/backtest.py`, add optional `simulation_summary` to `format_backtest_report()` and render a compact Markdown table before the in-sample/out-of-sample section.

In `scripts/run_backtest.py`:

- compute `simulation_summary = backtest.historical_simulation_summary(methodology_targets)`
- pass `simulation_summary["state_transitions_per_ticker_year"]` into acceptance-gate strategy metrics
- pass `simulation_summary` into `format_backtest_report()`
- write `simulation_summary` into `docs/backtest_metadata.json`

- [ ] **Step 4: Run GREEN**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
```

Expected: focused tests pass.

---

### Task 3: Docs, QA, Review, Deploy

**Files:**
- Modify `README.md`
- Modify `docs/BACKLOG.md`

- [ ] **Step 1: Update docs**

Document that the manual historical simulation report now includes rebalance count, state ticker count, selected ticker count, state transition count, and transitions per ticker-year.

- [ ] **Step 2: Run verification**

Run:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: all commands exit 0, allowing only normal CRLF warnings.

- [ ] **Step 3: Request review**

Ask a reviewer to inspect transition-rate math, runner gate wiring, metadata/report wording, and that historical simulation still avoids `state.json` writes.

- [ ] **Step 4: Commit, push, deploy**

Commit:

```powershell
git add src/backtest.py tests/test_backtest.py scripts/run_backtest.py tests/test_run_backtest_script.py README.md docs/BACKLOG.md docs/superpowers/plans/2026-05-21-b011-historical-simulation-evidence.md
git commit -m "feat: add historical simulation evidence"
git push
```

Deploy to Pi with focused tests, full tests, compile, service restart, and HTTP smoke.
