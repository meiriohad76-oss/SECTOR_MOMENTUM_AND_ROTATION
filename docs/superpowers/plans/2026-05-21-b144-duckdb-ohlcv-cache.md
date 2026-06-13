# B-144 DuckDB OHLCV Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent local DuckDB OHLCV cache so Pi restarts can reuse fresh market data instead of immediately refetching yfinance/Massive data.

**Architecture:** Add a focused `src.ohlcv_store` module that owns DuckDB schema, reads fresh-enough cached frames by ticker/period, and writes successful provider frames. Integrate `src.data.fetch_ohlcv()` so it loads cached tickers first, fetches only misses from the configured provider, persists successful misses, and preserves the existing return shape.

**Tech Stack:** DuckDB, pandas, pytest, existing yfinance/Massive provider adapters.

---

### Task 1: Cache Contract

**Files:**
- Create: `tests/test_ohlcv_store.py`
- Modify: `requirements.txt`

- [x] **Step 1: Install local dependency for test authoring**

Run:

```powershell
python -m pip install "duckdb>=1.1"
```

Evidence: local Python installed `duckdb-1.5.3`.

- [x] **Step 2: Write failing tests**

Cover direct DuckDB round-trip, fresh-cache fetch without provider calls, and provider-result persistence into DuckDB.

- [x] **Step 3: Verify RED**

Run:

```powershell
python -m pytest tests/test_ohlcv_store.py -q
```

Expected: FAIL because `src.ohlcv_store` does not exist yet.

Evidence:

```powershell
python -m pytest tests/test_ohlcv_store.py -q
# collection error: cannot import name 'ohlcv_store' from 'src'
```

### Task 2: Store And Fetch Integration

**Files:**
- Create: `src/ohlcv_store.py`
- Modify: `src/data.py`
- Modify: `requirements.txt`
- Modify: `docs/BACKLOG.md`
- Modify: `docs/superpowers/plans/2026-05-21-b144-duckdb-ohlcv-cache.md`

- [x] **Step 1: Implement DuckDB store**

Create the schema under `data_cache/ohlcv.duckdb` by default, support `OHLCV_CACHE_PATH`, support `OHLCV_CACHE_ENABLED=false`, and treat cached rows as usable only when they cover the requested period and the latest row is fresh within a small daily-data tolerance.

- [x] **Step 2: Integrate `fetch_ohlcv()`**

Load fresh cached tickers first, call the selected provider only for cache misses, write successful fetched frames back to DuckDB, and return tickers in the original de-duplicated request order.

- [x] **Step 3: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_ohlcv_store.py tests/test_data.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Evidence:

```powershell
python -m pytest tests/test_ohlcv_store.py tests/test_data.py -q
# 17 passed after review fixes for best-effort cache failures, sparse cache coverage, anchored path, lowercase Massive keys, and test isolation
```

Review fixes: made cache reads/writes best-effort around provider behavior, anchored the default cache path to the repo root, added requested-period business-day coverage checks for sparse caches, preserved uppercase Massive provider keys for lowercase requests, disabled default cache use in existing data tests, and corrected the `fetch_ohlcv()` column-order docstring.

- [x] **Step 4: Review, commit, push, deploy**

Request focused review, fix Critical/Important feedback, commit as `feat: add duckdb ohlcv cache`, push to GitHub, verify remote SHA, deploy to Pi with `./.venv/bin/python -m pip install -r requirements.txt`, run focused/full Pi pytest, and dashboard HTTP smoke.

Completion evidence:

```powershell
python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_run_backtest_script.py -q
# 25 passed
python -m pytest -q
# 292 passed
python -m compileall app.py src scripts
# exit 0
git diff --check
# exit 0
git push origin backlog-stepwise-qa
# 053d4e6 pushed
```

Pi evidence:

```bash
git pull --ff-only
# fast-forwarded to 053d4e6
./.venv/bin/python -m pip install -r requirements.txt
# installed duckdb-1.5.3
./.venv/bin/python -m pytest tests/test_ohlcv_store.py tests/test_data.py tests/test_run_backtest_script.py -q
# 25 passed
./.venv/bin/python -m pytest -q
# 292 passed
curl http://127.0.0.1:8501/?ticker=XLK
# HTTP 200 via sector-dashboard smoke
```
