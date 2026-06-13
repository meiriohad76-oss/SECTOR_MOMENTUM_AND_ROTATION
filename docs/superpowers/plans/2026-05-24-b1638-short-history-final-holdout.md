# B-163.8 Short-History Final Holdout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete B-163 by accepting the current historical coverage when it meets a 5-year minimum and by evaluating the selected calibration candidate on the untouched final holdout.

**Architecture:** Keep all changes inside the research backtest pipeline. Split construction records whether the full 10-year target or the accepted shorter window was used. Candidate selection still uses only calibration/validation folds; final holdout metrics are added afterward and live promotion remains disabled.

**Tech Stack:** Python, pandas, pytest, Streamlit artifact rendering.

---

### Task 1: Failing Tests

**Files:**
- Modify: `tests/test_backtest.py`
- Modify: `tests/test_run_backtest_script.py`

- [ ] Add tests proving shortened history can be accepted only when it reaches the configured minimum.
- [ ] Add tests proving the selected candidate can be evaluated on the final holdout without using final holdout data for selection.
- [ ] Add tests proving candidate config records final holdout evidence but still has `live_promotion_allowed=false`.
- [ ] Run the targeted tests and confirm they fail before implementation.

### Task 2: Split And Holdout Implementation

**Files:**
- Modify: `src/backtest.py`
- Modify: `scripts/run_backtest.py`

- [ ] Add a `minimum_years` acceptance path to `walk_forward_calibration_splits()`.
- [ ] Add shortened-history metadata to `walk_forward_split_summary()`.
- [ ] Add final-holdout label filtering that requires horizon labels to mature inside the holdout.
- [ ] Add final-holdout evaluation for the calibration-selected candidate after validation gates pass.
- [ ] Keep `live_promotion_allowed=false` for every row and artifact.

### Task 3: Dashboard And Documentation

**Files:**
- Modify: `app.py`
- Modify: `docs/BACKLOG.md`
- Modify: `README.md`
- Regenerate: `docs/calibration_10y_report.md`
- Regenerate: `docs/calibration_10y_summary.csv`
- Regenerate: `docs/calibration_10y_candidates.csv`
- Regenerate: `docs/calibration_10y_candidate_config.json`
- Regenerate: `docs/calibration_10y_metadata.json`
- Regenerate: `docs/backtest_metadata.json`

- [ ] Show the accepted shortened-history metadata in the Calibration Lab.
- [ ] Update docs so B-163.8 is the current completed research-only slice.
- [ ] Regenerate artifacts with `python scripts/run_backtest.py`.

### Task 4: Verification And Deploy

**Files:**
- No additional source edits expected.

- [ ] Run targeted tests.
- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall app.py src scripts`.
- [ ] Run `git diff --check`.
- [ ] Commit and push.
- [ ] Verify GitHub deployment and Pi service/dashboard smoke.
