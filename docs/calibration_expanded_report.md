# Expanded Calibration Report

Ticket: B-164

This is research-only statistical calibration evidence. It does not change live scoring, alerts, recommendations, broker behavior, or dashboard decision text.

## Split

- Profile: `fixed_5y_train_2y_to_3y_holdout`
- Status: `ready`
- Train window: `2018-06-22` to `2023-06-16`
- Holdout window: `2023-06-23` to `2026-05-22` (2.92 years)
- No-lookahead verified: `True`

## Candidate Counts

- Label rows: 4968
- Candidate rows: 432
- True sector override rows: 0
- Live promotion allowed: `false`

## Strongest Candidate Rows

- `xlf_positive_score_ge_1_2` (positive, 13w, scope `US Sectors`, sector `XLF`): holdout hit-rate delta 59.49%; bootstrap CI [0.481013, 0.696203]; do not promote.
  - Rejection/status reasons: `thin_sample`
- `xlf_positive_score_ge_1_2` (positive, 26w, scope `US Sectors`, sector `XLF`): holdout hit-rate delta 51.95%; bootstrap CI [0.414286, 0.623377]; do not promote.
  - Rejection/status reasons: `thin_sample`
- `global_positive_score_ge_1_2` (positive, 26w, scope `global`): holdout hit-rate delta 27.80%; bootstrap CI [0.145341, 0.405721]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_2` (positive, 26w, scope `US Sectors`): holdout hit-rate delta 27.80%; bootstrap CI [0.145341, 0.405721]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `global_positive_score_ge_1_0` (positive, 26w, scope `global`): holdout hit-rate delta 23.80%; bootstrap CI [0.150082, 0.323021]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_0` (positive, 26w, scope `US Sectors`): holdout hit-rate delta 23.80%; bootstrap CI [0.150082, 0.323021]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `xlu_positive_score_ge_1_0` (positive, 52w, scope `US Sectors`, sector `XLU`): holdout hit-rate delta 16.67%; bootstrap CI [-0.4, 0.733333]; do not promote.
  - Rejection/status reasons: `thin_sample`
- `global_positive_score_ge_1_2` (positive, 52w, scope `global`): holdout hit-rate delta 16.02%; bootstrap CI [0.015707, 0.290113]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_2` (positive, 52w, scope `US Sectors`): holdout hit-rate delta 16.02%; bootstrap CI [0.015707, 0.290113]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `global_positive_score_ge_1_0` (positive, 52w, scope `global`): holdout hit-rate delta 15.79%; bootstrap CI [0.081455, 0.237077]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`

## Sector Overrides

- No ticker-level sector override passed the research gate.

## Safety

- Expanded calibration is artifact-only and read-only in the dashboard.
- Sector weights are research candidates, not active live methodology parameters.
- Live promotion requires a separate reviewed ticket with activation flag, frozen config, rollback plan, and evidence-gate approval.
