# B-011 Backtest Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, auditable backtest harness that can evaluate the sector-rotation methodology against benchmarks, cost scenarios, and out-of-sample acceptance gates.

**Architecture:** Start with a pure pandas/numpy accounting engine in `src/backtest.py`, covered by deterministic unit tests. Then add benchmark builders, acceptance gates, historical signal generation that reuses pure `src/` modules without importing `app.py`, and finally reporting/dashboard integration. A vectorbt adapter is optional and must sit behind an import check so the core harness remains testable on Python 3.14.

**Tech Stack:** Python 3, pandas, numpy, pytest, yfinance-backed OHLCV from `src.data`, existing scoring modules, optional vectorbt adapter.

---

## Files

- Create: `src/backtest.py`
- Create: `tests/test_backtest.py`
- Later create: `scripts/run_backtest.py`
- Later create: `docs/backtest_report.md`
- Later modify: `requirements.txt`
- Later modify: `README.md`
- Later modify: `docs/BACKLOG.md`
- Later modify: `app.py` only after the report layer is proven

---

### Task 1: Deterministic Portfolio Accounting Core

**Files:**
- Create: `tests/test_backtest.py`
- Create: `src/backtest.py`

- [ ] **Step 1: Write failing accounting tests**

Create `tests/test_backtest.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from src import backtest


def test_run_weight_backtest_uses_prior_weights_and_charges_turnover_costs():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0, 121.0],
            "BBB": [100.0, 100.0, 100.0, 110.0],
        },
        index=dates,
    )
    target_weights = pd.DataFrame(
        {
            "AAA": [1.0, 0.0],
            "BBB": [0.0, 1.0],
        },
        index=[dates[0], dates[2]],
    )

    result = backtest.run_weight_backtest(
        prices,
        target_weights,
        transaction_cost_bps=10.0,
        initial_capital=100.0,
    )

    assert result.gross_returns.tolist() == pytest.approx([0.10, 0.10, 0.10])
    assert result.turnover.tolist() == pytest.approx([1.0, 0.0, 2.0])
    assert result.costs.tolist() == pytest.approx([0.001, 0.0, 0.002])
    assert result.net_returns.tolist() == pytest.approx([0.099, 0.10, 0.098])
    assert result.equity.iloc[0] == pytest.approx(100.0)
    assert result.equity.iloc[-1] == pytest.approx(132.714522)


def test_performance_metrics_reports_drawdown_and_turnover():
    dates = pd.bdate_range("2024-01-01", periods=5)
    returns = pd.Series([0.10, -0.25, 0.10, 0.00], index=dates[1:])
    equity = pd.Series([100.0, 110.0, 82.5, 90.75, 90.75], index=dates)
    turnover = pd.Series([1.0, 0.0, 0.5, 0.0], index=dates[1:])

    metrics = backtest.performance_metrics(
        returns,
        equity=equity,
        turnover=turnover,
        periods_per_year=4,
    )

    assert metrics["total_return"] == pytest.approx(-0.0925)
    assert metrics["max_drawdown"] == pytest.approx(-0.25)
    assert metrics["calmar"] < 0
    assert metrics["average_turnover"] == pytest.approx(0.375)
    assert metrics["annualized_turnover"] == pytest.approx(1.5)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
```

Expected: fails because `src.backtest` does not exist.

- [ ] **Step 3: Implement the accounting core**

Create `src/backtest.py`:

