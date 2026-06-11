# Dashboard Design Recovery — Spec

**Date:** 2026-06-11
**Branch:** backlog-stepwise-qa
**Status:** Approved — ready for implementation plan

---

## Context

A drift audit comparing `docs/PRODUCT_DESIGN.md` + `momentum v2/design_handoff_momentum_v2/` against the live Next.js implementation (`web/app/`) identified the following structural problems:

1. The default `/` route renders a developer API health shell, not the dashboard
2. The three user-facing displays (A/B/C) are hidden behind `?presentation=a/b/c` URL params
3. State colors are flattened to 3 generic CSS classes instead of 6 semantic tokens
4. Neither Inter nor JetBrains Mono is loaded — `Arial, Helvetica` is used throughout
5. Pick cards have no sparklines
6. The alerts/transitions banner is buried in a right rail, not a top-level section
7. The overview status tiles are wrong (4 items, wrong content)
8. There is no picks grid as a dedicated above-fold section

**Scope:** Front-end only. The Python engine, FastAPI, and Streamlit internals are untouched. This recovery plan does not add new features (comparison view, spaghetti chart are separate backlog items).

---

## Architecture Decision

**Next.js is the production front-door. Streamlit is retired as a user-facing UI** (it remains as the methodology engine and internal run/admin tool). The Next.js app reads from the existing FastAPI — no API contract changes.

---

## Layer 1 — Shell & Routing

### `/` — Landing page

The root route renders the active display directly. No health tables, no hero band, no API warning.

**Display persistence:**
- On mount, read `localStorage.getItem('momentum.display')` → `'a' | 'b' | 'c'`
- Default to `'c'` (Display C — Pillar Stack) if nothing stored
- On display switch, write the new value to localStorage

**Files changed:**
- `web/app/page.tsx` — stripped to a thin shell that renders `<DisplayShell />`
- New `web/components/DisplayShell.tsx` — reads localStorage, renders the active `HandoffAScreens | HandoffBScreens | HandoffCScreens`

### `/admin` — Developer shell

A new route at `web/app/admin/page.tsx` that renders exactly what `/` renders today:
- `HeroBand`
- `ApiWarning`
- `HealthTable` (persisted lanes)
- `HealthTable` (provider lanes)
- `ProviderRail`
- `BacktestArtifactPanel`

No user-facing content. Not linked from the main nav (accessible by URL only).

### `DisplayToolbar` — Persistent top-level switcher

New component: `web/components/DisplayToolbar.tsx`

Rendered in `web/app/layout.tsx` above all page content. Always visible. Contains:

| Element | Detail |
|---|---|
| Brand mark | The 4-bar C-shell logo + "Momentum" wordmark |
| Display buttons | Three buttons: **Terminal** (A) · **Brief** (B) · **Pillar Stack** (C) |
| Timestamp | Active display's `generatedAt`, right-aligned, muted mono |
| Admin link | Small muted link → `/admin`, far right |

**Interaction:** Clicking a button writes to localStorage and updates display state. Active button gets a 2px accent underline (the design spec tab style).

**Per-display top bars (`ATopBar`, `CTopBar`, `BMasthead`)** are slimmed down: they keep their screen-level navigation (Overview / Deep Dive / Rotation) but the display-switching buttons are removed. They no longer need to carry the display identity header — `DisplayToolbar` owns that.

---

## Layer 2 — Design Tokens

### Typography

**Font loading** in `web/app/layout.tsx`:

```ts
import { Inter, JetBrains_Mono } from 'next/font/google'

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })
```

Both variables exposed on `<html>`.

**`globals.css` updates:**
```css
body {
  font-family: var(--font-sans);
}

.mono {
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
}
```

**Rule:** Every number, ticker symbol, score, state pill label, timestamp, and quadrant label gets `font-family: var(--font-mono)`. Prose, labels, nav text use `var(--font-sans)`.

### State color semantic system

New file: `web/lib/state-colors.ts`

