# B-164 Expanded Statistical Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a research-only statistical calibration framework that uses roughly five years for calibration, two to three later years for holdout validation, and sector/class-specific rule weights when evidence is strong enough.

**Architecture:** Add a B-164 layer beside the existing B-163 artifacts instead of changing live scoring. The runner will produce expanded calibration artifacts from point-in-time labels, fixed train/holdout split profiles, candidate rule grids, sector-specific evidence, bootstrap confidence intervals, and fail-closed promotion labels. The dashboard only reads hash-verified artifacts and does not run calibration on page load.

**Tech Stack:** Python, pandas, numpy, pytest, Streamlit artifact rendering, existing local artifact hashing.

**Execution Status:** Implemented in `backlog-stepwise-qa` as research-only B-164 artifacts. Live promotion remains blocked pending a separate reviewed promotion ticket.

---

### Task 1: Backlog Contract And Guard Rails

**Files:**
- Modify: `docs/BACKLOG.md`
- Create: `docs/superpowers/plans/2026-05-24-b164-expanded-statistical-calibration.md`

- [ ] **Step 1: Add B-164 backlog entry**

Add a new backlog item after B-163:

```markdown
### B-164 - Expanded statistical calibration and sector-specific rule weights - PLANNED
**Goal:** use a five-year calibration window and a two-to-three-year holdout window to calibrate methodology thresholds, filters, and sector/class-specific rule weights.
**Scope:** research-only. No live scoring, alerting, recommendation, state-machine, broker, or dashboard decision text changes.
**Outputs:** `docs/calibration_expanded_report.md`, `docs/calibration_expanded_candidates.csv`, `docs/calibration_sector_overrides.csv`, `docs/calibration_expanded_metadata.json`, and dashboard read-only surfacing.
**Safety:** live promotion requires a separate reviewed ticket with activation flag, frozen config, rollback plan, and evidence gate approval.
```

- [ ] **Step 2: Run docs grep**

Run:

```powershell
rg -n "B-164|calibration_expanded|sector-specific" docs/BACKLOG.md docs/superpowers/plans/2026-05-24-b164-expanded-statistical-calibration.md
```

Expected: B-164 entry and this plan are discoverable.

### Task 2: Fixed Train/Holdout Split Profile

**Files:**
- Modify: `src/backtest.py`
- Test: `tests/test_backtest.py`

- [ ] **Step 1: Write failing split-profile test**

Add this test to `tests/test_backtest.py`:

```python
def test_fixed_train_holdout_split_uses_five_year_train_and_remaining_holdout():
    dates = pd.bdate_range("2018-06-22", "2026-05-22")

    split = backtest.fixed_train_holdout_calibration_split(
        dates,
        train_years=5,
        minimum_holdout_years=2,
        maximum_holdout_years=3,
    )

    assert split["status"] == "ready"
    assert split["profile"] == "fixed_5y_train_2y_to_3y_holdout"
    assert split["train"]["start"] == "2018-06-22"
    assert split["train"]["end"] < split["holdout"]["start"]
    assert split["holdout"]["years"] >= 2.0
    assert split["holdout"]["years"] <= 3.05
    assert split["no_lookahead_verified"] is True
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_fixed_train_holdout_split_uses_five_year_train_and_remaining_holdout -q
```

Expected: fail because `fixed_train_holdout_calibration_split()` does not exist.

- [ ] **Step 3: Implement split helper**

Add `fixed_train_holdout_calibration_split()` to `src/backtest.py`. It should:

