# FRED Macro Historical Validation Report

Generated UTC: 2026-05-22T07:22:03.699539Z
Ticket: B-157

No FRED macro rule is promoted into live scoring, veto logic, alerts, recommendations, or broker behavior by this report.

## Provider Configuration

- Requested OHLCV provider: massive
- Resolved OHLCV provider: massive
- FRED status: configured
- OOS start: 2024-01-05
- Validation split: walk-forward fallback because configured OOS start would leave 0 in-sample and 414 OOS rebalances

## Data Windows

- Market prices: 2018-06-19 to 2026-05-21 (1992 rows, 11 tickers)
- Methodology rebalances: 2018-06-22 to 2026-05-21 (414 rows)

## OHLCV Source Evidence

- Cache policy: bypassed for B-157 validation
- Source provider: massive
- Fetched tickers: 14
- Fresh cache hits: 0
- Stale cache hits: 0
- Missing tickers: 0

## FRED Series Windows

- BAMLC0A0CM: 2023-05-22 to 2026-05-20 (785 observations)
- BAMLH0A0HYM2: 2023-05-22 to 2026-05-20 (786 observations)
- CFNAI: 2003-01-01 to 2026-03-01 (279 observations)
- CPIAUCSL: 2003-01-01 to 2026-04-01 (279 observations)
- DCOILWTICO: 2003-01-02 to 2026-05-18 (5863 observations)
- DGS10: 2003-01-02 to 2026-05-20 (5850 observations)
- DHHNGSP: 2003-01-02 to 2026-05-18 (5874 observations)
- ICSA: 2003-01-04 to 2026-05-16 (1220 observations)
- INDPRO: 2003-01-01 to 2026-04-01 (280 observations)
- M2SL: 2003-01-01 to 2026-03-01 (279 observations)
- NFCI: 2003-01-03 to 2026-05-15 (1220 observations)
- PCEPILFE: 2003-01-01 to 2026-03-01 (279 observations)
- RECPROUSM156N: 2003-01-01 to 2026-03-01 (279 observations)
- STLFSI4: 2003-01-03 to 2026-05-15 (1220 observations)
- T10Y2Y: 2003-01-02 to 2026-05-21 (5851 observations)
- T10Y3M: 2003-01-02 to 2026-05-21 (5851 observations)
- T10YIE: 2003-01-02 to 2026-05-21 (5851 observations)
- UMCSENT: 2003-01-01 to 2026-03-01 (279 observations)
- UNRATE: 2003-01-01 to 2026-04-01 (279 observations)
- WALCL: 2003-01-01 to 2026-05-20 (1221 observations)

## Promotion Label Rules

- `candidate`: at least 20 active out-of-sample rebalances, OOS Sharpe delta >= 0.10, OOS CAGR delta >= 0, OOS drawdown delta >= 0, and full-period Sharpe delta >= 0.
- `do not promote`: enough OOS observations and no OOS improvement in Sharpe, CAGR, or drawdown.
- `needs more testing`: mixed evidence or insufficient OOS observations.

## Variant Results

| Variant | Series | Lag Days | Label | Active OOS | CAGR Delta | Sharpe Delta | Drawdown Delta | OOS CAGR Delta | OOS Sharpe Delta | OOS Drawdown Delta | Turnover Delta | Hit-Rate Delta | Trade Count Delta |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HY spread rising defensive | BAMLH0A0HYM2 | 1 | needs more testing | 47 | -2.01% | -0.08 | 0.00% | -2.76% | 0.36 | 9.49% | 293.40% | -8.39% | -29 |
| Stress rising defensive | STLFSI4 | 7 | needs more testing | 69 | -7.59% | -0.37 | 4.04% | -8.21% | -0.22 | 2.90% | 926.59% | -28.28% | -101 |
| Curve falling defensive | T10Y2Y | 1 | needs more testing | 64 | -3.94% | -0.13 | 11.25% | -11.63% | -0.70 | 0.60% | 645.39% | -25.87% | -105 |

## Decision

Use B-158 only for variants labeled `candidate` after review. Leave all other rules out of live behavior.
