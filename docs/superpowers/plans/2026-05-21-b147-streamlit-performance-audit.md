# B-147 Streamlit Performance Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log which dashboard sections rerun, and how long they take, so theme-toggle and other visual-only reruns can be identified from structured logs.

**Architecture:** Add a pure `src.performance_audit` module that snapshots relevant Streamlit session-state keys, classifies reruns as `initial`, `visual_only`, `interactive`, or `unchanged`, and records named section durations through a small context manager. Wire `app.py` to time the data/scoring pipeline and major render sections, then emit one `dashboard_performance_audit` structured log event after the page composes. This ticket measures before optimizing; it does not cache stateful scoring or move Streamlit controls.

**Tech Stack:** Python dataclasses, context managers, Streamlit session state, existing structured JSON logging, pytest static and unit tests.

---

### Task 1: Pure Audit Contract

**Files:**
- Create: `tests/test_performance_audit.py`
- Create: `src/performance_audit.py`

- [x] **Step 1: Write failing unit tests**

Add tests for visual snapshot classification and deterministic section timing:

```python
def test_classify_visual_only_rerun_reports_changed_keys():
    previous = performance_audit.session_snapshot({"theme": "dark", "klass": "US Sectors"})
    current = performance_audit.session_snapshot({"theme": "light", "klass": "US Sectors"})

    result = performance_audit.classify_rerun(previous, current)

    assert result.kind == "visual_only"
    assert result.changed_keys == ("theme",)
```

```python
def test_dashboard_performance_audit_records_section_durations():
    ticks = iter([10.0, 10.25, 11.0, 12.5])
    audit = performance_audit.DashboardPerformanceAudit(timer=lambda: next(ticks))

    with audit.section("load_data"):
        pass
    with audit.section("render_header"):
        pass

    assert audit.durations_ms == {"load_data": 250.0, "render_header": 1500.0}
```

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_performance_audit.py -q
```

Expected: FAIL because `src.performance_audit` does not exist yet.

Observed: FAIL during collection because `src.performance_audit` did not exist yet.

- [x] **Step 3: Implement pure audit helpers**

Create `src/performance_audit.py` with:

- `VISUAL_STATE_KEYS = ("theme", "bluf_mode", "view_density", "sparkline_style", "color_palette")`
- `session_snapshot(session_state, keys=...) -> tuple[tuple[str, str], ...]`
- `classify_rerun(previous, current) -> RerunClassification`
- `DashboardPerformanceAudit.section(name)` context manager

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_performance_audit.py -q
```

Expected: PASS.

Observed with app static tests included after implementation: `python -m pytest tests/test_performance_audit.py tests/test_performance_audit_app_static.py -q` -> `7 passed in 0.12s`.

### Task 2: Dashboard Logging Wiring

**Files:**
- Create: `tests/test_performance_audit_app_static.py`
- Modify: `app.py`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b147-streamlit-performance-audit.md`

- [x] **Step 1: Write failing static app tests**

Require `app.py` to import `DashboardPerformanceAudit`, `classify_rerun`, and `session_snapshot`; create one `PERF_AUDIT`; wrap `load_data`, `compute_signals`, and major render sections; log `dashboard_performance_audit`; and store `performance_last_snapshot` after logging.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_performance_audit_app_static.py -q
```

Expected: FAIL because app wiring does not exist yet.

Observed: same RED focused run failed before app wiring because the helper module was still missing.

- [x] **Step 3: Wire app timings and structured log event**

In `app.py`, instantiate `PERF_AUDIT` after preferences initialize, compute `_PERF_RERUN = classify_rerun(st.session_state.get("performance_last_snapshot"), _PERF_SNAPSHOT)`, wrap data/scoring/render sections with `PERF_AUDIT.section(...)`, then call:

```python
log_event(
    APP_LOGGER,
    "dashboard_performance_audit",
    rerun_kind=_PERF_RERUN.kind,
    changed_keys=_PERF_RERUN.changed_keys,
    sections_ms=PERF_AUDIT.durations_ms,
    provider=ohlcv_result.provider,
    scored_count=len(scored),
)
st.session_state.performance_last_snapshot = _PERF_SNAPSHOT
```

- [x] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_performance_audit.py tests/test_performance_audit_app_static.py tests/test_structured_logging_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:

- Focused review found two audit-correctness issues: the stored snapshot was captured before render-time session mutations, and the tracked key list missed interactive widgets. Regression tests were added before fixing both.
- `python -m pytest tests/test_performance_audit.py tests/test_performance_audit_app_static.py -q` -> `9 passed in 0.18s`
- `python -m pytest tests/test_performance_audit.py tests/test_performance_audit_app_static.py tests/test_structured_logging_app_static.py tests/test_header_controls_static.py tests/test_view_preferences_static.py tests/test_backtest_dashboard_static.py tests/test_comparison_view_app_static.py tests/test_custom_universe_app_static.py tests/test_run_debrief_dashboard_static.py tests/test_sector_spaghetti_app_static.py -q` -> `27 passed in 0.21s`
- `python -m pytest -q` -> `314 passed in 21.17s`
- `python -m compileall app.py src scripts` -> exit 0
- `git diff --check` -> exit 0

- [x] **Step 5: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: add streamlit performance audit`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Observed:

- Re-review: no blocking issues after the snapshot/key coverage fixes; residual risk is no browser-rerun test and stringified upload widget values may be noisy.
- Local commit: `381ca42 feat: add streamlit performance audit`
- GitHub branch: `backlog-stepwise-qa` at `381ca42289f814ce8de09d0ddffe59ffe1469f36`
- Pi pull: fast-forwarded `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION` to `381ca42`
- Pi focused verification: `./.venv/bin/python -m pytest tests/test_performance_audit.py tests/test_performance_audit_app_static.py -q` -> `9 passed in 0.05s`
- Pi full verification: `./.venv/bin/python -m pytest -q` -> `314 passed in 5.02s`
- Pi service smoke: `poll_1 active=active http=200`

### Follow-up: Visual-only compute reuse

After B-025 added local preference profiles and B-147 audit logs identified visual-only reruns, the dashboard gained a guarded reuse path:

- `should_reuse_dashboard_compute()` returns true only for `visual_only` classifications with a complete session snapshot that is no older than the one-hour market-data cache TTL.
- Local preference-profile control keys are classified as visual-only because they affect display preferences and local profile UI messages only.
- The reusable dashboard snapshot includes `ohlcv_result`, `ohlcv`, `fred_data`, `regime`, `scored`, and `created_at`.
- Header refresh/theme controls use Streamlit callbacks so cache clearing and theme mutation happen before the compute gate.
- Visual-only reuse skips provider/FRED loading, indicator/flow/scoring work, `apply_state_machine()`, and run-journal recording; it still emits a `dashboard_performance_audit` event with `reused_compute_snapshot=True`.
- Transition rows are refreshed as a small read-only state-file read so cross-session state changes remain visible.
- Fresh initial runs, stale or incomplete snapshots, and interactive/data-affecting controls keep the normal compute path.