```ts
export const STATE_COLORS = {
  STAGE_2_BULLISH: '#1A8A4E',
  HOLD:            '#5C9DCB',
  WARNING:         '#E2A53A',
  EXIT:            '#D5562C',
  BEARISH_STAGE_4: '#A21E2C',
  STAGE_1_BASING:  '#9E9E9E',
} as const

export const STATE_COLORS_LIGHT = {
  STAGE_2_BULLISH: '#2E8B57',
  HOLD:            '#3A78B4',
  WARNING:         '#C68A1E',
  EXIT:            '#B84A23',
  BEARISH_STAGE_4: '#8C1A26',
  STAGE_1_BASING:  '#888888',
} as const

export type StateKey = keyof typeof STATE_COLORS

export function stateColor(state: string, light = false): string {
  const map = light ? STATE_COLORS_LIGHT : STATE_COLORS
  return map[state as StateKey] ?? (light ? '#888888' : '#666666')
}
```

**Migration:** `stateToneForClass()` and `statusClass()` are replaced everywhere they are used for state rendering. They are kept only for non-state UI signals (API health status, gate pass/fail indicators). All `StatePill` and card border color calls switch to `stateColor()`.

### CSS token audit for Display A shell

Add to `globals.css` under `.a-shell`:
```css
.a-shell {
  --bg:     #0a0a0a;
  --panel:  #111111;
  --border: #1f1f1f;
  --fg:     #e8e8e8;
  --muted:  #7c7c7c;
  --accent: #5fa8d3;
  --green:  #26d65b;
  --red:    #ef4f4a;
  --amber:  #e6b450;
}
```

Display C shell tokens already match the design spec — no changes needed there.

---

## Layer 3 — Components

### Sparkline generator

New pure utility: `web/lib/sparkline.ts`

**`sparkPath(ticker, state, w, h): string`**

- 60 points
- Seed: `ticker.split('').reduce((a, c) => a * 31 + c.charCodeAt(0), 7)`
- `rnd(i)`: `((Math.sin(seed * 9301 + i * 49297) * 233280) % 1 + 1) % 1`
- Shape by state:
  - `STAGE_2_BULLISH`: `0.15 + 0.7*(i/N) + 0.08*rnd(i)` — up-right
  - `HOLD`: `0.30 + 0.4*(i/N) + 0.10*rnd(i)` — gradual rise
  - `WARNING`: rise to ~0.7 over first 70%, then `−0.18*` tail
  - `EXIT`: rise over first 55%, then `−0.45*` roll-over
  - `BEARISH_STAGE_4`: `0.85 − 0.7*(i/N) + 0.08*rnd(i)` — down-right
  - `STAGE_1_BASING` / default: `0.4 + 0.2*rnd(i)` — flat noisy
- y-maps: `h − (shape * (h − 4) + 2)` (inverts y, adds 2px padding)
- Returns: SVG `d` path string

No React, no DOM. Pure function — easy to unit test.

### `Sparkline` component

New: `web/components/Sparkline.tsx`

Props:
```ts
{ ticker: string; state: string; w?: number; h?: number; color?: string }
// defaults: w=120, h=36
```

Renders:
- SVG `viewBox="0 0 {w} {h}"`, `preserveAspectRatio="none"`, `display:block`
- Path from `sparkPath(ticker, state, w, h)` — stroke = `color ?? stateColor(state)`, `strokeWidth=1.4`, no fill on line
- Gradient fill area: `d + L{w},{h} L0,{h} Z`, vertical linear gradient `color@0.28 → color@0`
- `aria-label="{ticker} price trend, {state}"`

### `StatePill` update

Existing `StatePill` component updated to use `stateColor()`:
- Background: `stateColor(state, light)` — uses the 6-color semantic system
- Text: white (`#fff`) always
- Font: `var(--font-mono)`, 0.72rem, 600, `letter-spacing: 0.03em`
- Padding: 2px 9px, border-radius: 11px
- `light` prop: passed `true` for B and C displays

### `PickCard` component

New: `web/components/PickCard.tsx`

Used exclusively inside `PicksGrid`. `SnapshotCard` continues to exist and is not changed — it is still appropriate in deep dive contexts where a single focused row is shown.

