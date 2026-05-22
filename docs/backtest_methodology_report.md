# Historical Methodology Backtest Report

## Executive Summary

This report is research evidence, not investment advice. It summarizes the manual B-011 historical methodology run and should be read alongside the deterministic pytest suite.

The methodology full-period CAGR is 9.32%, Sharpe is 0.59, and max drawdown is -30.09%.

## Methodology Under Test

The strategy path uses the historical methodology target builder: each rebalance date slices OHLCV through that date, scores with pure `src/` modules, converts selected tickers to equal target weights, and records states through `decide_state()` without calling `apply_state_machine()` or writing `state.json`.

provider-backed historical flow is neutral until as-of provider snapshots exist, which avoids current-data leakage in this report.

## Evidence Tables

### Historical Methodology Simulation

| Evidence | Value |
|---|---:|
| Start date | 2018-06-22 |
| End date | 2026-05-21 |
| Rebalances | 414 |
| State tickers | 12 |
| Selected tickers | 11 |
| State transitions | 939 |
| State transitions per ticker-year | 9.85 |

### Strategy Metrics

| Metric | Value |
|---|---:|
| Total return | 102.19% |
| CAGR | 9.32% |
| Sharpe | 0.59 |
| Sortino | 0.81 |
| Max drawdown | -30.09% |
| Calmar | 0.31 |
| Annualized turnover | 2379.45% |

### Benchmark Comparison

| Benchmark | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| Methodology | 9.32% | 0.59 | -30.09% |
| 60/40 SPY/AGG | 7.83% | 0.68 | -22.22% |
| Equal-weight sectors | 10.16% | 0.62 | -36.87% |

### In-Sample / Out-of-Sample

| Window | Total Return | CAGR | Sharpe | Max Drawdown | Annualized Turnover |
|---|---:|---:|---:|---:|---:|
| Methodology full period | 102.19% | 9.32% | 0.59 | -30.09% | 2379.45% |
| Methodology in-sample | 43.23% | 6.71% | 0.43 | -30.09% | 2232.15% |
| Methodology out-of-sample | 41.17% | 15.69% | 1.11 | -14.88% | 2724.20% |
| 60/40 out-of-sample | 32.82% | 12.75% | 1.24 | -11.88% | 38.25% |
| Equal-weight sectors out-of-sample | 38.77% | 14.86% | 1.15 | -16.16% | 70.11% |

## Acceptance Gates

- Out-of-sample Sharpe: PASS (value 1.1112, threshold 0.7000)
  Evidence: strategy OOS Sharpe >= 0.70
- Max drawdown: FAIL (value 0.1488, threshold 0.1212)
  Evidence: absolute strategy OOS drawdown <= 75% of equal-weight OOS drawdown (0.1616)
- Annualized turnover: FAIL (value 27.2420, threshold 3.0000)
  Evidence: strategy OOS annualized turnover <= 300%
- State transitions per ticker-year: FAIL (value 9.8523, threshold 4.0000)
  Evidence: historical state transitions per ticker-year <= 4.0

Overall: FAIL

## Limitations And Next Work

- Manual artifacts are evidence for review, not a live-edge claim.
- provider-backed historical flow is neutral until timestamped as-of feeds are available.
- The notebook/report guide does not replace deterministic tests or live provider validation.
- Backtest results do not guarantee future performance.