```python
"""Pure backtest accounting helpers.

This module intentionally has no Streamlit imports, no network calls, and no
state-file writes. It accepts already-loaded prices and target weights.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestResult:
    prices: pd.DataFrame
    target_weights: pd.DataFrame
    period_weights: pd.DataFrame
    gross_returns: pd.Series
    turnover: pd.Series
    costs: pd.Series
    net_returns: pd.Series
    equity: pd.Series
    metrics: dict[str, float]


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    out = prices.copy()
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out = out.apply(pd.to_numeric, errors="coerce")
    return out.dropna(how="all").ffill()


def _prepare_target_weights(prices: pd.DataFrame, target_weights: pd.DataFrame) -> pd.DataFrame:
    weights = target_weights.copy()
    weights.index = pd.to_datetime(weights.index)
    weights = weights.sort_index()
    weights = weights.reindex(columns=prices.columns, fill_value=0.0).fillna(0.0)
    row_abs = weights.abs().sum(axis=1)
    over_allocated = row_abs > 1.0
    if over_allocated.any():
        weights.loc[over_allocated] = weights.loc[over_allocated].div(row_abs.loc[over_allocated], axis=0)
    return weights


def _period_weights(prices: pd.DataFrame, target_weights: pd.DataFrame) -> pd.DataFrame:
    aligned = target_weights.reindex(prices.index).ffill().fillna(0.0)
    return aligned.shift(1).iloc[1:].fillna(0.0)


def _period_turnover(prices: pd.DataFrame, target_weights: pd.DataFrame) -> pd.Series:
    zero = pd.DataFrame([[0.0] * len(target_weights.columns)], columns=target_weights.columns)
    changes = target_weights.reset_index(drop=True).diff()
    changes.iloc[0] = target_weights.iloc[0] - zero.iloc[0]
    changes.index = target_weights.index
    trade_turnover = changes.abs().sum(axis=1)
    return trade_turnover.reindex(prices.index).shift(1).iloc[1:].fillna(0.0)


def equity_curve(returns: pd.Series, initial_capital: float = 1.0) -> pd.Series:
    if returns.empty:
        return pd.Series(dtype=float)
    first_date = returns.index[0] - (returns.index[0] - returns.index[0])
    base = pd.Series([float(initial_capital)], index=[first_date])
    curve = initial_capital * (1.0 + returns).cumprod()
    return pd.concat([base, curve])


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def performance_metrics(
    returns: pd.Series,
    equity: Optional[pd.Series] = None,
    turnover: Optional[pd.Series] = None,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    returns = returns.astype(float).dropna()
    if equity is None:
        equity = equity_curve(returns)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0) if len(equity) else 0.0
    years = max(len(returns) / periods_per_year, 1 / periods_per_year)
    cagr = float((1.0 + total_return) ** (1.0 / years) - 1.0) if total_return > -1 else -1.0
    vol = float(returns.std(ddof=0) * np.sqrt(periods_per_year)) if len(returns) else 0.0
    excess = returns - risk_free_rate / periods_per_year
    sharpe = float(excess.mean() / excess.std(ddof=0) * np.sqrt(periods_per_year)) if excess.std(ddof=0) else 0.0
    downside = returns.where(returns < 0, 0.0)
    downside_std = downside.std(ddof=0)
    sortino = float(excess.mean() / downside_std * np.sqrt(periods_per_year)) if downside_std else 0.0
    mdd = max_drawdown(equity)
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0
    avg_turnover = float(turnover.mean()) if turnover is not None and len(turnover) else 0.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": mdd,
        "calmar": calmar,
        "average_turnover": avg_turnover,
        "annualized_turnover": avg_turnover * periods_per_year,
    }


def run_weight_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    transaction_cost_bps: float = 0.0,
    initial_capital: float = 1.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> BacktestResult:
    clean_prices = _clean_prices(prices)
    clean_weights = _prepare_target_weights(clean_prices, target_weights)
    asset_returns = clean_prices.pct_change().iloc[1:].fillna(0.0)
    weights = _period_weights(clean_prices, clean_weights)
    gross_returns = (asset_returns * weights).sum(axis=1)
    turnover = _period_turnover(clean_prices, clean_weights)
    costs = turnover * (transaction_cost_bps / 10_000.0)
    net_returns = gross_returns - costs
    equity = pd.concat(
        [
            pd.Series([float(initial_capital)], index=[clean_prices.index[0]]),
            initial_capital * (1.0 + net_returns).cumprod(),
        ]
    )
    metrics = performance_metrics(
        net_returns,
        equity=equity,
        turnover=turnover,
        periods_per_year=periods_per_year,
    )
    return BacktestResult(
        prices=clean_prices,
        target_weights=clean_weights,
        period_weights=weights,
        gross_returns=gross_returns,
        turnover=turnover,
        costs=costs,
        net_returns=net_returns,
        equity=equity,
        metrics=metrics,
    )
```

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run full suite**

Run:

```powershell
python -m pytest -q
```

Expected: all existing tests plus the two new backtest tests pass.

- [ ] **Step 6: Commit task**

```powershell
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: add backtest accounting core"
```

---

### Task 2: Price Matrix And Benchmark Builders

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests for OHLCV close extraction and static benchmark weights**

Append to `tests/test_backtest.py`:

