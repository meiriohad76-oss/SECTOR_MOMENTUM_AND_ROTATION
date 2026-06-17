# RRG Trail Direction & Timeframe Headings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make RRG trail direction instantly readable (hollow start ring + bigger arrowhead) and show the analysis window + snapshot date in each chart's meta badge.

**Architecture:** Two files. `web/app/chart-primitives.tsx` gets the visual trail changes and new `generatedAt` prop logic; `web/app/dashboard-screens-client.tsx` call sites pass `generatedAt={snapshot.generated_at}` to `RrgChart` and `MomentumBars`. No backend changes, no new files.

**Tech Stack:** TypeScript, React (JSX), SVG. No frontend test framework — verification is `tsc --noEmit` (run from `web/`).

---

## File Map

| File | Role |
|---|---|
| `web/app/chart-primitives.tsx` | SVG trail geometry, new `fmtSnapshotDate` helper, `generatedAt` prop on `RrgChart` + `MomentumBars` |
| `web/app/dashboard-screens-client.tsx` | 4 call sites for `RrgChart`/`MomentumBars` — add `generatedAt`, remove stale `meta` overrides |

---

## Task 1: Trail visual — hollow start ring + bigger arrowhead

**Files:**
- Modify: `web/app/chart-primitives.tsx:535–574`

There is no frontend test framework. Verification is `tsc --noEmit` from `web/`.

The three changes are all inside the `entries.map(...)` block of `RrgChart` (lines ~531–579). They are:
1. Bigger arrowhead dimensions
2. Higher arrowhead opacity
3. New hollow ring SVG element at `trail[0]`

- [ ] **Step 1: Change arrowhead size**

Find the line (currently line 535):
```tsx
          const aLen = 6, aWid = 3;
```
Change to:
```tsx
          const aLen = 10, aWid = 5;
```

- [ ] **Step 2: Change arrowhead opacity**

Find the `<polygon>` for the arrowhead (currently line 570–574):
```tsx
              <polygon
                points={`${pointX},${pointY} ${ax1},${ay1} ${ax2},${ay2}`}
                fill={stateColor(row)}
                fillOpacity="0.55"
              />
```
Change `fillOpacity` only:
```tsx
              <polygon
                points={`${pointX},${pointY} ${ax1},${ay1} ${ax2},${ay2}`}
                fill={stateColor(row)}
                fillOpacity="0.85"
              />
```

- [ ] **Step 3: Add hollow ring after trail segments**

The trail segments block ends with `})}` and is immediately followed by a comment `{/* Arrowhead — tip at dot center… */}`. Insert the hollow ring between those two blocks:

Before:
```tsx
              {/* Arrowhead — tip at dot center, circle drawn on top covers the overlap */}
              <polygon
```
After:
```tsx
              {/* Hollow ring at trail start (oldest position — marks where this ticker was) */}
              <circle
                cx={x(trail[0].x)}
                cy={y(trail[0].y)}
                r={3}
                fill="none"
                stroke={stateColor(row)}
                strokeOpacity={0.5}
                strokeWidth={1.5}
              />
              {/* Arrowhead — tip at dot center, circle drawn on top covers the overlap */}
              <polygon
```

- [ ] **Step 4: Verify TypeScript compiles**

Run from `web/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/app/chart-primitives.tsx
git commit -m "feat: rrg trail — hollow start ring and larger arrowhead"
```

---

## Task 2: Timeframe meta badge — generatedAt prop on RrgChart and MomentumBars

**Files:**
- Modify: `web/app/chart-primitives.tsx:467–632` (add helper, update both chart components)
- Modify: `web/app/dashboard-screens-client.tsx:854–855, 1486–1504` (4 call sites)

- [ ] **Step 1: Add `fmtSnapshotDate` helper to chart-primitives.tsx**

Add this function immediately before `export function RrgChart` (currently at line 467):

```tsx
function fmtSnapshotDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}
```

- [ ] **Step 2: Add `generatedAt` prop to `RrgChart`**

Find the current `RrgChart` props block:
```tsx
export function RrgChart({
  rows,
  onSelectTicker,
  title = "Relative Rotation Graph",
  subtitle = "Quadrants are split at 100 RS-ratio and 100 RS-momentum. Trails show recent direction from saved signal values.",
  meta,
}: {
  rows: SnapshotRow[];
  onSelectTicker: (ticker: string) => void;
  title?: string;
  subtitle?: string;
  meta?: string;
}) {
```

