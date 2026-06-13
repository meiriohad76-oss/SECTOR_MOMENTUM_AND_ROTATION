# Dashboard UX Review Handoff - 2026-05-25

## State

- Branch: `backlog-stepwise-qa`
- Workspace: `C:\Users\meiri\momentum and flow`
- Dashboard UX review fixes are implemented locally.
- Local QA is green and browser QA evidence was regenerated.
- Next operational step after this handoff: commit, push, and verify the Raspberry Pi deploy.

## User Review Scope

The implemented review covered:

- Larger, higher-contrast dashboard typography.
- Clearer macro tile wording and tooltips.
- Positive/negative status, trend direction, symbols, and gauges for macro/FRED blocks.
- Session range explanation and clearer state display.
- Oil tile clarified as a `USO` ETF proxy, not spot WTI crude.
- M2 tooltip explaining broad money supply.
- Recent transition readability and positive/negative transition badges.
- Pick card readability, rank badges, metric tooltip cues, and explicit sorting.
- Selector/listbox drill-down controls instead of repeated per-ticker drill buttons.
- Human-readable ETF descriptions for sectors, countries, factors, themes, crypto, and major stocks.
- RRG quadrant descriptions and selector-based drill-down.
- Browser QA hardening so screenshot capture uses the run timeout instead of the shorter Playwright default.
- Source cleanup for a stale mojibake marker in old macro tile rendering code.

## Files Touched

- `app.py`
- `src/macro_tiles.py`
- `static/style.css`
- `scripts/capture_browser_qa.py`
- `docs/browser-qa/latest/*`
- `tests/test_dashboard_review_static.py`
- `tests/test_browser_qa_script_static.py`
- `tests/test_empty_loading_states_static.py`
- `tests/test_macro_tiles.py`
- `tests/test_macro_tiles_app_static.py`
- `tests/test_mobile_responsive_static.py`

## Verification

Fresh checks run on 2026-05-25:

```powershell
python -m pytest -q
```

Result: `545 passed in 26.40s`.

```powershell
python -m compileall app.py src scripts
```

Result: passed.

```powershell
git diff --check
```

Result: passed.

Mojibake marker scan across Python, CSS, and Markdown source files.

Result: no matches.

```powershell
python scripts/capture_browser_qa.py --base-url http://127.0.0.1:8502 --out-dir docs/browser-qa/latest --qa-mode local-dashboard-ux-review
```

Result: `targets=9 failed=0`.

## Notes

- Local browser QA used `BROWSER_QA_MODE=1` and `http://127.0.0.1:8502`.
- The local Streamlit process was stopped after browser QA.
- Browser QA still reports provider gaps in screenshots when yfinance cannot fetch a few symbols locally; the provider banner is visible and expected in that mode.
- Streamlit printed deprecation warnings about `use_container_width`; that is existing follow-up work and did not fail QA.
