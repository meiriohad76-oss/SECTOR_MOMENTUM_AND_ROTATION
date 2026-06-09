# B-170 Production Dashboard Migration Plan

> For agentic workers: use the repo's stepwise QA pattern. Keep the Streamlit dashboard live until API and React parity is proven by tests and browser QA.

## Goal

Move the dashboard from a Streamlit-first production app toward a service architecture:

- FastAPI backend for status, data refresh jobs, provider health, saved state, portfolio analysis, and backtest artifacts.
- React/Next.js frontend for layout, routing, click behavior, progress UI, sortable tables, tooltips, and A/B/C screen parity.
- Streamlit remains the current production frontend until the replacement has feature and browser-QA parity.

## Architecture

Start by extracting pure response contracts and optional API boundaries. Do not import `app.py` from API code. Do not fetch providers from API module import time. Do not write state from a read-only status endpoint.

## Implementation Checklist

- [x] Document B-170 in `docs/BACKLOG.md`.
- [x] Add pure `src/api_contract.py` with a stable JSON health/status payload.
- [x] Add optional `src/api_server.py` FastAPI app factory with `/api/v1/health` and `/api/v1/status`.
- [x] Declare `fastapi` and `uvicorn` in `requirements.txt`.
- [x] Add tests proving the API contract is Streamlit-free and provider-fetch-free.
- [x] Add a real API status provider that reads the latest persisted Pi state, run journal, and provider snapshots without recomputing the dashboard.
- [x] Add API-backed provider/data-health endpoints:
  - `GET /api/v1/data-health`
  - `GET /api/v1/provider-health`
- [x] Add async refresh job endpoints:
  - `POST /api/v1/refresh`
  - `GET /api/v1/refresh/{job_id}`
  - `GET /api/v1/refresh/{job_id}/events`
- [x] Persist refresh progress events in a small local SQLite store for browser reconnects.
- [x] Wire the refresh job runner to the real Massive/FRED/dashboard refresh sequence.
- [x] Add read-only portfolio analysis API endpoint:
  - `POST /api/v1/portfolio/analyze`
  - accepts single ticker, JSON holdings, CSV text, or base64 CSV/XLSX content
  - maps holdings to the latest persisted dashboard snapshot without provider fetches, scoring recompute, broker calls, or state writes
- [x] Add React portfolio analyzer client:
  - single ticker input
  - pasted CSV holdings
  - uploaded CSV/XLS/XLSX encoded client-side and sent to the API
  - displays exposure, missing tickers, and per-holding methodology rows from the API response
- [x] Add explicit saved-portfolio persistence for the React migration path:
  - `GET /api/v1/portfolios`
  - `POST /api/v1/portfolios`
  - `DELETE /api/v1/portfolios?name=...`
  - reuses the existing `data/saved_inputs.json` store
  - keeps `POST /api/v1/portfolio/analyze` read-only
  - React can save the last analyzed request, load a named portfolio into analysis, and delete a saved portfolio
- [x] Add read-only backtest artifact API endpoint:
  - `GET /api/v1/backtest-artifacts`
  - reports artifact presence, size, timestamps, hashes, and metadata verification state
  - returns existing report text and equity CSV rows without running backtests, calibration, provider fetches, or research jobs
- [x] Add collapsed React Backtest Lab artifact panel:
  - consumes the server-fetched `GET /api/v1/backtest-artifacts` payload
  - shows artifact verification status, report preview, and an equity-curve preview from API rows
  - stays collapsed by default so research/backtest context does not crowd the main dashboard
- [x] Add read-only ticker chart API and C2 price panel:
  - `GET /api/v1/ticker-chart?ticker=...&period=3y`
  - reads only cached OHLCV rows, computes weekly close, 30-week moving average, CMF(21), OBV, and OBV slope, and fails closed if cache data is unavailable
  - React C2 deep dive fetches the selected ticker chart asynchronously and renders price/30wMA plus CMF/OBV panels, falling back to saved gate evidence without drawing synthetic prices
- [x] Expand read-only ticker chart routing for deeper C2 parity:
  - optional benchmark query support
  - cache-only relative-strength ratio series versus the selected benchmark
  - 12-week and 52-week momentum series
  - React C2 deep dive renders a relative-strength/momentum panel from API data and falls back to saved snapshot evidence when benchmark cache is unavailable
