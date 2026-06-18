# Streamlit Retirement — Design Spec

**Date:** 2026-06-18  
**North star:** Retire the Streamlit frontend; Next.js becomes the sole production frontend.  
**Approach:** MVP Parity Fast Path — define a minimal feature checklist, hit it, flip the Cloudflare route, retire Streamlit.

---

## Background

B-170 delivered the Next.js/FastAPI stack foundation and brought visual similarity to 0.81–0.89 across 9 handoff views. The remaining gap is (a) pixel-level layout deltas and (b) three daily-use features absent from Next.js. Once those are closed, the retirement is a Cloudflare routing change plus a 30-day rollback window.

Research-only Streamlit sections (calibration lab, evidence gate lab, personal trade backtest, component docs) are **explicitly out of scope** for this spec. They move post-retirement as separate tickets or stay terminal-only.

---

## Architecture

Three sequential phases with hard exit gates. Phases 1 and 2 are independent and run in parallel. Phase 3 begins only when both 1 and 2 are green.

```
Phase 1: Visual Pixel Parity
  Gate: Playwright similarity ≥ 0.90 for all 9 views (A1-3, B1-3, C1-3)

Phase 2: Feature Port (3 features)
  Gate: retirement readiness checker passes feature_parity=ok

Phase 3: Operational Cutover
  Gate: retirement readiness checker passes all 5 gates on Pi
  → Flip Cloudflare route, retire Streamlit
```

---

## Phase 1: Visual Pixel Parity

**Goal:** Raise all 9 Playwright similarity scores to ≥ 0.90.

### Current baseline (all below gate)

| View | Current similarity | Gap to gate |
|---|---|---|
| B2 Deep Dive | 0.813 | −0.087 |
| C1 Overview  | 0.821 | −0.079 |
| C2 Deep Dive | 0.838 | −0.062 |
| B1 Overview  | 0.843 | −0.057 |
| B3 Rotation  | 0.845 | −0.045 |
| C3 Rotation  | 0.853 | −0.047 |
| A1 Overview  | 0.870 | −0.030 |
| A2 Deep Dive | 0.874 | −0.026 |
| A3 Rotation  | 0.894 | −0.006 |

### Method

For each view (ordered biggest gap first: B2 → C1 → C2 → B1 → B3 → C3 → A1 → A2 → A3):

1. Diff current Playwright capture against handoff PNG — identify largest visual delta regions (layout gaps, colour mismatches, element size/position).
2. Make targeted CSS/JSX fixes in `web/app/globals.css`, `web/app/dashboard-screens-client.tsx`, or `web/app/chart-primitives.tsx`.
3. Re-run `scripts/capture_next_handoff_qa.py` and verify similarity increased.
4. Repeat until ≥ 0.90 for that view before moving to the next.

### Gate commit

```
chore: visual parity gate passed — all 9 views ≥ 0.90
```

### Tooling (already in place)

- `scripts/capture_next_handoff_qa.py` — captures all 9 views
- Similarity reporter — embedded in capture script
- Handoff PNGs — `docs/browser-qa/next-handoff/latest/`
- QA API — `scripts/serve_next_qa_api.py --port 8765`
- No new infrastructure needed.

---

## Phase 2: Feature Port

Three features, all independent. Can be built in any order or simultaneously.

### Feature A: Full 7-Pillar Matrix Table

**What:** sortable table of all scored tickers — ticker, state, class, rank, S-score, F-score, all 7 pillar scores. Used daily to scan the full universe.

**API:** no backend work. All data is in `/api/v1/dashboard-snapshot` → `rows[]`.

**Frontend:**
- New `FullTable` component in `web/app/dashboard-screens-client.tsx` (or extracted to `web/components/FullTable.tsx`).
- Placed on the C1 overview screen below the heatmap, collapsed by default.
- Sortable by any column via click on column header.
- State-color pills on the `state` column (reuse `stateColor()` from `web/lib/state-colors.ts`).
- Click a row → sets selected ticker (same as existing ticker focus mechanism).

**Gate contribution:** feature_parity check sees ≥ 1 row rendered in the full table section.

---

### Feature B: Debrief Lab

**What:** run-journal history, matured outcome summaries (did past BULLISH calls play out?), macro-conditioned breakdowns.

**API:** new `GET /api/v1/debrief` endpoint in `src/api_server.py`.
- Reads run journal via existing `src/run_debrief.py` + `src/run_journal.py`.
- Returns: `runs` (latest 20 run metadata), `outcomes` (aggregated by ticker/state/horizon), `macro_conditions` (macro-bucketed outcomes when available).
- All logic already exists in Python — this is a new route + JSON serialization layer only.
- New test: `tests/test_api_debrief.py`.

**Frontend:**
- New `DebriefLab` collapsible panel in `web/components/DebriefLab.tsx`.
- Rendered in the A1 overview screen (like the existing collapsed `BacktestLab` panel).
- Shows: last N runs table, outcome hit-rate summary, macro-conditioned table.
- Fetches `/api/v1/debrief` server-side in `web/app/page.tsx` alongside existing fetches.

**Gate contribution:** `/api/v1/debrief` returns HTTP 200 with run history.

---

### Feature C: Custom Universe Builder

**What:** user pastes a ticker list → dashboard ranks them by S-score within that custom list, shows state/class summaries and action buckets.