```python
def test_close_matrix_prefers_adjusted_close_and_aligns_tickers(ohlcv_frame_factory):
    aaa = ohlcv_frame_factory(days=5, start_price=100.0)
    bbb = ohlcv_frame_factory(days=5, start_price=50.0).drop(columns=["adj_close"])

    out = backtest.close_matrix_from_ohlcv({"BBB": bbb, "AAA": aaa})

    assert list(out.columns) == ["AAA", "BBB"]
    assert out.index.is_monotonic_increasing
    assert out["AAA"].iloc[0] == pytest.approx(aaa["adj_close"].iloc[0])
    assert out["BBB"].iloc[0] == pytest.approx(bbb["close"].iloc[0])


def test_static_weight_benchmark_rebalances_to_requested_weights():
    dates = pd.bdate_range("2024-01-01", periods=3)

    weights = backtest.static_weight_targets(
        dates,
        {"SPY": 0.60, "AGG": 0.40},
    )

    assert list(weights.columns) == ["AGG", "SPY"]
    assert weights.loc[dates[0], "SPY"] == pytest.approx(0.60)
    assert weights.loc[dates[-1], "AGG"] == pytest.approx(0.40)
    assert weights.sum(axis=1).tolist() == pytest.approx([1.0, 1.0, 1.0])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
```

Expected: fails because `close_matrix_from_ohlcv()` and `static_weight_targets()` do not exist.

- [ ] **Step 3: Implement benchmark helpers**

Add to `src/backtest.py`:

```python
def close_matrix_from_ohlcv(ohlcv: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = {}
    for ticker in sorted(ohlcv):
        frame = ohlcv[ticker]
        if frame.empty:
            continue
        column = "adj_close" if "adj_close" in frame.columns else "close"
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        values.index = pd.to_datetime(values.index)
        series[ticker] = values.sort_index()
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index().ffill().dropna(how="all")


def static_weight_targets(index: pd.DatetimeIndex, weights: dict[str, float]) -> pd.DataFrame:
    columns = sorted(weights)
    frame = pd.DataFrame(index=pd.to_datetime(index), columns=columns, dtype=float)
    for ticker in columns:
        frame[ticker] = float(weights[ticker])
    row_sum = frame.abs().sum(axis=1)
    if (row_sum > 1.0).any():
        frame = frame.div(row_sum, axis=0)
    return frame.fillna(0.0)


def sixty_forty_targets(index: pd.DatetimeIndex, equity_ticker: str = "SPY", bond_ticker: str = "AGG") -> pd.DataFrame:
    return static_weight_targets(index, {equity_ticker: 0.60, bond_ticker: 0.40})


def equal_weight_targets(index: pd.DatetimeIndex, tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame(index=pd.to_datetime(index))
    weight = 1.0 / len(tickers)
    return static_weight_targets(index, {ticker: weight for ticker in tickers})
```

- [ ] **Step 4: Run targeted and full tests**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit task**

```powershell
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: add backtest benchmark builders"
```

---

### Task 3: Cost Sensitivity And Acceptance Gates

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests for cost scenarios and gates**

Append to `tests/test_backtest.py`:

```python
def test_run_cost_scenarios_returns_metrics_by_bps():
    dates = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame({"AAA": [100.0, 110.0, 121.0, 133.1]}, index=dates)
    weights = pd.DataFrame({"AAA": [1.0]}, index=[dates[0]])

    scenarios = backtest.run_cost_scenarios(
        prices,
        weights,
        cost_bps_values=[0, 10],
        initial_capital=100.0,
    )

    assert list(scenarios.index) == [0, 10]
    assert scenarios.loc[0, "total_return"] > scenarios.loc[10, "total_return"]


def test_evaluate_acceptance_gates_compares_oos_to_equal_weight_benchmark():
    report = backtest.evaluate_acceptance_gates(
        strategy_metrics={
            "sharpe": 0.80,
            "max_drawdown": -0.20,
            "annualized_turnover": 2.50,
            "state_transitions_per_ticker_year": 3.0,
        },
        equal_weight_metrics={"max_drawdown": -0.30},
    )

    assert report["oos_sharpe"]["passed"] is True
    assert report["max_drawdown"]["passed"] is True
    assert report["annualized_turnover"]["passed"] is True
    assert report["state_transitions"]["passed"] is True
    assert report["all_passed"] is True
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
```

Expected: fails because `run_cost_scenarios()` and `evaluate_acceptance_gates()` do not exist.

- [ ] **Step 3: Implement cost scenarios and gates**

Add to `src/backtest.py`:

