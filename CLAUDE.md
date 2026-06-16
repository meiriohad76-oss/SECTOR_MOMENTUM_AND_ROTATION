# Momentum & Flow — Claude Code Project Context

## What this is
A local-first sector rotation dashboard. Two stacks exist simultaneously:

| Stack | Host | Port | Notes |
|---|---|---|---|
| Local Next.js | Windows 127.0.0.1 | 3100 | Dev server, uses `.env.local` |
| Local QA API | Windows 127.0.0.1 | 8765 | `python scripts/serve_next_qa_api.py --port 8765` |
| Pi FastAPI | Pi 127.0.0.1 | 8000 | Full featured, real data fetch |
| Pi Next.js | Pi 127.0.0.1 | 3100 | Deployed from git |

**Critical:** `web/.env.local` points the local Next.js at the QA API (port 8765), NOT the Pi. The QA server is a read-only mock — it serves persisted snapshot data without fetching live providers.

## Stack
- **Frontend:** Next.js 14 App Router, TypeScript, no UI library — everything is bespoke CSS in `web/app/globals.css`
- **Backend:** FastAPI (`src/api_server.py`), served by uvicorn on the Pi
- **Data:** Massive API (OHLCV), DuckDB for local cache (`data_cache/ohlcv.duckdb`), JSONL run journal
- **Signal model:** 7-pillar scoring system — see `src/scoring.py` and `src/flow.py`

## Seven pillars (weights)
1. `cmf21` — Chaikin Money Flow 21-day — **23%** (highest)
2. `mom_12_1` — 12-1 price momentum — **22%**
3. `rs_ratio` — RRG RS-Ratio — **15%**
4. `mansfield_rs` — Mansfield relative strength — **12%**
5. `breadth_50d` — Binary trend/breadth filters — **12%**
6. `cycle_tilt` — Business-cycle tilt — **8%**
7. `rs_momentum` — RRG RS-Momentum — **8%**

## Six states (state machine)
| State | Color | Meaning |
|---|---|---|
| `STAGE_2_BULLISH` | Green | Confirmed uptrend — buy/hold zone |
| `HOLD` | Blue | Trend intact, lower conviction |
| `WARNING` | Amber | Deterioration — reduce/tighten |
| `EXIT` | Orange-red | Confirmed breakdown — close |
| `BEARISH_STAGE_4` | Dark red | Full downtrend — avoid |
| `STAGE_1_BASING` | Gray | Accumulation base — wait |

## Key source files
```
web/
  app/
    layout.tsx              — Root layout; mounts <TooltipRoot />
    globals.css             — All CSS (no Tailwind)
    chart-primitives.tsx    — RrgChart, FlowRiver, MomentumBars, PillarStackBar, WaterfallChart, PillarHeatmap
    dashboard-screens-client.tsx  — All screen logic (rotation, overview, deepdive, handoff A/B/C)
    actions.ts              — Server Action: runRefreshAction() — triggers refresh job, polls, revalidates
    page.tsx                — Root page (server component)
  api/v1/refresh/
    route.ts                — POST proxy to FastAPI
    [job_id]/route.ts       — GET job status proxy
  admin/page.tsx            — Admin panel with per-lane refresh buttons
components/
  RefreshButton.tsx         — Client button using useTransition + runRefreshAction
  TooltipRoot.tsx           — Global floating tooltip engine (mousemove delegation, works in SVG too)
  DisplayShell.tsx          — Presentation mode switcher
  DisplayToolbar.tsx        — Top toolbar with refresh button
  PickCard.tsx              — Pick card with sparkline
  PicksGrid.tsx             — Grid of PickCards
  Sparkline.tsx             — SVG sparkline component
  TransitionsBanner.tsx     — State transition alerts
lib/
  api.ts                    — SnapshotRow type, fetch helpers
  state-colors.ts           — STATE_COLORS, STATE_SHORT, stateColor(), stateShortLabel()
  tooltips.ts               — Rich tooltip content: STATE_TOOLTIP, PILLAR_TOOLTIP, SCORE_TOOLTIP, RRG_QUADRANT_TOOLTIP
  sparkline.ts              — Sparkline path generation

scripts/
  serve_next_qa_api.py      — Local QA HTTP server; has do_GET, do_POST, do_OPTIONS
                              POST /api/v1/refresh → returns 202 + fake job_id
                              GET  /api/v1/refresh/{job_id} → returns "succeeded" immediately

src/
  api_dashboard_snapshot.py — Builds dashboard payload from run journal
  api_server.py             — FastAPI server
  flow.py                   — CMF, OBV, MFI, RVOL, distribution day indicators
  ohlcv_store.py            — DuckDB OHLCV cache (columns: open, high, low, close, volume, adj_close)
  scoring.py                — Composite score calculation
  indicators.py             — Technical indicator library
```

## Refresh button flow
1. User clicks → `RefreshButton.tsx` calls `runRefreshAction()` (Server Action)
2. Server Action POSTs to `API_BASE_URL/api/v1/refresh` (server-side, not browser)
3. Polls `GET /api/v1/refresh/{job_id}` every 4s until "succeeded"
4. Calls `revalidatePath("/", "layout")` → Next.js re-fetches all server components
5. Button shows `✓` → page reloads after 1.5s
6. **Local:** QA server handles the POST/GET with stub responses (no live fetch)
7. **Pi:** Real FastAPI fetches 89 tickers from Massive API (~1-2 min)

## QA server startup
```powershell
# Kill any existing instance first
netstat -ano | findstr ":8765"  # find PID
Stop-Process -Id <PID> -Force

# Start fresh
cd "c:\Users\meiri\momentum and flow"
python scripts/serve_next_qa_api.py --port 8765
```

## Tooltip system
- **Engine:** `web/components/TooltipRoot.tsx` — mounted in layout, listens to document mousemove
- **Opt-in:** Add `data-tooltip="..."` to any HTML or SVG element
- **Content:** `web/lib/tooltips.ts` — STATE_TOOLTIP, PILLAR_TOOLTIP, SCORE_TOOLTIP, RRG_QUADRANT_TOOLTIP
- **Wired to:** State pills (all views), pillar bar segments, RRG dots, rotation table column headers, card dl labels

## Current branch
`main` — all recent work is committed to main. Recent commits cover:
- Refresh button fix (QA server POST handler)
- RRG trail direction (fade + arrowhead)
- Flow river improvements (10 sectors, CMF labels, timestamp, contrast)
- Global tooltip system with rich indicator explanations
- Dashboard design recovery (DisplayShell, DisplayToolbar, /admin route, PickCard, PicksGrid, TransitionsBanner, StatusTiles, semantic state colors, JetBrains Mono) — **fully implemented and merged**
- **ADV20 on flow river** — `adv_20d()` indicator, compute_flow_signals wiring, snapshot payload, TypeScript type, FlowRiver render (`CMF 0.12 · $1.2B`) — **fully implemented and pushed 2026-06-16**

## Known deferred work
- **Real-time sparklines:** Currently synthetic (path generated from state in `web/lib/sparkline.ts`). Would need OHLCV endpoint per ticker.
