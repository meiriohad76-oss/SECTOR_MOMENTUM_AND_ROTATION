# Massive Historical Provider-Data Validation Report

Generated UTC: 2026-05-22T08:38:25.045740Z
Ticket: B-159

No Massive-derived rule is promoted into live scoring, veto logic, alerts, recommendations, provider-flow behavior, Pillar 7 weights, or broker behavior by this report.

## Provider Configuration

- Requested OHLCV provider: massive
- Resolved OHLCV provider: massive
- OOS start: 2024-01-05
- Validation split: walk-forward fallback because configured OOS start would leave 0 in-sample and 414 OOS rebalances

## Data Sets And Endpoints Checked

- yfinance.download
- https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}
- https://api.massive.com/v3/trades/{ticker}

## Main Run Data Windows

- Market prices: 2018-06-19 to 2026-05-21 (1992 rows, 11 tickers)
- Methodology rebalances: 2018-06-22 to 2026-05-21 (414 rows)

## OHLCV Source Evidence

- Cache policy: bypassed for B-159 validation
- Source provider: massive
- Fetched tickers: 14
- Fresh cache hits: 0
- Stale cache hits: 0
- Missing tickers: 0

## Historical Coverage By Ticker

- yfinance: AGG:2003-09-29->2026-05-21(5698); BIL:2007-05-30->2026-05-21(4776); SPY:1993-01-29->2026-05-21(8385); XLB:1998-12-22->2026-05-21(6895); XLC:2018-06-19->2026-05-21(1992); XLE:1998-12-22->2026-05-21(6895); XLF:1998-12-22->2026-05-21(6895); XLI:1998-12-22->2026-05-21(6895); XLK:1998-12-22->2026-05-21(6895); XLP:1998-12-22->2026-05-21(6895); XLRE:2015-10-08->2026-05-21(2670); XLU:1998-12-22->2026-05-21(6895); XLV:1998-12-22->2026-05-21(6895); XLY:1998-12-22->2026-05-21(6895)
- massive: AGG:2016-05-24->2026-05-21(2513); BIL:2016-05-24->2026-05-21(2513); SPY:2016-05-24->2026-05-21(2513); XLB:2016-05-24->2026-05-21(2513); XLC:2018-06-19->2026-05-21(1992); XLE:2016-05-24->2026-05-21(2513); XLF:2016-05-24->2026-05-21(2513); XLI:2016-05-24->2026-05-21(2513); XLK:2016-05-24->2026-05-21(2513); XLP:2016-05-24->2026-05-21(2513); XLRE:2016-05-24->2026-05-21(2513); XLU:2016-05-24->2026-05-21(2513); XLV:2016-05-24->2026-05-21(2513); XLY:2016-05-24->2026-05-21(2513)

## Baseline Vs Massive OHLCV

| Variant | Provider | Status | Coverage | Tickers | CAGR Delta | Sharpe Delta | Drawdown Delta | OOS CAGR Delta | OOS Sharpe Delta | OOS Drawdown Delta | Label |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Default/yfinance OHLCV baseline | yfinance | available | 2018-06-19 to 2026-05-21 | 14 | 0.00% | 0.00 | 0.00% | 0.00% | 0.00 | 0.00% | needs more testing |
| Massive aggregate OHLCV | massive | available | 2018-06-19 to 2026-05-21 | 14 | -0.15% | -0.01 | -0.38% | 0.22% | 0.03 | 1.57% | needs more testing |

## Provider-Derived Criteria Sweeps

| Variant | Endpoint | Status | Threshold | Label | Notes |
|---|---|---|---:|---|---|
| Block-trade upside ratio >= 1 | https://api.massive.com/v3/trades/{ticker} | unavailable_no_historical_asof_snapshots | 1.00 | do not promote | The current trade-tape endpoint can inform live provider flow, but this runner has no persisted timestamped as-of snapshots for historical rebalances. |
| Block-trade upside ratio >= 1.25 | https://api.massive.com/v3/trades/{ticker} | unavailable_no_historical_asof_snapshots | 1.25 | do not promote | The current trade-tape endpoint can inform live provider flow, but this runner has no persisted timestamped as-of snapshots for historical rebalances. |
| Block-trade upside ratio >= 1.5 | https://api.massive.com/v3/trades/{ticker} | unavailable_no_historical_asof_snapshots | 1.50 | do not promote | The current trade-tape endpoint can inform live provider flow, but this runner has no persisted timestamped as-of snapshots for historical rebalances. |

## Leakage And Survivorship Controls

- Validation OHLCV fetches bypass the local cache so provider evidence is fresh for the report run.
- yfinance and Massive provider rows are fetched separately and compared as data-source evidence, not as live rules.
- Historical methodology targets are built from OHLCV sliced through each rebalance date.
- Massive trade-tape/block-trade sweeps are labeled `do not promote` until timestamped as-of snapshots exist.
- Use B-160 before any Massive-derived criterion changes scoring, alerts, vetoes, recommendations, provider-flow behavior, Pillar 7 weights, or broker behavior.

## Decision

Treat B-159 as research evidence only. Promote only through B-160 after review and deterministic tests.