Replace with:
```tsx
export function RrgChart({
  rows,
  onSelectTicker,
  title = "Relative Rotation Graph",
  subtitle = "Quadrants are split at 100 RS-ratio and 100 RS-momentum. Trails show recent direction from saved signal values.",
  meta,
  generatedAt,
}: {
  rows: SnapshotRow[];
  onSelectTicker: (ticker: string) => void;
  title?: string;
  subtitle?: string;
  meta?: string;
  generatedAt?: string;
}) {
  const metaLabel = generatedAt ? `52w window · ${fmtSnapshotDate(generatedAt)}` : meta;
```

- [ ] **Step 3: Use `metaLabel` in `RrgChart` heading**

Find the line that renders the meta badge in `RrgChart` (currently inside the `return`, in the `chart-heading` div):
```tsx
        {meta ? <strong>{meta}</strong> : null}
```
Replace with:
```tsx
        {metaLabel ? <strong>{metaLabel}</strong> : null}
```

- [ ] **Step 4: Add `generatedAt` prop to `MomentumBars`**

Find the current `MomentumBars` props block:
```tsx
export function MomentumBars({
  rows,
  onSelectTicker,
  title = "12-1 Momentum Rank",
  subtitle = "Sorted by current saved momentum signal.",
  meta,
}: {
  rows: SnapshotRow[];
  onSelectTicker: (ticker: string) => void;
  title?: string;
  subtitle?: string;
  meta?: string;
}) {
```

Replace with:
```tsx
export function MomentumBars({
  rows,
  onSelectTicker,
  title = "12-1 Momentum Rank",
  subtitle = "Sorted by current saved momentum signal.",
  meta,
  generatedAt,
}: {
  rows: SnapshotRow[];
  onSelectTicker: (ticker: string) => void;
  title?: string;
  subtitle?: string;
  meta?: string;
  generatedAt?: string;
}) {
  const metaLabel = generatedAt ? `12-1 month · ${fmtSnapshotDate(generatedAt)}` : meta;
```

- [ ] **Step 5: Use `metaLabel` in `MomentumBars` heading**

Find the line that renders the meta badge in `MomentumBars` (currently inside the `return`, in the `chart-heading` div):
```tsx
        {meta ? <strong>{meta}</strong> : null}
```
Replace with:
```tsx
        {metaLabel ? <strong>{metaLabel}</strong> : null}
```

**Important:** There are two `{meta ? <strong>{meta}</strong> : null}` lines in the file — one in `RrgChart` and one in `MomentumBars`. You changed the `RrgChart` one in Step 3. Only change the `MomentumBars` one here.

- [ ] **Step 6: Update rotation screen call sites**

In `web/app/dashboard-screens-client.tsx`, find the rotation screen's two chart calls (around line 854):
```tsx
        <RrgChart rows={sectors} onSelectTicker={onSelectTicker} />
        <MomentumBars rows={sectors} onSelectTicker={onSelectTicker} />
```

Replace with:
```tsx
        <RrgChart rows={sectors} onSelectTicker={onSelectTicker} generatedAt={snapshot.generated_at} />
        <MomentumBars rows={sectors} onSelectTicker={onSelectTicker} generatedAt={snapshot.generated_at} />
```

- [ ] **Step 7: Update C screen `RrgChart` call site**

Find the C screen `RrgChart` call (inside `CRotationScreen`, around line 1486):
```tsx
        <RrgChart
          rows={rows}
          title="Relative rotation | US Sectors"
          subtitle="4-week trail"
          meta={`${rows.length} rows`}
          onSelectTicker={(ticker) => {
```

Replace with:
```tsx
        <RrgChart
          rows={rows}
          title="Relative rotation | US Sectors"
          subtitle="4-week trail"
          generatedAt={snapshot.generated_at}
          onSelectTicker={(ticker) => {
```

- [ ] **Step 8: Update C screen `MomentumBars` call site**

Find the C screen `MomentumBars` call (inside `CRotationScreen`, just below the `RrgChart`):
```tsx
        <MomentumBars
          rows={rows}
          title="12-1 momentum"
          subtitle="cross-sectional momentum ranking"
          meta="z-scored"
          onSelectTicker={(ticker) => {
```

Replace with:
```tsx
        <MomentumBars
          rows={rows}
          title="12-1 momentum"
          subtitle="cross-sectional momentum ranking"
          generatedAt={snapshot.generated_at}
          onSelectTicker={(ticker) => {
```

- [ ] **Step 9: Verify TypeScript compiles**

Run from `web/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add web/app/chart-primitives.tsx web/app/dashboard-screens-client.tsx
git commit -m "feat: rrg timeframe badge — 52w window and 12-1 month with snapshot date"
```