```python
def fixed_train_holdout_calibration_split(
    dates,
    *,
    train_years: int = 5,
    minimum_holdout_years: int = 2,
    maximum_holdout_years: int = 3,
) -> dict:
    index = _clean_datetime_index("dates", dates)
    train_years = _positive_int("train_years", train_years)
    minimum_holdout_years = _positive_int("minimum_holdout_years", minimum_holdout_years)
    maximum_holdout_years = _positive_int("maximum_holdout_years", maximum_holdout_years)
    if minimum_holdout_years > maximum_holdout_years:
        raise ValueError("minimum_holdout_years cannot exceed maximum_holdout_years")
    train_start = pd.Timestamp(index[0])
    train_end_target = train_start + pd.DateOffset(years=train_years)
    holdout_start = _first_on_or_after(index, train_end_target)
    if holdout_start is None:
        raise ValueError("not enough history to build holdout window")
    holdout_end_target = holdout_start + pd.DateOffset(years=maximum_holdout_years)
    holdout_dates = index[(index >= holdout_start) & (index < holdout_end_target)]
    if holdout_dates.empty:
        raise ValueError("holdout window cannot be built from available dates")
    holdout_end = pd.Timestamp(holdout_dates[-1])
    holdout_years = ((holdout_end - pd.Timestamp(holdout_start)).days + 1) / 365.25
    if holdout_years < minimum_holdout_years:
        return {
            "status": "insufficient_holdout",
            "profile": "fixed_5y_train_2y_to_3y_holdout",
            "reason": "holdout window is shorter than the configured minimum",
            "holdout_years": round(holdout_years, 2),
        }
    return {
        "status": "ready",
        "profile": "fixed_5y_train_2y_to_3y_holdout",
        "train": {"start": _date_string(train_start), "end": _date_string(_last_before(index, holdout_start))},
        "holdout": {"start": _date_string(holdout_start), "end": _date_string(holdout_end), "years": round(holdout_years, 2)},
        "no_lookahead_verified": True,
    }
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_backtest.py::test_fixed_train_holdout_split_uses_five_year_train_and_remaining_holdout -q
```

Expected: pass.

### Task 3: Expanded Candidate Rule Model

**Files:**
- Create: `src/calibration_research.py`
- Test: `tests/test_calibration_research.py`

- [ ] **Step 1: Write failing candidate-grid tests**

Create `tests/test_calibration_research.py`:

```python
from __future__ import annotations

from src.calibration_research import expanded_candidate_grid


def test_expanded_candidate_grid_contains_global_and_sector_specific_rules():
    rules = expanded_candidate_grid()
    ids = {rule["candidate_id"] for rule in rules}

    assert "global_positive_score_ge_1_0" in ids
    assert "us_sectors_positive_score_ge_1_0_rel_strength_ge_0_0" in ids
    assert "us_sectors_negative_score_le_minus_0_5" in ids
    assert all(rule["research_only"] is True for rule in rules)
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py::test_expanded_candidate_grid_contains_global_and_sector_specific_rules -q
```

Expected: fail because `src/calibration_research.py` does not exist.

- [ ] **Step 3: Implement candidate grid**

Create `src/calibration_research.py` with:

```python
from __future__ import annotations


def expanded_candidate_grid() -> list[dict]:
    score_thresholds = [0.8, 1.0, 1.2]
    negative_thresholds = [0.0, -0.5, -1.0]
    classes = ["global", "US Sectors", "US Defensive", "US Growth"]
    rules: list[dict] = []
    for scope in classes:
        safe_scope = scope.lower().replace(" ", "_")
        for threshold in score_thresholds:
            rules.append(
                {
                    "candidate_id": f"{safe_scope}_positive_score_ge_{str(threshold).replace('.', '_')}",
                    "scope": scope,
                    "direction": "positive",
                    "positive_min_s_score_after_veto": threshold,
                    "relative_strength_min": None,
                    "research_only": True,
                }
            )
            rules.append(
                {
                    "candidate_id": f"{safe_scope}_positive_score_ge_{str(threshold).replace('.', '_')}_rel_strength_ge_0_0",
                    "scope": scope,
                    "direction": "positive",
                    "positive_min_s_score_after_veto": threshold,
                    "relative_strength_min": 0.0,
                    "research_only": True,
                }
            )
        for threshold in negative_thresholds:
            rules.append(
                {
                    "candidate_id": f"{safe_scope}_negative_score_le_{str(threshold).replace('-', 'minus_').replace('.', '_')}",
                    "scope": scope,
                    "direction": "negative",
                    "negative_max_s_score_after_veto": threshold,
                    "research_only": True,
                }
            )
    return rules
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py -q
```

Expected: pass.

### Task 4: Sector/Class-Specific Evidence Aggregation

**Files:**
- Modify: `src/calibration_research.py`
- Test: `tests/test_calibration_research.py`

