# Component Bridge + Async Fetching Pause Handoff

**Paused at:** 2026-05-26 06:25 Asia/Jerusalem  
**Repo:** `C:\Users\meiri\momentum and flow`  
**Branch:** `backlog-stepwise-qa`  
**Base commit at pause:** `c2bfe5d fix: complete backlog review polish`  
**GitHub / Pi:** not pushed and not deployed in this pause slice.

## User Steer / Queue

Most recent queued work:

1. Implement `whole-card/Plotly click custom component bridge`.
2. Implement `floating custom preference/header component`.
3. Implement `async fetching`.
4. On completion, commit to GitHub, push to the Pi, restart the service, and verify the public dashboard.
5. Current pause request: "i need to pause for an hour, please generate a clean handoff point, so we can continue later. including my messages in the steer/queue".

## Current Working Tree

Dirty by design. Do not reset it.

Modified:
- `app.py`
- `docs/BACKLOG.md`
- `static/style.css`
- `tests/test_header_controls_static.py`
- `tests/test_performance_audit.py`
- `tests/test_performance_audit_app_static.py`
- `tests/test_transition_pulse_app_static.py`

New:
- `src/component_bridge.py`
- `src/ohlcv_prefetch.py`
- `tests/test_component_bridge.py`
- `tests/test_component_bridge_app_static.py`
- `tests/test_ohlcv_prefetch.py`
- `tests/test_ohlcv_prefetch_app_static.py`

Generated browser QA artifacts under `docs/browser-qa/latest` were restored after an interrupted/failed browser QA run wrote zero-byte screenshots.

## Implemented In This Slice

### Whole-card / Plotly click bridge

Implemented a new `src/component_bridge.py` module with:
- `drill_bridge_attrs(...)`
- `drill_click_bridge_html()`
- `rrg_plotly_click_bridge_html(...)`
- ticker normalization and accessible keyboard/click handling.

Wired in `app.py`:
- BLUF action cards and ticker list items expose `data-drill-ticker`.
- Recent transition rows expose `data-drill-ticker`.
- Pick cards and defensive cards expose `data-drill-ticker`.
- RRG quadrant cards expose `data-drill-ticker`.
- RRG Plotly chart is rendered through a click bridge component so point clicks update `?ticker=...`.

Existing native drill selectors remain as fallback.

### Floating custom preference/header component

Implemented a custom floating bridge payload in `src/component_bridge.py`:
- refresh
- theme toggle
- BLUF mode
- density
- sparkline style
- palette

Wired in `app.py`:
- the bridge emits short-lived `bridge_*` query params.
- `_apply_control_bridge_actions()` consumes bridge params before performance snapshotting.
- refresh clears `_load_data` through `refresh_market_data(_load_data)` and drops `dashboard_compute_snapshot`.
- display preference changes stay visual-only for performance reuse.
- native profile save/load/delete remains inside `VIEW OPTIONS`.

Important follow-up: local Streamlit emitted a warning that `st.components.v1.html` should be replaced by `st.iframe` and will be removed after 2026-06-01. This must be checked before finalizing because the current bridge uses `components.html(...)`.

### Async fetching

Implemented `src/ohlcv_prefetch.py`:
- `warm_ohlcv_cache(...)`
- `submit_ohlcv_prefetch(...)`
- `prefetch_status(...)`
- deduped in-flight requests
- daemon-thread background cache warming
- provider/cache summary only, no DataFrames and no secret-bearing error text.

Wired in `app.py`:
- `_start_ohlcv_cache_prefetch()` starts a background cache warmer after a successful foreground compute.
- scoring still uses only `ohlcv_result = _load_data("3y")`.
- background prefetch is not used inside `compute_signals`.
- browser QA mode disables prefetch.

## Verification Evidence

Passed:

```powershell
python -m pytest tests/test_component_bridge.py tests/test_ohlcv_prefetch.py -q
# 10 passed in 1.66s
```

