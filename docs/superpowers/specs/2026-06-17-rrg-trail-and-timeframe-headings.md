# RRG Trail Direction & Timeframe Headings — Design Spec

**Date:** 2026-06-17  
**Status:** Approved  
**Scope:** Visual improvements to `RrgChart` and `MomentumBars` in `chart-primitives.tsx`, plus call-site updates in `dashboard-screens-client.tsx`. No backend changes.

---

## Goal

1. **Trail direction** — make it instantly obvious where the ticker started and where it is now. Users should never have to guess which end of the trail is current.
2. **Timeframe headings** — each chart's `meta` badge (already in the DOM, currently unpopulated or vague) shows the analysis window + snapshot date, e.g. `52w window · Jun 17`.

---

## Part 1: Trail direction (RrgChart)

### Current state
- 4-point synthetic trail (calculated from `s_score` drift)
- Trail segments fade from opacity 0.10 (old) to 0.50 (recent)
- Arrowhead: `aLen=6, aWid=3, fillOpacity=0.55` — small, easy to miss
- No start marker

### Changes

**A. Bigger, more opaque arrowhead**  
`aLen=6, aWid=3, fillOpacity="0.55"` → `aLen=10, aWid=5, fillOpacity="0.85"`  
The tip still sits at the current dot center.

**B. Hollow ring at trail start**  
A small ring drawn at `trail[0]` (the oldest synthetic position):

```tsx
<circle
  cx={x(trail[0].x)}
  cy={y(trail[0].y)}
  r={3}
  fill="none"
  stroke={stateColor(row)}
  strokeOpacity={0.5}
  strokeWidth={1.5}
/>
```

Rendered after trail segments and before the arrowhead. The ring is styled with the same state color but no fill, making it visually distinct from the solid current dot (`r=5`, filled).

Visual read for the user: ○ (hollow = start) → faded lines → ↑ (arrowhead = now).

No other trail changes — segment opacities, stroke width, and the 4-point geometry are unchanged.

---

## Part 2: Timeframe headings

### Current state
Both `RrgChart` and `MomentumBars` have `meta?: string` prop that renders `<strong>{meta}</strong>` top-right of the heading.
- Rotation screen: `meta` not passed (hidden)
- C screen: `meta="{n} rows"` on RrgChart; `meta="z-scored"` on MomentumBars

Neither chart knows its analysis window or snapshot date.

### New prop: `generatedAt?: string`

Add `generatedAt?: string` to both `RrgChart` and `MomentumBars`.

### New helper: `fmtSnapshotDate`

```typescript
function fmtSnapshotDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}
```

Returns e.g. `"Jun 17"` from an ISO timestamp. Same pattern as the existing `dateLabel` in `FlowRiver`.

### Badge content per chart

| Chart | Badge when `generatedAt` is set | Badge when not set |
|---|---|---|
| `RrgChart` | `52w window · Jun 17` | existing `meta` prop (or hidden) |
| `MomentumBars` | `12-1 month · Jun 17` | existing `meta` prop (or hidden) |

Inside each component:
```tsx
const metaLabel = generatedAt
  ? `${WINDOW_LABEL} · ${fmtSnapshotDate(generatedAt)}`
  : meta;
// …
{metaLabel ? <strong>{metaLabel}</strong> : null}
```

Where `WINDOW_LABEL = "52w window"` in `RrgChart` and `"12-1 month"` in `MomentumBars` (inline string constants, not exported).

### Call-site updates in `dashboard-screens-client.tsx`

Four call sites change. All receive `generatedAt={snapshot.generated_at}`. The stale `meta` overrides (`"{n} rows"`, `"z-scored"`) are removed.

**Rotation screen (lines ~854-855):**
```tsx
<RrgChart rows={sectors} onSelectTicker={onSelectTicker} generatedAt={snapshot.generated_at} />
<MomentumBars rows={sectors} onSelectTicker={onSelectTicker} generatedAt={snapshot.generated_at} />
```

**C screen (lines ~1486-1505):**
```tsx
<RrgChart
  rows={rows}
  title="Relative rotation | US Sectors"
  subtitle="4-week trail"
  generatedAt={snapshot.generated_at}
  onSelectTicker={...}
/>
<MomentumBars
  rows={rows}
  title="12-1 momentum"
  subtitle="cross-sectional momentum ranking"
  generatedAt={snapshot.generated_at}
  onSelectTicker={...}
/>
```

---

## Files changed

| File | Change |
|---|---|
| `web/app/chart-primitives.tsx` | Add `fmtSnapshotDate()`, hollow ring at trail start, bigger arrowhead, `generatedAt` prop on both charts |
| `web/app/dashboard-screens-client.tsx` | Pass `generatedAt={snapshot.generated_at}` at all 4 RrgChart/MomentumBars call sites; remove stale meta overrides |

---

## Out of scope

- `FlowRiver` — already shows snapshot date; no change needed
- `PillarStackBar`, `WaterfallChart`, `PillarHeatmap` — per-ticker detail views; timeframe not needed
- Backend / QA server — no data model changes
- Real trail data (currently synthetic from `s_score`) — separate deferred item