- [ ] **Step 1: Write failing sector evidence test**

Append:

```python
import pandas as pd

from src.calibration_research import sector_override_candidates


def test_sector_override_candidates_require_sample_size_and_holdout_improvement():
    rows = pd.DataFrame(
        [
            {
                "candidate_id": "tech_rule",
                "scope": "US Sectors",
                "sector": "Technology",
                "direction": "positive",
                "train_signal_count": 80,
                "holdout_signal_count": 30,
                "holdout_hit_rate_delta_vs_baseline": 0.12,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.01,
                "fold_stability_passed": True,
            },
            {
                "candidate_id": "thin_rule",
                "scope": "US Sectors",
                "sector": "Utilities",
                "direction": "positive",
                "train_signal_count": 10,
                "holdout_signal_count": 4,
                "holdout_hit_rate_delta_vs_baseline": 0.40,
                "holdout_negative_hit_rate_delta_vs_baseline": 0.0,
                "holdout_max_drawdown_delta_vs_baseline": 0.02,
                "fold_stability_passed": True,
            },
        ]
    )

    overrides = sector_override_candidates(
        rows,
        min_train_signals=40,
        min_holdout_signals=20,
        min_holdout_hit_rate_delta=0.05,
    )

    assert overrides["candidate_id"].tolist() == ["tech_rule"]
    assert overrides.loc[0, "sector_weight_multiplier"] > 1.0
    assert overrides.loc[0, "live_promotion_allowed"] is False
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py::test_sector_override_candidates_require_sample_size_and_holdout_improvement -q
```

Expected: fail because `sector_override_candidates()` does not exist.

- [ ] **Step 3: Implement sector override gate**

Add to `src/calibration_research.py`:

```python
def sector_override_candidates(
    rows,
    *,
    min_train_signals: int = 40,
    min_holdout_signals: int = 20,
    min_holdout_hit_rate_delta: float = 0.05,
):
    frame = rows.copy()
    mask = (
        (frame["train_signal_count"] >= min_train_signals)
        & (frame["holdout_signal_count"] >= min_holdout_signals)
        & (frame["holdout_hit_rate_delta_vs_baseline"] >= min_holdout_hit_rate_delta)
        & (frame["holdout_negative_hit_rate_delta_vs_baseline"] >= 0)
        & (frame["holdout_max_drawdown_delta_vs_baseline"] >= 0)
        & (frame["fold_stability_passed"].map(bool))
    )
    out = frame.loc[mask].copy()
    if out.empty:
        return out
    out["sector_weight_multiplier"] = (1.0 + out["holdout_hit_rate_delta_vs_baseline"].clip(0, 0.25)).round(4)
    out["promotion_label"] = "sector_candidate"
    out["live_promotion_allowed"] = False
    out["promotion_requires"] = "separate_reviewed_live_promotion_ticket"
    return out.reset_index(drop=True)
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py -q
```

Expected: pass.

### Task 5: Bootstrap Confidence And Stability Checks

**Files:**
- Modify: `src/calibration_research.py`
- Test: `tests/test_calibration_research.py`

- [ ] **Step 1: Write failing bootstrap test**

Append:

```python
from src.calibration_research import bootstrap_hit_rate_delta


def test_bootstrap_hit_rate_delta_is_deterministic_and_reports_interval():
    candidate_success = [1, 1, 1, 0, 1, 1, 0, 1]
    baseline_success = [1, 0, 1, 0, 0, 1, 0, 0]

    result = bootstrap_hit_rate_delta(
        candidate_success,
        baseline_success,
        samples=200,
        random_seed=7,
    )

    assert result["mean_delta"] > 0
    assert result["ci_low"] <= result["mean_delta"] <= result["ci_high"]
    assert result == bootstrap_hit_rate_delta(
        candidate_success,
        baseline_success,
        samples=200,
        random_seed=7,
    )
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py::test_bootstrap_hit_rate_delta_is_deterministic_and_reports_interval -q
```

Expected: fail because `bootstrap_hit_rate_delta()` does not exist.

- [ ] **Step 3: Implement deterministic bootstrap**

Add:

