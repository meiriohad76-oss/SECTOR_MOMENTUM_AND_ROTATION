# B-146 Yfinance Graceful Degradation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gracefully degrade when yfinance rate-limits or returns no fresh rows by using stale DuckDB OHLCV cache data and surfacing an operator banner.

**Architecture:** Keep `fetch_ohlcv()` backward-compatible as a dict-returning wrapper, add `fetch_ohlcv_result()` with provider/cache status metadata, and extend `read_cached_ohlcv()` with an explicit `allow_stale=True` fallback path. The dashboard consumes the richer result, renders a compact provider-status banner only for stale fallbacks or provider gaps, then continues using the same `ohlcv` dict for methodology scoring.

**Tech Stack:** pandas, DuckDB cache module, Streamlit static wiring, pytest.

---

### Task 1: Fallback Contract

**Files:**
- Modify: `tests/test_ohlcv_store.py`
- Modify: `tests/test_data.py`
- Create: `tests/test_provider_fallback_app_static.py`

- [x] **Step 1: Write failing tests**

Cover explicit stale-cache reads, stale fallback when yfinance is unavailable, missing-provider-gap metadata when no cache exists, and dashboard static wiring/CSS for the provider-status banner.

- [x] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_provider_fallback_app_static.py -q
```

Expected: FAIL because `allow_stale`, `fetch_ohlcv_result()`, and banner wiring do not exist yet.

Observed: `5 failed, 17 passed`; failures were the expected missing `allow_stale`, `fetch_ohlcv_result()`, dashboard banner wiring, and CSS selectors.

### Task 2: Fallback Implementation And Docs

**Files:**
- Modify: `src/ohlcv_store.py`
- Modify: `src/data.py`
- Modify: `app.py`
- Modify: `static/style.css`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b146-yfinance-fallback.md`

- [x] **Step 1: Implement stale-cache result path**

Add result metadata, stale-cache fallback, and warnings while preserving `fetch_ohlcv()` behavior.

- [x] **Step 2: Wire dashboard banner**

Render a provider-status banner after data load and before benchmark validation if stale cache or missing provider gaps are present.

- [x] **Step 3: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_provider_fallback_app_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Observed:

- `python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_provider_fallback_app_static.py -q` -> `22 passed in 5.35s`
- `python -m pytest -q` -> `305 passed in 8.02s`
- `python -m compileall app.py src scripts` -> exit 0
- `git diff --check` -> exit 0

- [x] **Step 4: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: add yfinance stale-cache fallback`, push to GitHub, verify remote SHA, deploy to Pi, run focused/full Pi pytest, and dashboard HTTP smoke.

Observed:

- Focused reviewer: no blocking issues; residual risk is static banner coverage rather than screenshot/responsive coverage.
- Local commit: `127017c feat: add yfinance stale-cache fallback`
- GitHub branch: `backlog-stepwise-qa` at `127017ce3b3c5bc8a950afca5ae825a87fd0ef56`
- Pi pull: fast-forwarded `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION` to `127017c`
- Pi focused verification: `./.venv/bin/python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_provider_fallback_app_static.py -q` -> `22 passed in 1.38s`
- Pi full verification: `./.venv/bin/python -m pytest -q` -> `305 passed in 4.98s`
- Pi service smoke: `poll_1 active=active http=200`
