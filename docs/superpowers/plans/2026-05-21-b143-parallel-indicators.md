# B-143 Parallel Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parallelize per-ticker indicator computations while preserving the current dashboard output contract.

**Architecture:** Keep `src.indicators.compute_all_indicators()` as the public API and add a keyword-only `max_workers` escape hatch. Extract one pure per-ticker row helper, submit eligible tickers to a bounded `ThreadPoolExecutor` by default, and collect results in the original ticker order so scoring/ranking remains deterministic.

**Tech Stack:** Python standard-library `concurrent.futures`, pandas, pytest.

---

### Task 1: Parallel Indicator Contract

**Files:**
- Modify: `tests/test_indicators.py`

- [x] **Step 1: Write failing tests**

Add tests that call `compute_all_indicators(..., max_workers=3)`, verify eligible tickers are submitted to a patched executor, and verify output order remains the existing eligible ticker order.

- [x] **Step 2: Verify RED**

Run: `python -m pytest tests/test_indicators.py -q`

Expected: FAIL because `compute_all_indicators()` does not yet accept `max_workers`.

Evidence:

```powershell
python -m pytest tests/test_indicators.py -q
# 3 failed, 4 passed
```

### Task 2: Parallel Implementation

**Files:**
- Modify: `src/indicators.py`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b143-parallel-indicators.md`

- [x] **Step 1: Implement bounded parallel execution**

Extract a row helper, resolve a safe worker count, use `ThreadPoolExecutor` when there are at least two eligible tickers and more than one worker, and keep serial execution available with `max_workers=1`.

- [x] **Step 2: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_indicators.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Evidence:

```powershell
python -m pytest tests/test_indicators.py tests/test_backtest.py -q
# 50 passed after adding serial-vs-parallel equality coverage
python -m pytest -q
# 285 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0
```

Review notes: focused reviewer found no Critical or Important issues. Minor notes were fixed by checking this GREEN step and adding a real default-parallel-vs-serial equality test.

- [ ] **Step 3: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `perf: parallelize indicator computation`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.
