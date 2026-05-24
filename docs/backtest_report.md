# Manual Backtest Smoke Report

## Strategy Metrics

| Metric | Value |
|---|---:|
| Total return | 92.32% |
| CAGR | 8.63% |
| Sharpe | 0.55 |
| Sortino | 0.76 |
| Max drawdown | -30.09% |
| Calmar | 0.29 |
| Annualized turnover | 2415.71% |

## Benchmark Comparison

| Benchmark | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| Methodology | 8.63% | 0.55 | -30.09% |
| 60/40 SPY/AGG | 7.86% | 0.68 | -22.22% |
| Equal-weight sectors | 10.22% | 0.62 | -36.87% |

## Cost Sensitivity

| Cost | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| 3 bps | 9.15% | 0.58 | -30.06% |
| 5 bps | 8.63% | 0.55 | -30.09% |
| 10 bps | 7.32% | 0.48 | -30.14% |

## Historical Methodology Simulation

| Evidence | Value |
|---|---:|
| Start date | 2018-06-22 |
| End date | 2026-05-22 |
| Rebalances | 414 |
| State tickers | 12 |
| Selected tickers | 11 |
| State transitions | 939 |
| State transitions per ticker-year | 9.85 |

## In-Sample / Out-of-Sample

OOS starts: 2024-01-05

| Window | Total Return | CAGR | Sharpe | Max Drawdown | Annualized Turnover |
|---|---:|---:|---:|---:|---:|
| Methodology full period | 92.32% | 8.63% | 0.55 | -30.09% | 2415.71% |
| Methodology in-sample | 37.52% | 5.92% | 0.39 | -30.09% | 2277.10% |
| Methodology out-of-sample | 39.85% | 15.21% | 1.08 | -15.69% | 2739.60% |
| 60/40 out-of-sample | 33.19% | 12.86% | 1.25 | -11.88% | 38.18% |
| Equal-weight sectors out-of-sample | 39.45% | 15.07% | 1.16 | -16.16% | 69.99% |

## Acceptance Gates

- Out-of-sample Sharpe: PASS (value 1.0799, threshold 0.7000)
  Evidence: strategy OOS Sharpe >= 0.70
- Max drawdown: FAIL (value 0.1569, threshold 0.1212)
  Evidence: absolute strategy OOS drawdown <= 75% of equal-weight OOS drawdown (0.1616)
- Annualized turnover: FAIL (value 27.3960, threshold 3.0000)
  Evidence: strategy OOS annualized turnover <= 300%
- State transitions per ticker-year: FAIL (value 9.8523, threshold 4.0000)
  Evidence: historical state transitions per ticker-year <= 4.0

Overall: FAIL
