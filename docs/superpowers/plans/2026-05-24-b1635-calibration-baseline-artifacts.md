# B-163.5 Calibration Baseline Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate deterministic research-only baseline calibration artifacts for the dashboard Calibration Lab.

**Architecture:** Keep calibration evidence generation inside the manual backtest runner, using existing point-in-time label construction and `calibration_label_metrics()`. The runner writes summary CSV, metadata JSON, and Markdown report artifacts under `docs/`; the dashboard only reads those files and no live scoring, alerts, recommendations, provider behavior, or promotion gates change.

**Tech Stack:** Python, pandas, existing `src.backtest` calibration helpers, `scripts/run_backtest.py`, pytest.

---

### Task 1: Artifact Paths And Writer Contract

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `tests/test_run_backtest_script.py`

- [ ] **Step 1: Write failing tests**

Add assertions that the runner exposes:
`CALIBRATION_REPORT_PATH`, `CALIBRATION_SUMMARY_PATH`, and `CALIBRATION_METADATA_PATH`.
Add a writer test that passes a small calibration summary and metadata payload into `_write_artifacts()` and verifies all three files are written, hashes are recorded in `backtest_metadata.json`, and the calibration metadata records report/summary hashes.

- [ ] **Step 2: Run tests to verify failure**

Run:
`python -m pytest tests/test_run_backtest_script.py::test_run_backtest_artifact_paths_are_repo_root_anchored tests/test_run_backtest_script.py::test_write_artifacts_persists_calibration_artifacts_and_metadata -q`

Expected: FAIL because the new paths and writer parameters do not exist yet.

- [ ] **Step 3: Implement minimal writer support**

Add the three paths and optional `_write_artifacts()` parameters for `calibration_report`, `calibration_summary`, and `calibration_metadata`. Serialize summary with `to_csv(index=False)`, report as UTF-8 Markdown, metadata as sorted JSON, and stage all writes atomically with existing artifact staging.

- [ ] **Step 4: Run tests to verify pass**

Run the same focused command and expect PASS.

### Task 2: Baseline Summary Builder

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `tests/test_run_backtest_script.py`

- [ ] **Step 1: Write failing tests**

Add a test for `_build_calibration_baseline_artifacts()` that stubs the label builder and metrics aggregator. Verify the returned summary contains both overall and class rows, the report includes positive and negative momentum hit rates, and metadata records B-163/B-163.5, horizons, row counts, split status, and a research-only safety flag.

- [ ] **Step 2: Run test to verify failure**

Run:
`python -m pytest tests/test_run_backtest_script.py::test_build_calibration_baseline_artifacts_summarizes_directional_metrics -q`

Expected: FAIL because the helper does not exist yet.

- [ ] **Step 3: Implement minimal builder**

Build labels with `backtest.build_calibration_feature_labels()`, aggregate overall and class metrics with `backtest.calibration_label_metrics()`, normalize rows with a `scope` column, render a compact Markdown report, and return `(summary, report, metadata)`.

- [ ] **Step 4: Run test to verify pass**

Run the same focused command and expect PASS.

### Task 3: Runner Integration And Docs

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `tests/test_run_backtest_script.py`
- Modify: `docs/BACKLOG.md`
- Modify: `README.md`

- [ ] **Step 1: Write/extend failing integration test**

Extend the main manual-backtest test to verify the new calibration summary/report/metadata files are written and referenced from `backtest_metadata.json`.

- [ ] **Step 2: Run focused test to verify failure**

Run:
`python -m pytest tests/test_run_backtest_script.py::test_run_backtest_main_writes_reports_equity_states_metadata_and_baseline_config -q`

Expected: FAIL until main calls the builder and writer.

- [ ] **Step 3: Wire the runner**

Call `_build_calibration_baseline_artifacts()` after methodology targets and prices are available. Pass its outputs into `_write_artifacts()`. Update backlog/README to say B-163.5 now generates baseline calibration artifacts only.

- [ ] **Step 4: Verify**

Run focused QA, compile, `git diff --check`, full pytest, then commit, push, and verify GitHub Actions plus Pi service.