```python
import numpy as np


def bootstrap_hit_rate_delta(candidate_success, baseline_success, *, samples: int = 1000, random_seed: int = 42) -> dict:
    candidate = np.asarray(candidate_success, dtype=float)
    baseline = np.asarray(baseline_success, dtype=float)
    if len(candidate) != len(baseline):
        raise ValueError("candidate_success and baseline_success must have the same length")
    if len(candidate) == 0:
        return {"mean_delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "sample_count": 0}
    rng = np.random.default_rng(random_seed)
    deltas = []
    for _ in range(int(samples)):
        idx = rng.integers(0, len(candidate), len(candidate))
        deltas.append(float(candidate[idx].mean() - baseline[idx].mean()))
    return {
        "mean_delta": round(float(candidate.mean() - baseline.mean()), 6),
        "ci_low": round(float(np.percentile(deltas, 2.5)), 6),
        "ci_high": round(float(np.percentile(deltas, 97.5)), 6),
        "sample_count": int(len(candidate)),
    }
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py -q
```

Expected: pass.

### Task 6: Runner Integration And New Artifacts

**Files:**
- Modify: `scripts/run_backtest.py`
- Modify: `src/backtest.py`
- Modify: `src/calibration_research.py`
- Test: `tests/test_run_backtest_script.py`
- Create/regenerate: `docs/calibration_expanded_report.md`
- Create/regenerate: `docs/calibration_expanded_candidates.csv`
- Create/regenerate: `docs/calibration_sector_overrides.csv`
- Create/regenerate: `docs/calibration_expanded_metadata.json`

- [ ] **Step 1: Write failing artifact-writing test**

Add to `tests/test_run_backtest_script.py`:

```python
def test_write_artifacts_persists_expanded_calibration_artifacts(monkeypatch, tmp_path):
    expanded_report = tmp_path / "calibration_expanded_report.md"
    expanded_candidates = tmp_path / "calibration_expanded_candidates.csv"
    sector_overrides = tmp_path / "calibration_sector_overrides.csv"
    expanded_metadata = tmp_path / "calibration_expanded_metadata.json"

    monkeypatch.setattr(run_backtest, "CALIBRATION_EXPANDED_REPORT_PATH", expanded_report, raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_EXPANDED_CANDIDATES_PATH", expanded_candidates, raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_SECTOR_OVERRIDES_PATH", sector_overrides, raising=False)
    monkeypatch.setattr(run_backtest, "CALIBRATION_EXPANDED_METADATA_PATH", expanded_metadata, raising=False)

    run_backtest._write_expanded_calibration_artifacts(
        report="# Expanded Calibration Report\n",
        candidates=pd.DataFrame([{"candidate_id": "global_positive_score_ge_1_0"}]),
        sector_overrides=pd.DataFrame([{"candidate_id": "tech_rule", "sector": "Technology"}]),
        metadata={"ticket": "B-164", "live_promotion_allowed": False},
    )

    assert expanded_report.read_text(encoding="utf-8").startswith("# Expanded Calibration Report")
    assert pd.read_csv(expanded_candidates).loc[0, "candidate_id"] == "global_positive_score_ge_1_0"
    assert pd.read_csv(sector_overrides).loc[0, "sector"] == "Technology"
    metadata = json.loads(expanded_metadata.read_text(encoding="utf-8"))
    assert metadata["ticket"] == "B-164"
    assert metadata["live_promotion_allowed"] is False
    assert len(metadata["artifacts"]["candidates_sha256"]) == 64
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_write_artifacts_persists_expanded_calibration_artifacts -q
```

Expected: fail because expanded artifact paths/writer do not exist.

- [ ] **Step 3: Implement writer and metadata**

Add constants and `_write_expanded_calibration_artifacts()` to `scripts/run_backtest.py`. Use existing `_sha256_bytes()` and `_json_artifact_bytes()` patterns. Metadata must include:

```python
{
    "ticket": "B-164",
    "research_only": True,
    "live_promotion_allowed": False,
    "split_profile": "fixed_5y_train_2y_to_3y_holdout",
    "artifacts": {
        "report_sha256": "...",
        "candidates_sha256": "...",
        "sector_overrides_sha256": "...",
    },
}
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_run_backtest_script.py::test_write_artifacts_persists_expanded_calibration_artifacts -q
```

