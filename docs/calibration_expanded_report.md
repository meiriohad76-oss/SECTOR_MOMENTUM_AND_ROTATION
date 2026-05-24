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
- Candidate rows: 135
- Sector/class override rows: 4
- Live promotion allowed: `false`

## Strongest Candidate Rows

- `global_positive_score_ge_1_2` (positive, 26w, scope `global`): holdout hit-rate delta 27.80%; bootstrap CI [0.132018, 0.402906]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_2` (positive, 26w, scope `US Sectors`): holdout hit-rate delta 27.80%; bootstrap CI [0.132018, 0.402906]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `global_positive_score_ge_1_0` (positive, 26w, scope `global`): holdout hit-rate delta 23.80%; bootstrap CI [0.141285, 0.335421]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_0` (positive, 26w, scope `US Sectors`): holdout hit-rate delta 23.80%; bootstrap CI [0.141285, 0.335421]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `global_positive_score_ge_1_2` (positive, 52w, scope `global`): holdout hit-rate delta 16.02%; bootstrap CI [-0.002927, 0.307105]; needs more testing.
  - Rejection/status reasons: `bootstrap_interval_crosses_zero`
- `us_sectors_positive_score_ge_1_2` (positive, 52w, scope `US Sectors`): holdout hit-rate delta 16.02%; bootstrap CI [-0.002927, 0.307105]; needs more testing.
  - Rejection/status reasons: `bootstrap_interval_crosses_zero`
- `global_positive_score_ge_1_0` (positive, 52w, scope `global`): holdout hit-rate delta 15.79%; bootstrap CI [0.04129, 0.272376]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_1_0` (positive, 52w, scope `US Sectors`): holdout hit-rate delta 15.79%; bootstrap CI [0.04129, 0.272376]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `global_positive_score_ge_0_8` (positive, 26w, scope `global`): holdout hit-rate delta 15.03%; bootstrap CI [0.070086, 0.235772]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`
- `us_sectors_positive_score_ge_0_8` (positive, 26w, scope `US Sectors`): holdout hit-rate delta 15.03%; bootstrap CI [0.070086, 0.235772]; research_candidate.
  - Rejection/status reasons: `separate_live_promotion_ticket_required`

## Sector/Class Overrides

- `us_sectors_positive_score_ge_1_0` for `US Sectors`: weight multiplier `1.238`; promotion requires `separate_reviewed_live_promotion_ticket`.
- `us_sectors_positive_score_ge_1_2` for `US Sectors`: weight multiplier `1.25`; promotion requires `separate_reviewed_live_promotion_ticket`.
- `us_sectors_positive_score_ge_0_8` for `US Sectors`: weight multiplier `1.1284`; promotion requires `separate_reviewed_live_promotion_ticket`.
- `us_sectors_positive_score_ge_1_0` for `US Sectors`: weight multiplier `1.1579`; promotion requires `separate_reviewed_live_promotion_ticket`.

## Safety

- Expanded calibration is artifact-only and read-only in the dashboard.
- Sector/class weights are research candidates, not active live methodology parameters.
- Live promotion requires a separate reviewed ticket with activation flag, frozen config, rollback plan, and evidence-gate approval.
