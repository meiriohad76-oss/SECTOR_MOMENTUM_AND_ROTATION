# B-163.7 Calibrated Rerun Gate Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a research-only calibrated rerun gate artifact that records whether a calibration candidate is ready for final holdout evaluation.

**Architecture:** Keep the gate fail-closed in the manual backtest runner. The runner writes `docs/calibration_10y_candidate_config.json`, hashes it into both backtest and calibration metadata, and the dashboard only reads the artifact. No live scoring, alerts, recommendations, provider behavior, broker behavior, or dashboard decision text changes.

**Tech Stack:** Python, pandas, JSON artifact metadata, Streamlit static rendering, pytest.

---

### Task 1: Candidate Config Writer

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `tests/test_run_backtest_script.py`

- [ ] **Step 1: Write failing tests**

Add assertions that `_write_artifacts()` persists `calibration_10y_candidate_config.json`, records `calibration_10y_candidate_config_sha256` in `docs/backtest_metadata.json`, and records `candidate_config_sha256` in `docs/calibration_10y_metadata.json`.

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_run_backtest_artifact_paths_are_repo_root_anchored tests/test_run_backtest_script.py::test_write_artifacts_persists_calibration_artifacts_and_metadata -q
```

Expected: failure because `CALIBRATION_CANDIDATE_CONFIG_PATH` and candidate-config writer metadata do not exist yet.

- [ ] **Step 3: Implement writer**

Add `CALIBRATION_CANDIDATE_CONFIG_PATH`, add an optional `calibration_candidate_config` parameter to `_write_artifacts()`, serialize it as sorted JSON, and hash-wire it into both metadata payloads.

- [ ] **Step 4: Verify pass**

Run the same pytest command. Expected: both tests pass.

### Task 2: Fail-Closed Gate Builder

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `tests/test_run_backtest_script.py`

- [ ] **Step 1: Write failing tests**

Add tests for `_build_calibration_candidate_config()`:
- when the split summary is not `ready`, it returns `config_status=skipped_insufficient_history`, `final_holdout_evaluated=False`, `live_promotion_allowed=False`, and no selected candidate;
- when a selected calibration candidate exists but final holdout is not evaluated in this slice, it returns `config_status=blocked_final_holdout_not_evaluated`, copies the candidate rule thresholds, and keeps promotion disabled.

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_build_calibration_candidate_config_skips_when_history_is_insufficient tests/test_run_backtest_script.py::test_build_calibration_candidate_config_records_selected_candidate_without_promotion -q
```

Expected: failure because `_build_calibration_candidate_config()` does not exist.

- [ ] **Step 3: Implement builder and runner wiring**

Add `_build_calibration_candidate_config()` and call it from `_build_calibration_baseline_artifacts()`. Return the candidate config as the fifth artifact from that helper, pass it through `main()`, and keep all statuses research-only.

- [ ] **Step 4: Verify pass**

Run the same pytest command plus the main manual-backtest script test. Expected: all selected tests pass and metadata records slice `B-163.7` for the candidate config only.

### Task 3: Dashboard Status Surfacing

**Files:**
- Modify: `src/calibration_dashboard.py`
- Modify: `app.py`
- Modify: `tests/test_calibration_dashboard.py`
- Modify: `tests/test_calibration_dashboard_static.py`

- [ ] **Step 1: Write failing tests**

Add candidate config to calibration status rows and static dashboard checks. Assert the dashboard reads and displays the artifact only after matching metadata hashes, without running calibration logic on page load.

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m pytest tests/test_calibration_dashboard.py tests/test_calibration_dashboard_static.py -q
```

Expected: failure because dashboard status rows do not include candidate config yet.

- [ ] **Step 3: Implement dashboard read-only surfacing**

Add the path constant, hash extraction, status row, and an expander that displays the JSON candidate config when verified.

- [ ] **Step 4: Verify pass**

Run the same pytest command. Expected: calibration dashboard tests pass.

### Task 4: Docs, Artifacts, And Verification

**Files:**
- Modify: `docs/BACKLOG.md`
- Modify: `README.md`
- Generate: `docs/calibration_10y_candidate_config.json`
- Regenerate: `docs/backtest_metadata.json`, `docs/calibration_10y_metadata.json`, `docs/calibration_10y_report.md`, `docs/calibration_10y_summary.csv`, `docs/calibration_10y_candidates.csv`

- [ ] **Step 1: Update docs**

Update B-163 latest slice and README to state B-163.7 adds a fail-closed calibrated rerun gate artifact.

- [ ] **Step 2: Regenerate artifacts**

Run:

```powershell
python scripts/run_backtest.py
```

Expected: artifacts regenerate and candidate config reports `skipped_insufficient_history` with `live_promotion_allowed=false`.

- [ ] **Step 3: Full local verification**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: pytest, compileall, and whitespace checks pass.

- [ ] **Step 4: Commit, push, and deploy verify**

Commit the change, push `backlog-stepwise-qa`, then verify GitHub/Pi deployment via SSH:

```powershell
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=10 ahad@10.100.102.18 "hostname; whoami; cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git rev-parse HEAD && systemctl is-active sector-dashboard && curl -s -o /dev/null -w '%{http_code}' --max-time 8 'http://127.0.0.1:8501/?ticker=XLK'"
```

Expected: `AHADPI5`, `ahad`, pushed commit SHA, `active`, and `200`.