Expected: pass.

### Task 7: Candidate Evaluation Engine

**Files:**
- Modify: `src/calibration_research.py`
- Test: `tests/test_calibration_research.py`

- [ ] **Step 1: Write failing evaluator test**

Add:

```python
from src.calibration_research import evaluate_expanded_candidates


def test_evaluate_expanded_candidates_returns_fail_closed_holdout_labels():
    labels = pd.DataFrame(
        {
            "rebalance_date": pd.to_datetime(["2019-01-04", "2024-01-05"]),
            "class": ["US Sectors", "US Sectors"],
            "ticker": ["XLK", "XLK"],
            "positive_signal": [True, True],
            "negative_signal": [False, False],
            "S_score_after_veto": [1.1, 1.1],
            "rs_ratio_z": [0.2, 0.2],
            "label_available_13w": [True, True],
            "positive_success_13w": [True, True],
            "negative_success_13w": [False, False],
            "forward_return_13w": [0.05, 0.04],
            "forward_excess_return_13w": [0.03, 0.02],
            "post_entry_drawdown_13w": [-0.01, -0.01],
        }
    )
    split = {
        "status": "ready",
        "train": {"start": "2018-06-22", "end": "2023-06-21"},
        "holdout": {"start": "2023-06-22", "end": "2026-05-22", "years": 2.92},
    }

    result = evaluate_expanded_candidates(
        labels,
        split,
        candidate_rules=[
            {
                "candidate_id": "global_positive_score_ge_1_0",
                "scope": "global",
                "direction": "positive",
                "positive_min_s_score_after_veto": 1.0,
                "research_only": True,
            }
        ],
        horizons_weeks=(13,),
        min_train_signals=1,
        min_holdout_signals=1,
    )

    assert result.loc[0, "candidate_id"] == "global_positive_score_ge_1_0"
    assert result.loc[0, "holdout_evaluated"] is True
    assert result.loc[0, "live_promotion_allowed"] is False
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_calibration_research.py::test_evaluate_expanded_candidates_returns_fail_closed_holdout_labels -q
```

Expected: fail because evaluator does not exist.

- [ ] **Step 3: Implement evaluator**

Implement `evaluate_expanded_candidates()` using the same no-lookahead principles as B-163:
- Train window uses labels whose rebalance date and label maturity are inside the train window.
- Holdout window uses labels whose rebalance date and label maturity are inside the holdout window.
- Candidate row includes train and holdout signal counts, hit-rate deltas versus baseline, bootstrap interval, fold stability flag, `promotion_label`, and `live_promotion_allowed=False`.
- Sector/class rules filter labels by `class` or sector column before scoring.

- [ ] **Step 4: Run evaluator tests**

Run:

```powershell
python -m pytest tests/test_calibration_research.py -q
```

Expected: pass.

### Task 8: Dashboard Read-Only Surfacing

**Files:**
- Modify: `app.py`
- Modify: `src/calibration_dashboard.py`
- Test: `tests/test_calibration_dashboard.py`
- Test: `tests/test_calibration_dashboard_static.py`

- [ ] **Step 1: Write failing static dashboard test**

Add assertions that `app.py` defines and renders:

```python
assert 'CALIBRATION_EXPANDED_REPORT_PATH = APP_ROOT / "docs" / "calibration_expanded_report.md"' in app_source
assert 'CALIBRATION_SECTOR_OVERRIDES_PATH = APP_ROOT / "docs" / "calibration_sector_overrides.csv"' in app_source
assert "Expanded calibration" in app_source
assert "sector-specific" in app_source
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_calibration_dashboard_static.py::test_app_surfaces_calibration_artifacts_without_running_calibration -q
```

Expected: fail until dashboard constants/UI are added.

- [ ] **Step 3: Implement dashboard artifact rows**

Extend the Calibration Lab with hash-verified expanded artifacts:
- Expanded calibration report.
- Expanded candidates table.
- Sector override table.
- Expanded metadata JSON.

Keep all text read-only and research-only.

- [ ] **Step 4: Run dashboard tests**

Run:

```powershell
python -m pytest tests/test_calibration_dashboard.py tests/test_calibration_dashboard_static.py -q
```