**API:** new `POST /api/v1/universe/analyze` endpoint in `src/api_server.py`.
- Accepts `{ "tickers": ["XLK", "XLE", ...] }`.
- Runs `src/custom_universe.py` analysis against the latest persisted snapshot.
- Returns: ranked rows with state/score/class, invalid/missing ticker diagnostics, action buckets.
- New test: `tests/test_api_universe.py`.

**Frontend:**
- New `CustomUniversePanel` collapsible component in `web/components/CustomUniversePanel.tsx`.
- Text input (comma/newline separated tickers) + submit button.
- Ranked result table with state pills and S-scores.
- Validation error list for invalid/missing tickers.
- Lives as a collapsible panel in the A1 overview screen (consistent with DebriefLab placement).
- Client-side POST on submit — no server-side fetch.

**Gate contribution:** `POST /api/v1/universe/analyze` returns HTTP 200 with ranked rows.

---

### Phase 2 gate check

`scripts/check_b170_retirement_readiness.py` feature_parity=ok when:

1. Next.js HTTP 200 at root
2. `/api/v1/dashboard-snapshot` returns ≥ 1 row (existing)
3. `/api/v1/debrief` returns 200 with run history ← new
4. `POST /api/v1/universe/analyze` returns 200 with ranked rows ← new
5. Full table section renders ≥ 1 row in the Next.js HTML ← new check

Update `scripts/check_b170_retirement_readiness.py` to include the new gate checks once the features are shipped.

---

## Phase 3: Operational Cutover

Begins only after Phase 1 (visual gate) and Phase 2 (feature gate) are both green.

### Step 1: Deploy to Pi

1. Install `systemd/sector-api.service` on AHADPI5 → FastAPI on `127.0.0.1:8000`.
2. Install `systemd/sector-next.service` on AHADPI5 → Next.js on `127.0.0.1:3100`.
3. Run `scripts/check_b170_retirement_readiness.py` on Pi — all 5 gates must pass:
   - `feature_parity` — Next.js HTTP 200, snapshot rows present, debrief and universe endpoints live
   - `data_parity` — API health, data health, provider health, snapshot all return real data
   - `visual_parity` — screenshot QA similarity ≥ 0.90 (A/B/C profiles)
   - `operational_parity` — API health ok, Next.js HTTP 200
   - `rollback` — Streamlit still on port 8501, HTTP 200

### Step 2: Parallel-run window (1 week)

- Add second Cloudflare route: `next.ahaddashboards.uk` → Next.js port 3100.
- Keep `sentimentdashboard.ahaddashboards.uk` → Streamlit port 8501 unchanged.
- Run both in parallel for 7 days; verify Next.js serves real run-journal data from Pi.

### Step 3: Flip the route

- Update Cloudflare tunnel config: `sentimentdashboard.ahaddashboards.uk` → Next.js port 3100.
- Streamlit remains running on port 8501 for 30-day rollback window (not publicly routed).

### Step 4: Retire Streamlit (after 30-day window)

- No rollback triggered in 30 days → retire:
  ```
  sudo systemctl disable sector-dashboard
  sudo systemctl stop sector-dashboard
  ```
- Add `DEPRECATED` header comment to `app.py`.
- Commit: `chore: retire Streamlit — Next.js is production`
- Update CLAUDE.md "Current branch" and "Known deferred work" sections.
- Mark B-170 complete in `docs/BACKLOG.md`.

### Rollback procedure (documented)

At any point during the 30-day window:
1. Revert Cloudflare tunnel config to point back to port 8501.
2. `sudo systemctl start sector-dashboard` (if stopped).
3. Streamlit service is never deleted until the 30-day window closes.

---

## Files changed by phase

### Phase 1 (visual parity)
- `web/app/globals.css` — layout/spacing/colour fixes
- `web/app/dashboard-screens-client.tsx` — layout fixes
- `web/app/chart-primitives.tsx` — chart sizing/positioning fixes
- `docs/browser-qa/next-handoff/latest/` — updated captures

### Phase 2 (feature port)
- `src/api_server.py` — 2 new routes (`/api/v1/debrief`, `POST /api/v1/universe/analyze`)
- `tests/test_api_debrief.py` — new
- `tests/test_api_universe.py` — new
- `web/app/dashboard-screens-client.tsx` — `FullTable` + `DebriefLab` + `CustomUniversePanel` wiring
- `web/components/DebriefLab.tsx` — new
- `web/components/CustomUniversePanel.tsx` — new
- `web/app/page.tsx` — add debrief server-side fetch
- `scripts/check_b170_retirement_readiness.py` — extend feature_parity gate

### Phase 3 (operational)
- `systemd/sector-api.service` — deploy to Pi
- `systemd/sector-next.service` — deploy to Pi
- Cloudflare tunnel config — route update (not in repo, manual step)
- `app.py` — DEPRECATED header
- `docs/BACKLOG.md` — B-170 complete
- `CLAUDE.md` — update current state

---

## Out of scope (post-retirement)

These Streamlit sections are not required for retirement and will be addressed as separate tickets after Streamlit is retired:

- Calibration lab
- Evidence gate lab
- Personal trade backtest
- Comparison view
- Sector spaghetti chart
- Component docs / explainer
- View preferences panel (DisplayShell already covers theme/mode)
