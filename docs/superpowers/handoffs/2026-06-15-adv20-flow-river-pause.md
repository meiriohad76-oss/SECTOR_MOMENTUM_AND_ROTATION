# Handoff: ADV20 Flow River — Paused at Spec

**Date:** 2026-06-15  
**Branch:** `main`  
**Status:** Design approved, spec committed. Implementation plan not yet written.

---

## What was done this session

1. **Confirmed design recovery is complete** — all 15 tasks from `2026-06-11-dashboard-design-recovery.md` were already implemented and merged (CLAUDE.md note was stale). DisplayShell, DisplayToolbar, /admin, PickCard, PicksGrid, TransitionsBanner, StatusTiles, semantic state colors, JetBrains Mono — all live on `main`.

2. **Brainstormed and designed ADV20 on Flow River** — 20-day average daily dollar volume (`close × volume`) per ticker, surfaced in the Flow River as `CMF 0.12 · $1.2B` on each sector node.

3. **Spec written and committed** — `docs/superpowers/specs/2026-06-15-adv20-flow-river-design.md`

---

## Exact next step to resume

Run this in Claude Code:

> "continue from the CLAUDE.md handoff"

Claude will load this file and pick up at:  
**→ invoke `superpowers:writing-plans` against `docs/superpowers/specs/2026-06-15-adv20-flow-river-design.md`**

Then execute the plan.

---

## Spec summary (4 files, no scoring changes)

| File | Change |
|---|---|
| `src/flow.py` | Add `adv_20d(df, lookback=20)` function; add `"adv_20d"` column in `compute_flow_signals()` |
| `src/api_dashboard_snapshot.py` | Add `"adv_20d": _float_or_none(_payload_value(row, "adv_20d"))` in `_row_payload()` |
| `web/lib/api.ts` | Add `adv_20d: number | null` to `SnapshotRow` type |
| `web/app/chart-primitives.tsx` | Add `fmtDollarVolume()` helper; update both node text lines; update caption |

**Null-safe throughout:** old snapshots (QA server) show just `CMF 0.12`, no bullet suffix. No QA server changes needed.

---

## Key data flow detail

`adv_20d` is NOT in `PILLAR_SCORE_COLUMNS` in `src/run_journal.py`, so it automatically routes to the `payload` dict in `scored_snapshot_records_from_frame()`. `_payload_value(row, "adv_20d")` in `api_dashboard_snapshot.py` then reads it from there.

---

## Git state

All work committed to `main`. Working tree clean (except untracked dev files).

Latest commits:
- `2e07ac5` docs: add ADV20 flow river design spec
- `c069908` docs: add CLAUDE.md project context for Claude Code sessions
- `f01d353` feat: global tooltip system with rich indicator explanations