- [x] Build a React/Next.js shell that consumes `/api/v1/health` and `/api/v1/data-health`.
- [ ] Port A/B/C overview, deep-dive, and rotation screens from the handoff artifacts.
  - [x] Add read-only `/api/v1/dashboard-snapshot` over the latest run-journal scores and decisions.
  - [x] Render first-pass journal-backed A/B/C React sections in the Next shell.
  - [x] Add native React A/B/C screen selection, row/card click selection, ticker focus selection, overview sorting, and rotation quadrant filtering in the Next shell.
  - [x] Add API-fed SVG chart primitives for pillar-stack heatmap rows, ticker waterfall, RRG, momentum bars, and data-derived flow river.
  - [x] Add repeatable Next screenshot QA against the A1/A2/A3, B1/B2/B3, and C1/C2/C3 handoff PNGs with current evidence in `docs/browser-qa/next-handoff/latest`.
  - [x] Add `?presentation=c` light Display C presentation mode so screenshot QA compares the candidate layout rather than the dark ops wrapper.
  - [x] Add `?presentation=a` terminal Display A presentation mode backed by the live snapshot, with BLUF/status tiles, 7-pillar heatmap, transition/position rail, terminal deep dive, and terminal rotation map.
  - [x] Add `?presentation=b` editorial Display B presentation mode backed by the live snapshot, with brief overview, article deep dive, and narrated rotation/map column.
  - [ ] Match the handoff A/B/C layouts and chart primitives with browser screenshot evidence.
- [ ] Replace Streamlit custom click/tooltip bridges with native React interactions.
  - [x] Native React interaction foundation exists in `web/app/dashboard-screens-client.tsx`.
  - [ ] Keep Streamlit bridge in production until the React route reaches feature, data, visual, and rollback parity.
- [x] Add Playwright screenshot QA against the design handoff PNG/HTML references.
  - [x] `scripts/capture_next_handoff_qa.py` captures Overview, Deep Dive, and Rotation against C1/C2/C3 references.
  - [x] `scripts/serve_next_qa_api.py` provides a QA-only read-only API fallback when FastAPI is not installed locally.
  - [x] Latest profile-C evidence targets `http://127.0.0.1:3100/?presentation=c`; required text/nonblank checks pass for C1/C2/C3 with current similarity 0.7795 overview, 0.8386 deep dive, and 0.8524 rotation after tightening the signed pillar-stack primitive and removing the visible C1 run-journal/debug rail card while keeping provenance as heatmap metadata, while remaining below a pixel-parity release gate.
  - [x] Latest profile-A evidence targets `http://127.0.0.1:3100/?presentation=a`; required text/nonblank checks pass for A1/A2/A3 with current similarity 0.8704 overview, 0.8736 deep dive, and 0.8939 rotation after the shared signed pillar-stack primitive update, while remaining below a pixel-parity release gate.
  - [x] Latest profile-B evidence targets `http://127.0.0.1:3100/?presentation=b`; required text/nonblank checks pass for B1/B2/B3 with current similarity 0.8427 overview, 0.8134 deep dive, and 0.8454 rotation after replacing the dark terminal RRG with a live-data editorial rotation figure, compact leaderboards, numbered B2 article paragraphs, compact gate table, and cached ticker-chart sidebar panels, while remaining below a pixel-parity release gate.
  - [x] The screenshot QA helper now hides the Next development overlay before capture and compacts duplicate snapshot sections below the local transport limit while preserving the current real row universe.
  - [ ] Raise visual similarity through layout/pixel-parity tickets before using the similarity score as a release gate.
- [x] Add Pi systemd/API deployment docs and Cloudflare route plan.
- [ ] Retire the Streamlit route only after feature parity, data parity, visual parity, and rollback path are documented.

## Definition Of Done For This Slice

- The current production Streamlit service is unchanged.
- The API contract is pure and unit tested.
- The optional API server can be enabled after installing dependencies.
- The refresh runner is explicit opt-in from the API (`run_now: true`) and remains queue-only by default.
- Data/provider-health endpoints are read-only and do not call live providers.
- The initial Next.js shell lives under `web/`, is guarded by static tests, has a committed lockfile, and passes `npm audit --omit=dev --audit-level=moderate` plus `npm run build`; Next handoff screenshot QA is repeatable for A/B/C profiles and recorded under `docs/browser-qa/next-handoff/latest`.
- The first A/B/C React sections are backed by persisted run-journal data through `/api/v1/dashboard-snapshot`; native interaction controls, API-fed chart primitives, async cached ticker chart data for price/trend, flow, relative strength, and momentum, an API-backed portfolio analyzer with explicit saved-portfolio persistence, a read-only/collapsed Backtest Lab artifact panel, and screenshot evidence are implemented in the React shell; handoff visual parity remains a future gate.
- Candidate Pi units and route docs exist for `sector-api` on `127.0.0.1:8000` and `sector-next` on `127.0.0.1:3000`, while Streamlit remains the production route.
- The backlog records the migration as started, not complete.
