# Calibration Baseline Report

Ticket: B-163.8

This is research-only baseline and calibration-candidate evidence. It does not change live scoring, alter recommendations, or allow live promotion.

## Provenance

- Baseline config hash: `70d9b9ba8879ed98142d330c3611312aeab956850115484a2a16533c6cffb69f`
- Label rows: 4968
- Summary rows: 24
- Split status: `ready`
- History window: `accepted_short_history` (7.92 years used; minimum accepted 5 years; effective calibration 5 years).
- Calibrated rerun gate: `rejected_final_holdout_no_data`

## Overall Baseline Hit Rates

- Positive momentum hit rate (4w): 37.10% (617 successes / 1663 available signals).
- Negative momentum hit rate (4w): 66.42% (2957 successes / 4452 available signals).
- Positive momentum hit rate (13w): 36.44% (591 successes / 1622 available signals).
- Negative momentum hit rate (13w): 73.89% (3209 successes / 4343 available signals).
- Positive momentum hit rate (26w): 37.83% (594 successes / 1570 available signals).
- Negative momentum hit rate (26w): 79.64% (3344 successes / 4199 available signals).
- Positive momentum hit rate (52w): 36.19% (532 successes / 1470 available signals).
- Negative momentum hit rate (52w): 84.31% (3310 successes / 3926 available signals).

## Calibration Candidate Search

- Selected by calibration window only: `positive_score_ge_1_0` (rejected_final_holdout_no_data; do not promote).
- Final holdout evidence was not evaluated for the selected candidate.
- Final holdout is evaluated only after calibration-window selection; no candidate is live-promoted.

## Safety

- Candidate search is research-only and does not update live methodology parameters.
- Live promotion remains pending a future reviewed ticket with an activation flag and rollback plan.
- Dashboard surfacing remains artifact-only and read-only.