```
┌──────────────────────────────┐  ← 3px left border: stateColor(state)
│ XLK                  HOLD   │  ← ticker (mono 700) + StatePill
│ US Sectors                   │  ← asset_class (Inter, muted, 0.72rem)
│                              │
│ [sparkline 120×36]           │  ← Sparkline component
│                              │
│ S +1.83    F +0.67           │  ← mono, signed, green/red by sign
│ MOM +32.4%   LEADING         │  ← mono, muted, momentum + quadrant
└──────────────────────────────┘
```

Styles:
- Background: `panel`, 1px border, **3px left border** = `stateColor(state)`
- Padding: 12px vertical / 14px horizontal
- Border-radius: 6px
- Hover: left border → `var(--accent)`, transition 150ms ease
- Cursor: pointer

Interaction: onClick → select ticker + navigate to deep dive screen.

Numeric formatting:
- S, F: `fmtSign(value, 2)` — `+1.83` / `-0.94`
- Momentum: `fmtSign(value * 100, 1) + '%'`

### `TransitionsBanner` component

New: `web/components/TransitionsBanner.tsx`

Renders above the picks grid in all three display overview screens.

**Data source:** `snapshot.screens.overview?.transitions ?? []`

**Empty state:** Returns `null` — does not render if no transitions.

**Layout:**
```
RECENT TRANSITIONS                            last N
────────────────────────────────────────────────────
● XLF    EXIT → BEARISH_STAGE_4    yesterday
● SOXX   HOLD → WARNING            2d ago
● XLU    WARNING → STAGE_2_BULLISH  5d ago
```

Row spec:
- 8px round dot: `background: stateColor(transition.to)`
- Ticker: mono 700, min-width 64px
- Transition text: `{fromLabel} → {toLabel}`, muted, mono
- Date: right-aligned, muted, mono
- 1px bottom border between rows
- Row is a `<button>` — onClick: select ticker + navigate to deep dive

Container: `panel` background, 1px border, 6px radius, 8px/12px padding. Section header: "RECENT TRANSITIONS" in mono uppercase, muted, 0.72rem.

Max 8 rows displayed.

---

## Layer 4 — Overview Polish

### `StatusTiles` component

New: `web/components/StatusTiles.tsx`

Replaces `AStatusStrip` in the A display and the equivalent logic in C and B overview screens.

Exactly **3 tiles**, always in this order:

| # | Label | Value | Sub-caption | Color |
|---|---|---|---|---|
| 1 | `RISK REGIME` | `RISK-ON` or `CAUTION` | `{warnings} warning rows` | green/red |
| 2 | `CYCLE PHASE` | from `snapshot.run.metadata.cycle_phase` | `run-journal context` | amber if LATE/RECESS |
| 3 | `ACTIVE WARNINGS` | `state_counts.WARNING + state_counts.EXIT` | `warning + exit rows` | red if > 0, green if 0 |

**Derivation of Regime:**
```ts
const regime = warnings > bullish ? 'CAUTION' : 'RISK-ON'
```

Tile spec (per design §6.1):
- Width: 1/3 each on desktop, full-width stack on mobile
- Background: `panel`, 1px border, 6px radius
- Padding: 14px vertical / 18px horizontal
- Label: Inter uppercase, 0.72rem, 500, muted, letter-spacing 0.08em
- Value: JetBrains Mono, 1.4rem, 600
- Sub-caption: JetBrains Mono, 0.78rem, muted

### `PicksGrid` section

New: `web/components/PicksGrid.tsx`

Renders **above** the 7-pillar heatmap in all three displays' overview screens.

**Selection logic:**
```ts
const picks = [
  ...rows.filter(r => r.state === 'STAGE_2_BULLISH').sort((a,b) => b.s_score - a.s_score),
  ...rows.filter(r => r.state === 'HOLD').sort((a,b) => b.s_score - a.s_score),
].slice(0, 8)
```

**Layout:** CSS grid, `grid-template-columns: repeat(4, 1fr)` on desktop, `repeat(2, 1fr)` on tablet, `1fr` on mobile.

