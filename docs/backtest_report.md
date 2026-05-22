# Manual Backtest Smoke Report

## Strategy Metrics

| Metric | Value |
|---|---:|
| Total return | 102.19% |
| CAGR | 9.32% |
| Sharpe | 0.59 |
| Sortino | 0.81 |
| Max drawdown | -30.09% |
| Calmar | 0.31 |
| Annualized turnover | 2379.45% |

## Benchmark Comparison

| Benchmark | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| Methodology | 9.32% | 0.59 | -30.09% |
| 60/40 SPY/AGG | 7.83% | 0.68 | -22.22% |
| Equal-weight sectors | 10.16% | 0.62 | -36.87% |

## Cost Sensitivity

| Cost | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| 3 bps | 9.84% | 0.61 | -30.06% |
| 5 bps | 9.32% | 0.59 | -30.09% |
| 10 bps | 8.03% | 0.52 | -30.14% |

## Historical Methodology Simulation

| Evidence | Value |
|---|---:|
| Start date | 2018-06-22 |
| End date | 2026-05-21 |
| Rebalances | 414 |
| State tickers | 12 |
| Selected tickers | 11 |
| State transitions | 939 |
| State transitions per ticker-year | 9.85 |

## In-Sample / Out-of-Sample

OOS starts: 2015-01-01

| Window | Total Return | CAGR | Sharpe | Max Drawdown | Annualized Turnover |
|---|---:|---:|---:|---:|---:|
| Methodology full period | 102.19% | 9.32% | 0.59 | -30.09% | 2379.45% |
| Methodology in-sample | 0.00% | 0.00% | 0.00 | 0.00% | 0.00% |
| Methodology out-of-sample | 102.19% | 9.32% | 0.59 | -30.09% | 2379.45% |
| 60/40 out-of-sample | 81.36% | 7.83% | 0.68 | -22.22% | 57.78% |
| Equal-weight sectors out-of-sample | 114.79% | 10.16% | 0.62 | -36.87% | 84.62% |

## Macro Condition Variants

Analysis-only exposure filters from historical macro series. Positive deltas mean the variant beat the baseline methodology metric.

| Variant | Series | Condition | Active Rebalances | Return Delta | Sharpe Delta | Drawdown Delta |
|---|---|---|---:|---:|---:|---:|
| Stress rising defensive | STLFSI4 | rising | 213 | -18.76% | 0.19 | 17.28% |
| Curve falling defensive | T10Y2Y | falling | 180 | -80.25% | -0.33 | 7.90% |
| HY spread rising defensive | BAMLH0A0HYM2 | rising | 69 | -21.64% | -0.06 | 0.00% |

## Acceptance Gates

- Out-of-sample Sharpe: FAIL (value 0.5863, threshold 0.7000)
  Evidence: strategy OOS Sharpe >= 0.70
- Max drawdown: FAIL (value 0.3009, threshold 0.2766)
  Evidence: absolute strategy OOS drawdown <= 75% of equal-weight OOS drawdown (0.3687)
- Annualized turnover: FAIL (value 23.7945, threshold 3.0000)
  Evidence: strategy OOS annualized turnover <= 300%
- State transitions per ticker-year: FAIL (value 9.8523, threshold 4.0000)
  Evidence: historical state transitions per ticker-year <= 4.0

Overall: FAIL
