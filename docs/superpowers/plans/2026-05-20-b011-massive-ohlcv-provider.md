# B-011 Massive OHLCV Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit Massive historical OHLCV provider path for the manual backtest runner and dashboard data loader while keeping yfinance as the free default.

**Architecture:** Extend `src.data.fetch_ohlcv()` with a provider selector. `provider="yfinance"` keeps existing behavior, `provider="massive"` uses Massive aggregate bars with `MASSIVE_API_KEY`, and `provider="auto"` prefers Massive when the key is configured and otherwise falls back to yfinance. The Massive path remains deterministic under tests by injecting mocked `requests.get` responses.

**Tech Stack:** Python, pandas, requests, pytest, existing `src.data` helpers.

---

## File Structure

- Modify `src/data.py`: provider selection, Massive aggregate-bar fetcher, period-to-date-range helper, JSON-to-OHLCV parser.
- Modify `tests/test_data.py`: offline tests for provider selection, Massive request shape, response flattening, missing-key fallback, and empty/error handling.
- Modify `scripts/run_backtest.py`: use `provider="auto"` for the manual runner so Massive is preferred when configured.
- Modify `README.md`: document `OHLCV_PROVIDER` and `MASSIVE_API_KEY` for historical bars.
- Modify `docs/BACKLOG.md`: update B-011 latest slice and B-020 provider notes.

---

### Task 1: Massive Provider In Data Layer

**Files:**
- Modify: `tests/test_data.py`
- Modify: `src/data.py`

- [ ] **Step 1: Write failing tests**

Add tests that:

- set `OHLCV_PROVIDER=massive` and `MASSIVE_API_KEY=secret`
- monkeypatch `data.requests.get`
- assert Massive URL contains `/v2/aggs/ticker/XLK/range/1/day/`
- assert `Authorization: Bearer secret` is sent
- assert parsed columns are `open`, `high`, `low`, `close`, `volume`, `adj_close`
- assert missing key with `provider="auto"` falls back to yfinance
- assert Massive provider returns `{}` on HTTP/provider errors

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_data.py -q`

Expected: fails because `fetch_ohlcv()` does not accept `provider`, and Massive helpers do not exist.

- [ ] **Step 3: Implement provider seam**

In `src/data.py`:

- import `os`, `date`, `timedelta`, and `requests`
- add `_resolve_secret(name)`, mirroring the environment/Streamlit-secret pattern used in provider modules
- add `_select_ohlcv_provider(provider)`
- add `_period_to_date_range(period, today=None)` for `max`, `Nd`, `Nmo`, and `Ny`
- add `_massive_interval(interval)` supporting daily bars
- add `_frame_from_massive_results(results)`
- add `_fetch_massive_ohlcv(tickers, period, interval, api_key=None)`
- extend `fetch_ohlcv(..., provider=None)` so `auto` uses Massive only when `MASSIVE_API_KEY` exists, else yfinance

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_data.py -q`

Expected: data-layer tests pass.

- [ ] **Step 5: Commit data layer**

```powershell
git add src/data.py tests/test_data.py docs/superpowers/plans/2026-05-20-b011-massive-ohlcv-provider.md
git commit -m "feat: add massive ohlcv provider"
```

---

### Task 2: Runner Wiring And Docs

**Files:**
- Modify: `tests/test_run_backtest_script.py`
- Modify: `scripts/run_backtest.py`
- Modify: `README.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Write failing runner test**

Update the successful manual-runner test to assert `fetch_ohlcv()` is called with `provider="auto"`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_run_backtest_script.py::test_run_backtest_fetches_benchmarks_and_writes_rich_report -q`

Expected: fails because the runner does not yet pass `provider="auto"`.

- [ ] **Step 3: Wire runner and docs**

In `scripts/run_backtest.py`, call:

```python
ohlcv = fetch_ohlcv(REQUIRED_TICKERS, period="max", provider="auto")
```

Document:

- default `OHLCV_PROVIDER=yfinance`
- `OHLCV_PROVIDER=massive` to force Massive historical bars
- `OHLCV_PROVIDER=auto` to prefer Massive when `MASSIVE_API_KEY` is configured
- manual runner uses `auto`

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest tests/test_data.py tests/test_run_backtest_script.py -q
python -m compileall app.py src scripts
git diff --check
```

Expected: focused tests pass, compile exits 0, diff check exits 0 allowing normal CRLF warnings.

- [ ] **Step 5: Commit runner/docs**

```powershell
git add scripts/run_backtest.py tests/test_run_backtest_script.py README.md docs/BACKLOG.md
git commit -m "docs: document massive ohlcv backtest path"
```

---

### Task 3: Full QA And Review

**Files:** no planned edits unless QA finds issues.

- [ ] **Step 1: Run full verification**

Run:

```powershell
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

- [ ] **Step 2: Live smoke note**

Run `python scripts/run_backtest.py`. If the environment lacks `MASSIVE_API_KEY`, or Yahoo remains blocked, record the provider evidence as a manual gap rather than treating it as a deterministic test failure.

- [ ] **Step 3: Request review**

Ask reviewer to inspect provider selection, Massive request construction, no-network tests, and default-yfinance compatibility.