```python
def run_cost_scenarios(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps_values: list[int | float] = [3, 5, 10],
    initial_capital: float = 1.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.DataFrame:
    rows = []
    for cost_bps in cost_bps_values:
        result = run_weight_backtest(
            prices,
            target_weights,
            transaction_cost_bps=float(cost_bps),
            initial_capital=initial_capital,
            periods_per_year=periods_per_year,
        )
        row = {"cost_bps": float(cost_bps), **result.metrics}
        rows.append(row)
    return pd.DataFrame(rows).set_index("cost_bps")


def _gate(name: str, value: float, threshold: float, passed: bool) -> dict[str, float | bool | str]:
    return {
        "name": name,
        "value": float(value),
        "threshold": float(threshold),
        "passed": bool(passed),
    }


def evaluate_acceptance_gates(
    strategy_metrics: dict[str, float],
    equal_weight_metrics: dict[str, float],
    min_oos_sharpe: float = 0.70,
    max_drawdown_ratio: float = 0.75,
    max_annualized_turnover: float = 3.0,
    max_state_transitions_per_ticker_year: float = 4.0,
) -> dict[str, dict | bool]:
    strategy_dd = abs(float(strategy_metrics.get("max_drawdown", 0.0)))
    benchmark_dd = abs(float(equal_weight_metrics.get("max_drawdown", 0.0)))
    max_allowed_dd = benchmark_dd * max_drawdown_ratio
    gates = {
        "oos_sharpe": _gate(
            "Out-of-sample Sharpe",
            float(strategy_metrics.get("sharpe", 0.0)),
            min_oos_sharpe,
            float(strategy_metrics.get("sharpe", 0.0)) >= min_oos_sharpe,
        ),
        "max_drawdown": _gate(
            "Max drawdown",
            strategy_dd,
            max_allowed_dd,
            strategy_dd <= max_allowed_dd,
        ),
        "annualized_turnover": _gate(
            "Annualized turnover",
            float(strategy_metrics.get("annualized_turnover", 0.0)),
            max_annualized_turnover,
            float(strategy_metrics.get("annualized_turnover", 0.0)) <= max_annualized_turnover,
        ),
        "state_transitions": _gate(
            "State transitions per ticker-year",
            float(strategy_metrics.get("state_transitions_per_ticker_year", 0.0)),
            max_state_transitions_per_ticker_year,
            float(strategy_metrics.get("state_transitions_per_ticker_year", 0.0)) <= max_state_transitions_per_ticker_year,
        ),
    }
    gates["all_passed"] = all(item["passed"] for item in gates.values() if isinstance(item, dict))
    return gates
```

- [ ] **Step 4: Run targeted and full tests**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit task**

```powershell
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: add backtest gates and cost scenarios"
```

---

### Task 4: Historical Methodology Target Weights

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `src/backtest.py`

- [ ] **Step 1: Write failing tests for selected-ticker target weights**

Append to `tests/test_backtest.py`:

```python
def test_target_weights_from_scores_uses_selected_tickers_only():
    scores = pd.DataFrame(
        {
            "selected": [True, True, False],
            "S_score_after_veto": [2.0, 1.0, -9.99],
        },
        index=["XLK", "XLF", "XLE"],
    )

    weights = backtest.target_weights_from_scores(scores)

    assert weights.to_dict() == pytest.approx({"XLK": 0.5, "XLF": 0.5})
    assert "XLE" not in weights
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_target_weights_from_scores_uses_selected_tickers_only -q
```

Expected: fails because `target_weights_from_scores()` does not exist.

- [ ] **Step 3: Implement selected-ticker weights**

Add to `src/backtest.py`:

```python
def target_weights_from_scores(scored_df: pd.DataFrame) -> pd.Series:
    if scored_df.empty or "selected" not in scored_df.columns:
        return pd.Series(dtype=float)
    selected = scored_df[scored_df["selected"]].copy()
    if selected.empty:
        return pd.Series(dtype=float)
    weight = 1.0 / len(selected)
    return pd.Series(weight, index=selected.index, dtype=float).sort_index()
```

- [ ] **Step 4: Add historical runner shell after weight contract is green**

Add this minimal runner API to `src/backtest.py` so later tasks can fill signal computation without changing call sites:

```python
def weekly_rebalance_dates(prices: pd.DataFrame) -> pd.DatetimeIndex:
    if prices.empty:
        return pd.DatetimeIndex([])
    weekly = prices.resample("W-FRI").last().dropna(how="all")
    return weekly.index
```

- [ ] **Step 5: Run targeted and full tests**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit task**

