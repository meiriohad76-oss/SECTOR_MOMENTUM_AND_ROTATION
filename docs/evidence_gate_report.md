# Evidence Gate Report

Generated UTC: 2026-05-22T09:29:59.169609Z

No live scoring, veto, alert, recommendation, broker, or Pillar 7 behavior changes are made by this report.

## Promotion Criteria

- at least 20 active out-of-sample rebalances
- OOS Sharpe delta >= 0.10
- OOS CAGR delta >= 0
- OOS drawdown delta >= 0
- full-period Sharpe delta >= 0

## Gate Decisions

| Ticket | Source | Status | Validation Report | Candidates | Candidate Variants | Blockers |
|---|---|---|---|---:|---|---|
| B-158 | FRED macro | blocked_no_candidates | docs/fred_macro_validation_report.md | 0 | - | No candidate rows were present in the validation summary. |
| B-160 | Massive provider data | blocked_no_candidates | docs/massive_provider_validation_report.md | 0 | - | No candidate rows were present in the validation summary. |

## Rejected Or Unready Variants

- B-158: HY spread rising defensive, Stress rising defensive, Curve falling defensive
- B-160: Default/yfinance OHLCV baseline, Massive aggregate OHLCV, Block-trade upside ratio >= 1, Block-trade upside ratio >= 1.25, Block-trade upside ratio >= 1.5

## Rollback

Rollback for any future promoted rule is to remove the promoted criteria change, rerun the validation report, and confirm the gate returns to `blocked_no_candidates` or `ready_for_review` without altering live behavior from this report alone.

## Decision

Only tickets with `ready_for_review` may proceed to a separate reviewed promotion patch. Tickets with `blocked_no_candidates` or `blocked_invalid_summary` remain research-only.
