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
- [x] Add async refresh job endpoints:
  - `POST /api/v1/refresh`
  - `GET /api/v1/refresh/{job_id}`
  - `GET /api/v1/refresh/{job_id}/events`
- [x] Persist refresh progress events in a small local SQLite store for browser reconnects.
- [x] Wire the refresh job runner to the real Massive/FRED/dashboard refresh sequence.
- [ ] Build a React/Next.js shell that consumes `/api/v1/health`.
- [ ] Port A/B/C overview, deep-dive, and rotation screens from the handoff artifacts.
- [ ] Replace Streamlit custom click/tooltip bridges with native React interactions.
- [ ] Add Playwright screenshot QA against the design handoff PNG/HTML references.
- [ ] Add Pi systemd/API deployment docs and Cloudflare route plan.
- [ ] Retire the Streamlit route only after feature parity, data parity, visual parity, and rollback path are documented.

## Definition Of Done For This Slice

- The current production Streamlit service is unchanged.
- The API contract is pure and unit tested.
- The optional API server can be enabled after installing dependencies.
- The refresh runner is explicit opt-in from the API (`run_now: true`) and remains queue-only by default.
- The backlog records the migration as started, not complete.