```powershell
python -m pytest tests/test_component_bridge_app_static.py tests/test_ohlcv_prefetch_app_static.py tests/test_header_controls_static.py tests/test_performance_audit.py::test_session_snapshot_tracks_interactive_widget_keys_and_ignores_audit_state tests/test_performance_audit_app_static.py::test_visual_controls_use_precompute_bridge_actions -q
# 10 passed in 0.24s
```

```powershell
python -m pytest tests/test_transition_pulse_app_static.py tests/test_performance_audit_app_static.py::test_visual_only_reuse_refreshes_read_only_transition_rows -q
# 3 passed in 0.06s
```

```powershell
python -m compileall app.py src scripts
# exit 0
```

```powershell
python -m pytest -q
# 567 passed in 38.82s
```

```powershell
git diff --check
# exit 0
```

```powershell
rg -n "use_container_width=" app.py src scripts -g "*.py"
# exit 1 with no output, meaning no matches
```

Not passed / interrupted:

```powershell
$env:BROWSER_QA_MODE='1'; $env:BROWSER_QA_FIXTURE='1'; python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true
python scripts/capture_browser_qa.py --base-url http://127.0.0.1:8502 --out-dir docs/browser-qa/latest --qa-mode local-dashboard-component-bridge
# browser_qa=written out_dir=docs\browser-qa\latest qa_mode=local-dashboard-component-bridge targets=9 failed=7
```

Browser QA notes:
- the pause interrupted the run cleanup path.
- several screenshots were zero-byte during the failed run; `docs/browser-qa/latest` was restored afterward.
- server logs showed yfinance SSL/cert failures for symbols including `IBIT`, `^TNX`, `^VIX`, and `^IRX`.
- server logs also showed `st.components.v1.html` deprecation warnings.
- port `8502` was stopped; only `TIME_WAIT` connections remained.

## First Resume Steps

1. Open this file first.
2. Run:

```powershell
git status --short --branch
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
rg -n "use_container_width=" app.py src scripts -g "*.py"
```

3. Investigate the `st.components.v1.html` deprecation warning before finalizing the custom bridge. Confirm whether this repo's Streamlit version supports `st.iframe` for the same parent-window JS behavior or whether a different component approach is needed.
4. Rerun browser QA from a clean server. If the yfinance SSL issue repeats in browser QA mode, either force fixture/cache coverage for browser QA or capture the exact blocker before committing.
5. After browser QA is healthy, commit, push `backlog-stepwise-qa`, wait for the Pi deploy workflow, verify Pi tests and HTTP smoke, then report commit hash, deploy run, Pi test count, and smoke status.

## Residual Risks

- The custom bridge currently uses `components.html(...)`; Streamlit says this path is near removal.
- Browser QA has not passed for this slice.
- No GitHub push or Pi deploy has happened for this slice.
- The implementation is uncommitted; do not assume remote or Pi has any of these changes.

## Resume Update - 2026-05-26

The handoff was resumed in the same branch. The `components.html(...)` deprecation was resolved by switching bridge rendering to `st.iframe(...)` with 1px invisible bridge frames. Browser QA no longer depends on yfinance in QA mode; `src/browser_qa_data.py` now provides deterministic local OHLCV fixtures.

Additional user-reported drill-down chart issue handled during resume:
- the price and Chaikin Money Flow charts were visually misaligned because they used different heights.
- the CMF line could clip at the top because the y-axis was fixed to `[-0.5, 0.5]`.
- `src/visuals.py` now gives CMF the same 400px height as the price chart and computes a padded y-axis range around visible CMF values and threshold guide lines.

Fresh resume verification:

```powershell
python -m pytest -q
# 569 passed in 20.69s

python -m compileall app.py src scripts
# exit 0

git diff --check
# exit 0

rg -n "use_container_width=" app.py src scripts -g "*.py"
# exit 1 with no output, meaning no matches

python scripts/capture_browser_qa.py --base-url http://127.0.0.1:8502 --out-dir docs/browser-qa/latest --qa-mode local-dashboard-component-bridge
# browser_qa=written out_dir=docs\browser-qa\latest qa_mode=local-dashboard-component-bridge targets=9 failed=0
```

Remaining after this resume update: commit, push to GitHub, wait for the Pi deploy workflow, and verify Pi/service smoke.
