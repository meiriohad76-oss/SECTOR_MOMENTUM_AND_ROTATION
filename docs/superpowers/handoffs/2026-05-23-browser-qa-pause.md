# Browser QA Handoff

Repo: `C:\Users\meiri\momentum and flow`
Branch: `backlog-stepwise-qa`
Base commit: `77044760a42c862b792cbdd400d41417a979e45a` (`7704476 feat: reuse visual-only dashboard compute`)
Last refreshed: `2026-05-23 12:26:27 +03:00`

## Purpose

Preserve a clean continuation point for the browser/screenshot QA evidence slice. This slice should be committed, pushed, and deployment-verified before moving to the next backlog ticket.

## Scope

Browser QA evidence now covers the remaining visual/responsive screenshot gaps for:

- B-110 mobile responsive view
- B-111 sector spaghetti chart
- B-112 drill range selector
- B-113 full matrix hover-preview evidence
- B-114 transition pulse responsive context
- B-115 comparison view
- B-116 sparkline / drill evidence
- B-117 palette/view-options evidence
- B-146 provider fallback banner/responsive context
- B-147 visual-only rerun/performance UI context

## Implemented Files

- `app.py`
- `src/browser_qa.py`
- `scripts/capture_browser_qa.py`
- `tests/test_browser_qa.py`
- `tests/test_browser_qa_script_static.py`
- `tests/test_browser_qa_app_static.py`
- `requirements-qa.txt`
- `docs/browser-qa/latest/browser_qa_report.md`
- `docs/browser-qa/latest/browser_qa_manifest.json`
- `docs/browser-qa/latest/*.png`
- `README.md`
- `docs/BACKLOG.md`
- `docs/superpowers/handoffs/2026-05-23-browser-qa-pause.md`

## Design Notes

- `BROWSER_QA_MODE=1` plus `BROWSER_QA_ALLOW_FIXTURES=1` is an explicit QA-only mode. It forces deterministic dashboard OHLCV fixtures and disables FRED fetches so screenshot QA does not depend on Massive/FRED secrets. Production should not set `BROWSER_QA_ALLOW_FIXTURES`.
- QA mode also enables deterministic visual fixtures through query params:
  - `browser_qa_palette=Solarized`
  - `browser_qa_transition=1`
  - `browser_qa_provider_banner=1`
- The capture script uses Playwright only inside the runner and can use installed browser channels with `--browser-channel chrome` or `--browser-channel msedge`.
- Each target waits for dashboard-ready text, waits for visible loading markers to clear, scrolls Streamlit's real `section[data-testid="stMain"]` container, checks target-specific text, runs target actions, and rejects blank screenshots with Pillow image extrema.
- The table target hovers the first full-matrix row and asserts the row preview is visible.
- The palette target uses the deterministic QA query fixture, expands View Options, and asserts the Solarized radio is checked without triggering a mid-capture rerun.
- The transition target injects a same-day QA transition and asserts `.alert-row.pulse-transition` is visible.
- The provider target renders a QA provider-status banner that says no API keys are required.

## Fresh Evidence

Focused tests:

```powershell
python -m pytest tests/test_browser_qa.py tests/test_browser_qa_script_static.py tests/test_browser_qa_app_static.py -q
# 7 passed in 0.24s
```

Dashboard smoke before capture:

```powershell
Invoke-WebRequest http://127.0.0.1:8503/?ticker=XLK
# HTTP_STATUS=200
```

Browser capture:

```powershell
python scripts/capture_browser_qa.py --base-url http://127.0.0.1:8503 --browser-channel chrome --out-dir docs/browser-qa/latest --timeout-ms 120000 --settle-ms 5000 --qa-mode browser-qa-secret-free
# browser_qa=written out_dir=docs\browser-qa\latest qa_mode=browser-qa-secret-free targets=9 failed=0
```

Generated report:

- `docs/browser-qa/latest/browser_qa_report.md`
- Generated: `2026-05-23T09:21:12Z`
- Status: `9/9` targets passed

## Review Feedback Resolved

- B-117 no longer relies on generic View Options text. The target preselects Solarized in QA mode and asserts the radio is checked.
- B-113 now hovers a full-matrix row and asserts the `.row-preview` card is visible.
- B-114 now uses a deterministic transition fixture and asserts `.alert-row.pulse-transition` is visible.
- B-146 now uses a deterministic provider-status fixture in secret-free QA mode.
- Stale screenshots are unlinked before each target capture.
- Pillow and Playwright are documented in `requirements-qa.txt`.
- The manifest records `qa_mode`.
- The idle wait handles Streamlit non-breaking spaces and visible loading markers.

## Final Local Gate

```powershell
python -m pytest -q
# 473 passed in 41.92s

python -m compileall app.py src scripts
# exit 0

git diff --check
# exit 0; warnings only for README.md, app.py, and docs/BACKLOG.md LF-to-CRLF conversion
```

Commit the intended files explicitly:

```powershell
git add README.md app.py docs/BACKLOG.md requirements-qa.txt docs/browser-qa/latest scripts/capture_browser_qa.py src/browser_qa.py tests/test_browser_qa.py tests/test_browser_qa_script_static.py tests/test_browser_qa_app_static.py docs/superpowers/handoffs/2026-05-23-browser-qa-pause.md
git commit -m "test: add browser qa evidence capture"
git push
```

Then verify GitHub remote state and the Pi deployment before starting the next backlog item.

## Runtime State

A local QA Streamlit process may still be running on:

- `http://127.0.0.1:8503/?ticker=XLK`

Clean it up before switching tasks:

```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Where-Object { $_.CommandLine -like '*capture_browser_qa.py*' -or $_.CommandLine -like '*streamlit run app.py*' } | Select-Object ProcessId,CommandLine | Format-List
```
