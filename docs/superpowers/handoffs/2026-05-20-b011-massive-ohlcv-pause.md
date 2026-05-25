# B-011 Massive OHLCV Pause Handoff

## Stop Point

Paused on 2026-05-20 12:09:13 +03:00 on branch `backlog-stepwise-qa`.

Working tree status:

```text
## backlog-stepwise-qa
```

Latest commits:

```text
f11ae53 fix: harden ohlcv provider selection
80df356 docs: document massive ohlcv backtest path
43f8f56 feat: add massive ohlcv provider
59f515c feat: use methodology targets in backtest runner
c0d6a98 docs: plan b011 methodology runner strategy
```

## What Was Completed

- `scripts/run_backtest.py` now uses the historical methodology target builder as the manual strategy path and compares it to 60/40 SPY/AGG plus equal-weight sectors.
- `src.data.fetch_ohlcv()` now supports:
  - default yfinance provider
  - `provider="massive"` for Massive aggregate bars
  - `provider="auto"` to prefer Massive when `MASSIVE_API_KEY` is configured
  - `OHLCV_PROVIDER` override for the manual runner
- yfinance download exceptions now return `{}` instead of escaping through the dashboard or runner data path.
- Tests explicitly pin yfinance behavior so local Massive secrets cannot make offline tests hit the network.
- `.streamlit/secrets.toml.example` documents `OHLCV_PROVIDER`; `MASSIVE_API_KEY` placeholder is blank so copied examples do not accidentally select Massive in auto mode.
- B-011 docs/backlog now mention the optional Massive historical OHLCV path.

## Fresh Verification

Commands run after the latest commit:

```powershell
python -m pytest tests/test_data.py tests/test_run_backtest_script.py -q
```

Result before commit:

```text
15 passed in 0.70s
```

```powershell
python -m pytest -q
```

Result before commit:

```text
153 passed in 3.51s
```

```powershell
python -m compileall app.py src scripts
```

Result:

```text
Listing 'src'...
Listing 'scripts'...
```

```powershell
git diff --check
```

Result: exit code 0, with only normal CRLF conversion warnings before the final commit.

## Review Notes

Reviewer agent `Leibniz` reviewed `59f515c..80df356` and found:

- Critical: yfinance `yf.download()` exceptions could escape before per-ticker handling.
- Important: yfinance/default tests were not isolated from local provider env/secrets.
- Important: README said `OHLCV_PROVIDER=yfinance` could force the manual runner, but the runner hard-coded `provider="auto"`.
- Minor: copied `MASSIVE_API_KEY` placeholder could accidentally select Massive in auto mode.

All listed Critical/Important issues and the placeholder minor issue were fixed in `f11ae53`.

## Live Smoke Evidence

The workspace currently has no configured provider secrets:

```text
MASSIVE_API_KEY=UNSET
OHLCV_PROVIDER=UNSET
```

Manual smoke command:

```powershell
python scripts/run_backtest.py
```

Result: exit code 1 because `provider="auto"` fell back to Yahoo and Yahoo failed in this environment:

```text
Failed to get ticker 'BIL' reason: Failed to perform, curl: (60) SSL certificate problem: unable to get local issuer certificate.
Failed to get ticker 'AGG' reason: Failed to perform, curl: (60) SSL certificate problem: unable to get local issuer certificate.
Missing required price data for manual backtest: AGG, BIL, SPY, XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY
```

Direct probes also showed Yahoo SSL verification failures, and an unsafe `verify=False` probe reached Yahoo but returned `429 Too Many Requests`. Treat this as an external/provider evidence gap, not a deterministic test failure.

## Next Clean Continuation

1. If the user is ready to validate Massive live data, configure `MASSIVE_API_KEY` and optionally `OHLCV_PROVIDER=massive`, then run:

```powershell
python scripts/run_backtest.py
```

2. If continuing code work without secrets, stay in B-011 and implement the next deterministic slice:
   - in-sample/out-of-sample metric split, likely 2015+ out-of-sample
   - add OOS report section and acceptance gates wired to OOS metrics
   - keep all tests offline and synthetic

3. Re-run at minimum:

```powershell
python -m pytest tests/test_backtest.py tests/test_run_backtest_script.py tests/test_data.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```
