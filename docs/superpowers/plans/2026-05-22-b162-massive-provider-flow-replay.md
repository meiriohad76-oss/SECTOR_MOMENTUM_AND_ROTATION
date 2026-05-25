# B-162 Massive Provider-Flow Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backtest Massive trade-tape/block-trade threshold variants from stored as-of snapshots without changing live scoring or recommendations.

**Architecture:** Keep B-162 inside the opt-in `scripts/run_backtest.py --massive-variants` research path. Read snapshots through `src.provider_snapshots`, replay only records available on or before each rebalance date, keep missing snapshots neutral, and write coverage plus threshold sweep evidence into the Massive validation CSV/report.

**Tech Stack:** Python, pandas, pytest, SQLite provider snapshot store, existing manual backtest/report artifacts.

---

### Task 1: Provider-Flow Replay Tests

**Files:**
- Modify: `tests/test_run_backtest_script.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_massive_provider_flow_sweeps_replay_snapshots_as_of_rebalance(...):
    # Seed B-161 snapshots before and after a rebalance.
    # Assert the future snapshot is not used, missing snapshots are neutral,
    # threshold rows include coverage counts, and no live provider fetch is called.
```

```python
def test_massive_provider_report_includes_snapshot_coverage_and_sweep_metrics(...):
    # Build a tiny summary with provider_feature_sweep rows.
    # Assert the report includes snapshot coverage, missing-date handling,
    # active OOS counts, and research-only labels.
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_run_backtest_script.py -q`

Expected: FAIL because B-162 replay helpers/report columns do not exist yet.

### Task 2: Provider-Flow Replay Implementation

**Files:**
- Modify: `scripts/run_backtest.py`

- [ ] **Step 1: Implement replay helpers**

```python
def _build_massive_provider_flow_sweep_rows(*, snapshot_db_path, prices, target_weights, oos_start):
    # For every threshold and rebalance, use provider_snapshots.load_provider_snapshot_as_of().
    # Missing snapshots leave weights unchanged and are counted as neutral.
    # Available snapshots below threshold zero that ticker's baseline weight for research metrics only.
```

- [ ] **Step 2: Wire into `--massive-variants` only**

```python
massive_validation_summary = _build_massive_provider_validation_summary(
    enabled=True,
    oos_start=validation_oos_start,
    prices=prices[strategy_columns],
    target_weights=methodology_targets.target_weights,
    snapshot_db_path=args.provider_snapshot_db,
    precomputed_provider_rows=precomputed_provider_rows,
)
```

- [ ] **Step 3: Run tests to verify GREEN**

Run: `python -m pytest tests/test_run_backtest_script.py -q`

Expected: PASS.

### Task 3: Snapshot Capture Audit Metadata

**Files:**
- Modify: `tests/test_capture_massive_provider_snapshots_script.py`
- Modify: `scripts/capture_massive_provider_snapshots.py`

- [ ] **Step 1: Write the failing capture metadata test**

```python
assert xlk.payload["request"]["params"]["timestamp.gte"] == "2026-05-19"
assert xlk.payload["response"]["result_count"] == 1
```

- [ ] **Step 2: Add request/response audit metadata to saved payloads**

```python
payload={
    "source": "massive/v3/trades",
    "request": {...},
    "response": {"result_count": len(trades), "status": "captured"},
    "trades": trades,
}
```

- [ ] **Step 3: Run focused tests**

Run: `python -m pytest tests/test_capture_massive_provider_snapshots_script.py tests/test_provider_snapshots.py -q`

Expected: PASS.

### Task 4: Docs, QA, Review, Deploy

**Files:**
- Modify: `docs/BACKLOG.md`
- Modify generated artifacts if `python scripts/run_backtest.py --massive-variants` is run with available snapshots.

- [ ] **Step 1: Mark B-162 implemented/research-only**

```markdown
### B-162 · Massive provider-flow historical backtest variants — IMPLEMENTED
```

- [ ] **Step 2: Run local QA**

Run:
```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 3: Review, commit, push, deploy, and Pi QA**

Run:
```powershell
git add .
git commit -m "feat: add massive provider-flow replay variants"
git push origin backlog-stepwise-qa
ssh -i $env:USERPROFILE\.ssh\codex_ahadpi_ed25519 -o BatchMode=yes -o ConnectTimeout=8 ahad@10.100.102.18 "cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION && git pull --ff-only origin backlog-stepwise-qa && ./.venv/bin/python -m pytest -q && systemctl is-active sector-dashboard"
```

Expected: local and Pi QA pass, service remains active, and HTTP smoke returns 200.