Expected: pass.

### Task 9: Report Generation And Manual Artifact Run

**Files:**
- Modify: `scripts/run_backtest.py`
- Regenerate: `docs/calibration_expanded_report.md`
- Regenerate: `docs/calibration_expanded_candidates.csv`
- Regenerate: `docs/calibration_sector_overrides.csv`
- Regenerate: `docs/calibration_expanded_metadata.json`
- Modify: `README.md`
- Modify: `src/component_docs.py`

- [ ] **Step 1: Add report formatter**

Add `_format_expanded_calibration_report()` to `scripts/run_backtest.py`. It must report:
- Split profile and dates.
- Candidate counts.
- Global candidates.
- Sector-specific override candidates.
- Holdout hit-rate deltas.
- Bootstrap confidence intervals.
- Reasons for rejection.
- `live_promotion_allowed=false`.

- [ ] **Step 2: Generate artifacts**

Run:

```powershell
python scripts/run_backtest.py
```

Expected: existing B-163 artifacts plus new B-164 expanded artifacts are written.

- [ ] **Step 3: Inspect generated outcome**

Run:

```powershell
Get-Content docs/calibration_expanded_report.md -TotalCount 80
Get-Content docs/calibration_expanded_metadata.json
Get-Content docs/calibration_sector_overrides.csv -TotalCount 20
```

Expected: artifacts explicitly say research-only and fail-closed.

### Task 10: Review, QA, Commit, Push, Deploy

**Files:**
- No new files beyond B-164 implementation files.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_calibration_research.py tests/test_backtest.py tests/test_run_backtest_script.py tests/test_calibration_dashboard.py tests/test_calibration_dashboard_static.py -q
```

Expected: pass.

- [ ] **Step 2: Run full local verification**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected: full pytest passes, compileall passes, diff check exits 0 with only existing CRLF warnings.

- [ ] **Step 3: Request code review**

Ask a reviewer to inspect:
- Lookahead leakage.
- Holdout split correctness.
- Bootstrap/stability math.
- Sector-specific override gating.
- Artifact hash consistency.
- Dashboard read-only behavior.

- [ ] **Step 4: Commit and push**

Run:

```powershell
git status --short --branch
git add README.md app.py docs/BACKLOG.md docs/calibration_expanded_report.md docs/calibration_expanded_candidates.csv docs/calibration_sector_overrides.csv docs/calibration_expanded_metadata.json docs/superpowers/plans/2026-05-24-b164-expanded-statistical-calibration.md scripts/run_backtest.py src/backtest.py src/calibration_research.py src/component_docs.py tests/test_backtest.py tests/test_calibration_research.py tests/test_run_backtest_script.py tests/test_calibration_dashboard.py tests/test_calibration_dashboard_static.py
git commit -m "feat: add expanded statistical calibration"
git push origin backlog-stepwise-qa
```

Expected: branch pushes cleanly.

- [ ] **Step 5: Verify GitHub and Pi**

Run:

```powershell
gh run list --branch backlog-stepwise-qa --limit 5
gh run watch <RUN_ID> --exit-status
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=10 ahad@10.100.102.18 "hostname; whoami; cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git rev-parse HEAD && systemctl is-active sector-dashboard && curl -s -o /dev/null -w '%{http_code}' --max-time 12 'http://127.0.0.1:8501/?ticker=XLK'"
curl.exe --ssl-no-revoke -I --max-time 20 https://sentimentdashboard.ahaddashboards.uk/
```

Expected:
- GitHub deploy succeeds.
- Pi SHA matches the pushed commit.
- `sector-dashboard` is active.
- Pi local dashboard returns `200`.
- Public URL returns Cloudflare Access redirect or HTTP success.

---

## Execution Notes

- Do not promote any B-164 candidate into live scoring.
- Do not change alerts, recommendations, broker behavior, state-machine behavior, or dashboard decision text.
- Sector-specific overrides are research artifacts only.
- If sector evidence is thin, write `do not promote` or `needs more testing`.
- If a candidate is strong globally but weak for a sector, prefer global fallback for that sector.
- If a sector candidate is strong only in one fold/year/regime, reject it as unstable.
