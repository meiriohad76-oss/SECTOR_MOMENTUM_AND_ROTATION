# B-011 Backtest Harness Design

## Goal

Build an auditable backtest harness for the sector-rotation methodology before adding more live signals. The harness must produce reproducible metrics, benchmark comparisons, cost sensitivity, and out-of-sample acceptance gates without writing dashboard state or depending on Streamlit import side effects.

## Context

`docs/sector-rotation-methodology.md` section 8 defines the target: 2003-to-today data, walk-forward evaluation, 60/40 SPY/AGG and equal-weight sector benchmarks, metrics including CAGR/Sharpe/Sortino/max drawdown/Calmar/turnover, and acceptance gates for out-of-sample Sharpe and drawdown. The current app computes only the latest snapshot from three years of data and `apply_state_machine()` writes `state.json`, so the backtest cannot reuse `app.py` or stateful scoring directly.

The local interpreter is Python 3.14 and `vectorbt` is not currently installed. Current PyPI metadata lists `vectorbt` 1.0.0 with Python `>=3.10` and classifiers through Python 3.13. The implementation should therefore keep deterministic pandas/numpy accounting as the tested source of truth, then add a thin optional vectorbt adapter only after the core engine is green.

## Approaches Considered

### Approach A: Vectorbt-first historical harness

Install vectorbt immediately, model orders in `Portfolio.from_orders()`, and build the methodology around vectorbt outputs.

Trade-off: fastest route to rich analytics if the dependency imports cleanly, but it makes the first test slice fragile in this Python 3.14 workspace and can hide accounting assumptions inside a large third-party engine.

### Approach B: Pure engine first, vectorbt adapter second

Create a small pure backtest engine that accepts close prices and dated target weights, computes shifted portfolio returns, turnover, per-side transaction costs, metrics, and acceptance gates. Add optional vectorbt parity later for richer analytics and dashboard experiments.

Trade-off: a little more local code, but every accounting rule is testable, deterministic, and independent of dependency availability. This is the recommended path.

### Approach C: Report/UI first

Add a `/backtest` dashboard section first and fill it with provisional or one-off calculations.

Trade-off: visually satisfying, but it would produce research theater before the accounting contract is proven. Defer UI until the engine and reports are trustworthy.

## Recommended Design

Use Approach B.

The first B-011 slice creates `src/backtest.py` and `tests/test_backtest.py`. `src/backtest.py` owns pure portfolio accounting:

- Convert OHLCV dictionaries into aligned adjusted-close matrices.
- Accept a target-weight DataFrame where rows are rebalance dates and columns are tickers.
- Shift target weights by one return period so Friday close decisions are applied to the next tradable interval.
- Compute gross returns, turnover, per-side transaction costs, net returns, and equity.
- Compute metrics: CAGR, annualized volatility, Sharpe, Sortino, max drawdown, Calmar, total return, average turnover, annualized turnover, and average holding period proxy.
- Build benchmarks: 60/40 SPY/AGG and equal-weight 11-sector baskets.
- Evaluate acceptance gates: out-of-sample Sharpe at least 0.7, max drawdown no worse than 75 percent of equal-weight sector benchmark, annualized turnover no more than 300 percent, and average state transitions no more than 4 per ticker per year once historical state simulation exists.

The second slice adds historical signal generation without importing `app.py`. It uses existing pure modules (`src.data`, `src.indicators`, `src.flow`, `src.macro`, `src.scoring.compute_composite`) on expanding windows at weekly rebalance dates. It must call `decide_state()` directly when historical states are needed and must not call `apply_state_machine()` because that writes `state.json`.

The third slice adds report outputs under `docs/` and data artifacts under a small ignored/generated path only if needed. A dashboard `/backtest` view can follow after the report file proves the results and acceptance gates.

## Data Flow

1. Fetch or provide daily OHLCV from 2003 onward.
2. Build adjusted close prices aligned by date.
3. At each weekly rebalance date, compute the methodology snapshot using only data available through that date.
4. Convert selected tickers to target weights.
5. Apply weights to subsequent returns, subtract transaction costs from turnover, and produce an equity curve.
6. Run the same accounting against benchmarks and cost scenarios.
7. Split outputs into in-sample and out-of-sample windows, with 2015 onward treated as out-of-sample.

## Test Strategy

Every task starts with a failing test. The deterministic core uses tiny price and weight matrices so expected returns, turnover, costs, drawdown, and gates can be calculated by hand. Historical signal tests use synthetic OHLCV fixtures and monkeypatch provider-backed flow stubs to remain offline. No test may import `app.py`, write `state.json`, or require network access.

## Acceptance Gates Before Moving Beyond B-011

- `python -m pytest tests/test_backtest.py -q`
- `python -m pytest -q`
- `python -m compileall app.py src`
- `git diff --check origin/main...HEAD`
- Subagent review for accounting, no-lookahead behavior, state-file isolation, and report wording.

Live 2003-to-today data runs may be added as a separate manual evidence step, but deterministic tests remain the completion gate for code correctness.

## Out Of Scope For First B-011 Slice

- Claiming the methodology has live edge.
- Persisting backtest artifacts as source-of-truth data.
- Importing `app.py`.
- Changing live dashboard selection behavior.
- Enabling provider-backed flow stubs beyond the B-010 ETF primary-flow seam.