**Section header:** "ACTIVE PICKS" (mono uppercase, muted) + count badge.

**Empty state:** If 0 picks, renders a muted message: "No active picks — all instruments below conviction threshold."

Each card in the grid is a `PickCard` component (from Layer 3).

### Final overview screen order

**Display A (Terminal) and Display C (Pillar Stack):**

```
[ DisplayToolbar ]          ← always visible (Layer 1)
─────────────────────────────────────────────────────
[ Screen nav: Overview / Deep Dive / Rotation ]
─────────────────────────────────────────────────────
[ StatusTiles ]             ← 3 tiles: Regime / Phase / Warnings
[ TransitionsBanner ]       ← last 8 state changes (hidden if empty)
[ PicksGrid ]               ← 4–8 PickCards with sparklines
─────────────────────────────────────────────────────
[ 7-pillar heatmap ]        ← existing, unchanged
[ Right rail ]              ← existing positions/bullish cohort, unchanged
```

**Display B (Editorial — newspaper style):**

B keeps its existing overview layout, which already has equivalent "By the numbers" sidebar content. `StatusTiles` and `PicksGrid` are **not** added to B — they would break its editorial character. `TransitionsBanner` is added to B above the "This week's transitions" stories section, replacing the existing story list header.

```
[ DisplayToolbar ]          ← always visible (Layer 1)
─────────────────────────────────────────────────────
[ BMasthead + screen nav ]
─────────────────────────────────────────────────────
[ B tape strip + headline grid + By the numbers ]   ← existing, unchanged
[ TransitionsBanner ]       ← replaces bare section heading above stories
[ Transition stories + positions sidebar ]          ← existing, unchanged
```

---

## What Is Explicitly Out of Scope

The following are **not touched** in this recovery:

- Deep dive screens (A/B/C) — left as-is
- Rotation screens (RRG, momentum bars, flow river) — left as-is
- Portfolio analyzer panel — **moves to `/admin`**. After Layer 1, the "default" `DashboardScreensClient` presentation mode is no longer the entry point, so `PortfolioAnalyzerPanel` needs a home. `/admin/page.tsx` is the right place — it's an analysis tool, not part of the morning check-in flow. The `BacktestArtifactPanel` (already in default mode) moves there too.
- Gate checklist — left as-is
- Waterfall chart — left as-is
- Comparison view — separate backlog item
- Spaghetti chart — separate backlog item
- Python engine, FastAPI, Streamlit — not touched

---

## File Inventory

**New files:**
- `web/app/admin/page.tsx`
- `web/components/DisplayShell.tsx`
- `web/components/DisplayToolbar.tsx`
- `web/components/StatusTiles.tsx`
- `web/components/TransitionsBanner.tsx`
- `web/components/PickCard.tsx`
- `web/components/PicksGrid.tsx`
- `web/components/Sparkline.tsx`
- `web/lib/state-colors.ts`
- `web/lib/sparkline.ts`

**Modified files:**
- `web/app/page.tsx` — stripped to thin shell
- `web/app/layout.tsx` — add font loading + `DisplayToolbar`
- `web/app/globals.css` — font variables, `.mono` class, `.a-shell` tokens
- `web/app/dashboard-screens-client.tsx` — remove `stateToneForClass` from state rendering; remove per-display top-bar display switching; integrate `StatusTiles`, `TransitionsBanner`, `PicksGrid` into overview screens
- `web/lib/api.ts` — no changes expected

---

## Success Criteria

1. `/` loads Display C (or last-chosen display) immediately — no health tables visible
2. Switching A/B/C via the toolbar persists across page refreshes
3. `/admin` shows the health/provider/backtest panels
4. Every state pill uses the 6-color semantic palette — `HOLD` is blue, `BEARISH_STAGE_4` is dark red
5. Ticker symbols and numeric values render in JetBrains Mono
6. Pick cards show sparklines whose shapes encode the state
7. TransitionsBanner appears above the picks grid when transitions exist
8. StatusTiles shows exactly 3 tiles with correct content
9. No regressions in deep dive, rotation, or portfolio analyzer screens