```powershell
git add src/backtest.py tests/test_backtest.py
git commit -m "feat: add methodology target weights"
```

---

### Task 5: Report Skeleton And Manual Runner

**Files:**
- Create: `scripts/run_backtest.py`
- Create or update: `docs/backtest_report.md`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Add a no-network report writer test**

Create a small test in `tests/test_backtest.py` that formats a gate report without fetching market data:

```python
def test_format_gate_report_includes_pass_fail_lines():
    gates = {
        "oos_sharpe": {"name": "Out-of-sample Sharpe", "value": 0.8, "threshold": 0.7, "passed": True},
        "max_drawdown": {"name": "Max drawdown", "value": 0.2, "threshold": 0.225, "passed": True},
        "all_passed": True,
    }

    text = backtest.format_gate_report(gates)

    assert "Out-of-sample Sharpe: PASS" in text
    assert "Max drawdown: PASS" in text
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_format_gate_report_includes_pass_fail_lines -q
```

Expected: fails because `format_gate_report()` does not exist.

- [ ] **Step 3: Implement report formatter**

Add to `src/backtest.py`:

```python
def format_gate_report(gates: dict[str, dict | bool]) -> str:
    lines = ["# Backtest Acceptance Gates", ""]
    for key, gate in gates.items():
        if key == "all_passed" or not isinstance(gate, dict):
            continue
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"- {gate['name']}: {status} "
            f"(value {gate['value']:.4f}, threshold {gate['threshold']:.4f})"
        )
    lines.append("")
    lines.append(f"Overall: {'PASS' if gates.get('all_passed') else 'FAIL'}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Add manual runner**

Create `scripts/run_backtest.py`:

```python
from __future__ import annotations

from pathlib import Path

from src import backtest
from src.data import fetch_ohlcv


def main() -> int:
    tickers = ["SPY", "AGG", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]
    ohlcv = fetch_ohlcv(tickers, period="max")
    prices = backtest.close_matrix_from_ohlcv(ohlcv).loc["2003-01-01":]
    rebalance_dates = backtest.weekly_rebalance_dates(prices)
    sixty_forty = backtest.sixty_forty_targets(rebalance_dates)
    result = backtest.run_weight_backtest(prices[["SPY", "AGG"]], sixty_forty, transaction_cost_bps=5.0)
    report = backtest.format_gate_report(
        backtest.evaluate_acceptance_gates(
            strategy_metrics={**result.metrics, "state_transitions_per_ticker_year": 0.0},
            equal_weight_metrics={"max_drawdown": result.metrics["max_drawdown"]},
        )
    )
    Path("docs/backtest_report.md").write_text(report, encoding="utf-8")
    print("Wrote docs/backtest_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run offline tests and compile**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
python -m pytest -q
python -m compileall app.py src scripts
```

Expected: all tests pass and compile exits 0.

- [ ] **Step 6: Commit task**

```powershell
git add src/backtest.py tests/test_backtest.py scripts/run_backtest.py README.md docs/BACKLOG.md
git commit -m "feat: add backtest report runner"
```

---

### Task 6: Final B-011 QA And Review

**Files:**
- No new edits unless verification finds a bug.

- [ ] **Step 1: Run deterministic B-011 gate**

Run:

```powershell
python -m pytest tests/test_backtest.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check origin/main...HEAD
git status --short --branch
```

Expected: tests pass, compile exits 0, diff check is clean, working tree is clean.

- [ ] **Step 2: Optional manual data run**

Run only after deterministic gates pass:

```powershell
python scripts/run_backtest.py
```

Expected: writes `docs/backtest_report.md`. Treat network or yfinance failures as manual evidence gaps, not unit-test failures.

- [ ] **Step 3: Request subagent review**

Review scope:

- `src/backtest.py`
- `tests/test_backtest.py`
- `scripts/run_backtest.py`
- `docs/backtest_report.md` if generated
- `docs/BACKLOG.md`
- `README.md`

Reviewer checklist:

- No lookahead in weight application.
- Transaction costs are charged from turnover.
- Acceptance gates match methodology section 8.
- Tests are deterministic and offline.
- No `app.py` import or `state.json` writes.
- Docs do not claim live edge unless a fresh manual run supports it.

- [ ] **Step 4: Mark B-011 progress**

After review issues are fixed and all gates pass, mark B-011 as completed or partially completed in `docs/BACKLOG.md` with exact scope, verification commands, and any manual-data limitations.
