# Dashboard Signals Report Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the dashboard signals PDF into a detailed analyst-style XLE methodology report.

**Architecture:** Keep the report generator self-contained. Add typed report rows for signal detail, calculation gates, and score contributions, then render those rows into additional PDF pages using Pillow.

**Tech Stack:** Python, pandas, Pillow, pytest, cached DuckDB OHLCV data through existing `src.*` modules.

---

### Task 1: Add Tests For Detailed Report Data

**Files:**
- Modify: `tests/test_dashboard_signals_report.py`
- Modify later: `scripts/generate_dashboard_signals_report.py`

- [ ] Add fixture fields for `faber`, `antonacci`, `rs_ratio`, `rs_momentum`, `obv_slope`, `mfi14`, `rvol`, `dist_days_25`, `obv_divergence`, `dark_pool_pct`, `si_delta_15d`, `thirteen_f_q`, `top_n_target`, `s_score_after_veto`, `cycle_tilt`, and `ma30w_slope_5w`.
- [ ] Add `test_signal_detail_rows_include_formulas_values_and_horizons`.
- [ ] Add `test_xle_calculation_rows_show_current_value_threshold_and_explanation`.
- [ ] Add `test_score_contribution_rows_sum_to_fixture_s_score`.
- [ ] Run `python -m pytest tests/test_dashboard_signals_report.py -q` and verify the new tests fail because the helper functions and fields do not exist yet.

### Task 2: Implement Detailed Report Data Helpers

**Files:**
- Modify: `scripts/generate_dashboard_signals_report.py`

- [ ] Add dataclasses `SignalDetailRow`, `CalculationRow`, and `ScoreContributionRow`.
- [ ] Extend `XleSnapshot` with the detail fields used by the tests.
- [ ] Add `build_signal_detail_rows(snapshot)`.
- [ ] Add `build_xle_calculation_rows(snapshot)`.
- [ ] Add `build_score_contribution_rows(snapshot)`.
- [ ] Update `_snapshot_from_cache()` and `_fallback_inputs()` to populate the new fields.
- [ ] Run `python -m pytest tests/test_dashboard_signals_report.py -q` and verify the tests pass.

### Task 3: Render Expanded PDF Pages

**Files:**
- Modify: `scripts/generate_dashboard_signals_report.py`
- Update: `docs/dashboard_signals_and_xle_stage2_report.pdf`

- [ ] Add table and bar-chart drawing helpers for dense report pages.
- [ ] Add pages for signal deep dive, XLE calculation details, score contribution math, and flow component analysis.
- [ ] Keep the existing overview, checklist, and visuals, but make them more numeric.
- [ ] Increase the PDF renderer test size expectation so it catches accidental regression to a short PDF.
- [ ] Run `python scripts/generate_dashboard_signals_report.py`.
- [ ] Verify the PDF starts with `%PDF` and has a materially larger file size than the original 382 KB artifact.

### Task 4: Final QA

**Files:**
- All changed files

- [ ] Run `python -m pytest tests/test_dashboard_signals_report.py -q`.
- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall app.py src scripts`.
- [ ] Run `git diff --check`.
- [ ] Review `git status --short --branch` and report all changed files.
