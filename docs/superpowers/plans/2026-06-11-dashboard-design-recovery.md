# Dashboard Design Recovery — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the Momentum v2 Next.js dashboard to its intended design: correct landing page, semantic state colors, JetBrains Mono typography, sparkline pick cards, prominent transitions banner, and a fixed overview screen order.

**Architecture:** Four independent layers applied in sequence — Shell/Routing → Design Tokens → Components → Overview Polish. Each layer is independently testable. No Python/API changes. All work is in `web/`.

**Tech Stack:** Next.js 14 (App Router), TypeScript, CSS Modules via `globals.css`, `next/font/google` for font loading, React 18 client components.

---

## File Map

### New files
| File | Responsibility |
|---|---|
| `web/app/admin/page.tsx` | Developer health shell (current `/` content) |
| `web/components/DisplayShell.tsx` | localStorage display state + renders active A/B/C display |
| `web/components/DisplayToolbar.tsx` | Persistent A/B/C switcher rendered above all display content |
| `web/components/StatusTiles.tsx` | 3-tile status row (Regime / Phase / Warnings) |
| `web/components/TransitionsBanner.tsx` | Last-8 state transitions above picks grid |
| `web/components/PickCard.tsx` | Pick card with sparkline, state pill, scores |
| `web/components/PicksGrid.tsx` | 4-up grid of PickCards above heatmap |
| `web/components/Sparkline.tsx` | SVG sparkline component |
| `web/lib/state-colors.ts` | 6-color semantic state system — single source of truth |
| `web/lib/sparkline.ts` | Pure `sparkPath()` generator function |

### Modified files
| File | What changes |
|---|---|
| `web/app/page.tsx` | Stripped to thin shell — renders `<DisplayShell>` only |
| `web/app/layout.tsx` | Adds Inter + JetBrains Mono font variables |
| `web/app/globals.css` | Adds `--font-sans/mono`, `.mono` class, `.a-shell` tokens, new component styles |
| `web/app/dashboard-screens-client.tsx` | Adds `"admin"` presentation mode; migrates `StatePill` to `stateColor()`; slims `ATopBar`/`CTopBar`/`BMasthead`; integrates `StatusTiles`/`TransitionsBanner`/`PicksGrid` into overview screens |

---

## Layer 1 — Shell & Routing

### Task 1: State color semantic module

**Files:**
- Create: `web/lib/state-colors.ts`

- [ ] **Step 1: Create the module**

```typescript
// web/lib/state-colors.ts

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

export const STATE_SHORT: Record<StateKey, string> = {
  STAGE_2_BULLISH: 'BULLISH',
  HOLD:            'HOLD',
  WARNING:         'WARN',
  EXIT:            'EXIT',
  BEARISH_STAGE_4: 'BEAR',
  STAGE_1_BASING:  'BASE',
}

/** Returns the hex color for a state string. Falls back to gray if unknown. */
export function stateColor(state: string, light = false): string {
  const map = light ? STATE_COLORS_LIGHT : STATE_COLORS
  return map[state as StateKey] ?? (light ? '#888888' : '#666666')
}

/** Returns the compact display label for a state string. */
export function stateShortLabel(state: string): string {
  return STATE_SHORT[state as StateKey] ?? state.replaceAll('_', ' ')
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors referencing `state-colors.ts`

- [ ] **Step 3: Commit**

```bash
cd web && git add lib/state-colors.ts
git commit -m "feat: add semantic state color module (6-state system)"
```

---

### Task 2: /admin route

Move the developer health shell out of `/` into `/admin`. The `page.tsx` components (`HeroBand`, `HealthTable`, `ProviderRail`, `ApiWarning`) move wholesale. `PortfolioAnalyzerPanel` and `BacktestArtifactPanel` from `dashboard-screens-client.tsx` also go here via a new `"admin"` presentation mode.

**Files:**
- Create: `web/app/admin/page.tsx`
- Modify: `web/app/dashboard-screens-client.tsx` (add `"admin"` to `PresentationMode`)

- [ ] **Step 1: Add `"admin"` presentation mode to `DashboardScreensClient`**

In `web/app/dashboard-screens-client.tsx`, find:
```typescript
type PresentationMode = "default" | "handoff-a" | "handoff-b" | "handoff-c";
```
Replace with:
```typescript
type PresentationMode = "default" | "handoff-a" | "handoff-b" | "handoff-c" | "admin";
```

Then, inside `DashboardScreensClient`, add this block **before** the `if (presentation === "handoff-a")` check:

```typescript
  if (presentation === "admin") {
    return (
      <div className="screen-stack">
        <PortfolioAnalyzerPanel onSelectTicker={() => {}} />
        <BacktestArtifactPanel payload={backtestArtifacts} />
      </div>
    );
  }
```

- [ ] **Step 2: Create `web/app/admin/page.tsx`**

Copy the server-side components from the current `web/app/page.tsx` and wire them together:

```typescript
// web/app/admin/page.tsx
import {
  fetchBacktestArtifacts,
  fetchDashboardSnapshot,
  fetchDataHealth,
  fetchHealth,
  type BacktestArtifactsPayload,
  type DashboardHealthPayload,
  type HealthLane,
} from "../../lib/api";
import DashboardScreensClient from "../dashboard-screens-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "healthy" || normalized === "info") return "good";
  if (normalized === "stale") return "bad";
  return "warn";
}

function laneRows(payload: DashboardHealthPayload | null): HealthLane[] {
  return payload?.lanes ?? [];
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${statusClass(status)}`}>{status || "unknown"}</span>;
}

function HeroBand({ payload }: { payload: DashboardHealthPayload | null }) {
  const health = payload?.health;
  return (
    <section className="hero-band" aria-label="Dashboard health overview">
      <div>
        <p className="eyebrow">Admin / System health</p>
        <h1>Sector Momentum — Admin</h1>
        <p className="subtle">
          {health?.detail || "Waiting for the FastAPI backend health payload."}
        </p>
      </div>
      <div className="summary-strip">
        <div><span>Health</span><strong>{health?.label || "Unavailable"}</strong></div>
        <div><span>Lanes</span><strong>{health?.lane_count ?? 0}</strong></div>
        <div><span>Generated</span><strong>{payload?.generated_at || "-"}</strong></div>
        <div><span>Frontend</span><strong>{payload?.app?.active_frontend || "next"}</strong></div>
      </div>
    </section>
  );
}

function HealthTable({ title, lanes }: { title: string; lanes: HealthLane[] }) {
  return (
    <section className="table-section" aria-label={title}>
      <div className="section-heading">
        <h2>{title}</h2>
        <span>{lanes.length} lanes</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Lane</th><th>Status</th><th>Latest</th>
              <th>Freshness</th><th>Coverage</th><th>Operational Detail</th>
            </tr>
          </thead>
          <tbody>
            {lanes.map((lane) => (
              <tr key={lane.lane_id}>
                <td><strong>{lane.source || lane.lane_id}</strong><small>{lane.role}</small></td>
                <td><StatusPill status={lane.status} /></td>
                <td>{lane.latest || "-"}</td>
                <td>{lane.freshness || "-"}</td>
                <td>{lane.coverage || "-"}</td>
                <td>{lane.detail || lane.sla || "-"}</td>
              </tr>
            ))}
            {!lanes.length ? (
              <tr><td colSpan={6}>No API health lanes returned yet.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProviderRail({ payload }: { payload: DashboardHealthPayload | null }) {
  const providerLane = laneRows(payload).find((lane) => lane.lane_id === "provider_flow_readiness");
  const providers = providerLane?.providers ?? [];
  return (
    <aside className="provider-rail" aria-label="Provider health">
      <div className="section-heading compact">
        <h2>Provider Flow</h2>
        <span>{payload?.provider_flow?.enabled_provider_count ?? 0} enabled</span>
      </div>
      <div className="provider-list">
        {providers.map((provider) => (
          <div className="provider-row" key={provider.id}>
            <div>
              <strong>{provider.label}</strong>
              <span>{provider.provider} | {provider.signal}</span>
            </div>
            <StatusPill status={provider.status} />
            <p>{provider.mode}. {provider.detail}</p>
          </div>
        ))}
        {!providers.length ? (
          <p className="subtle">Provider readiness is unavailable until the API responds.</p>
        ) : null}
      </div>
    </aside>
  );
}

function ApiWarning({
  healthError, dataHealthError, snapshotError, backtestError,
}: { healthError: string; dataHealthError: string; snapshotError: string; backtestError: string }) {
  if (!healthError && !dataHealthError && !snapshotError && !backtestError) return null;
  return (
    <section className="api-warning" role="status">
      <strong>API connection pending</strong>
      <span>
        Health: {healthError || "ok"} | Data health: {dataHealthError || "ok"} |
        Snapshot: {snapshotError || "ok"} | Backtest: {backtestError || "ok"}
      </span>
    </section>
  );
}

export default async function AdminPage() {
  const [healthResult, dataHealthResult, snapshotResult, backtestResult] = await Promise.all([
    fetchHealth(),
    fetchDataHealth(),
    fetchDashboardSnapshot(),
    fetchBacktestArtifacts(),
  ]);
  const primary = dataHealthResult.data || healthResult.data;
  const snapshot = snapshotResult.data;
  const backtestArtifacts: BacktestArtifactsPayload | null = backtestResult.data;
  const persistedLanes = laneRows(primary).filter((lane) => !lane.lane_id.startsWith("provider_"));
  const providerLanes = laneRows(primary).filter((lane) => lane.lane_id.startsWith("provider_"));

  return (
    <main>
      <HeroBand payload={primary} />
      <ApiWarning
        healthError={healthResult.error}
        dataHealthError={dataHealthResult.error}
        snapshotError={snapshotResult.error}
        backtestError={backtestResult.error}
      />
      <div className="dashboard-grid">
        <div className="main-stack">
          <DashboardScreensClient
            snapshot={snapshot}
            backtestArtifacts={backtestArtifacts}
            presentation="admin"
          />
          <HealthTable title="Persisted Data Health" lanes={persistedLanes} />
          <HealthTable title="Provider Data Health" lanes={providerLanes} />
        </div>
        <ProviderRail payload={primary} />
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Verify build**

```bash
cd web && npx tsc --noEmit 2>&1 | head -30
```
Expected: no new type errors

- [ ] **Step 4: Commit**

```bash
git add web/app/admin/page.tsx web/app/dashboard-screens-client.tsx
git commit -m "feat: add /admin route with dev shell, portfolio analyzer, backtest panel"
```

---

### Task 3: DisplayShell + stripped page.tsx

`DisplayShell` owns the display state (localStorage) and renders the active handoff display. `page.tsx` becomes a minimal server wrapper.

**Files:**
- Create: `web/components/DisplayShell.tsx`
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Create `web/components/DisplayShell.tsx`**

```typescript
// web/components/DisplayShell.tsx
"use client";

import { useEffect, useState } from "react";
import type { DashboardSnapshotPayload } from "../lib/api";
import DashboardScreensClient from "../app/dashboard-screens-client";
import DisplayToolbar from "./DisplayToolbar";

export type DisplayMode = "a" | "b" | "c";
const STORAGE_KEY = "momentum.display";

export default function DisplayShell({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload | null;
}) {
  const [display, setDisplay] = useState<DisplayMode>("c");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "a" || stored === "b" || stored === "c") {
      setDisplay(stored);
    }
    setHydrated(true);
  }, []);

  function switchDisplay(mode: DisplayMode) {
    setDisplay(mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }

  const generatedAt = snapshot?.generated_at ?? "";

  const presentation =
    display === "a" ? "handoff-a" : display === "b" ? "handoff-b" : "handoff-c";

  // Suppress flash of wrong display before hydration
  if (!hydrated) {
    return (
      <div style={{ minHeight: "100vh", background: "#fbfaf8" }} aria-hidden="true" />
    );
  }

  return (
    <>
      <DisplayToolbar
        activeDisplay={display}
        generatedAt={generatedAt}
        onSwitch={switchDisplay}
      />
      <DashboardScreensClient snapshot={snapshot} presentation={presentation} />
    </>
  );
}
```

- [ ] **Step 2: Strip `web/app/page.tsx` to a thin server shell**

Replace the entire contents of `web/app/page.tsx` with:

```typescript
// web/app/page.tsx
import { fetchDashboardSnapshot } from "../lib/api";
import DisplayShell from "../components/DisplayShell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  const result = await fetchDashboardSnapshot();
  return (
    <main>
      <DisplayShell snapshot={result.data} />
    </main>
  );
}
```

- [ ] **Step 3: Verify build compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors from the new files. `DisplayToolbar` import will error until Task 4 — that is expected.

- [ ] **Step 4: Commit (after Task 4 completes)**

Hold this commit — complete Task 4 first, then commit both together.

---

### Task 4: DisplayToolbar component

The persistent display switcher rendered by `DisplayShell` above all content.

**Files:**
- Create: `web/components/DisplayToolbar.tsx`
- Modify: `web/app/globals.css` (add toolbar styles)

- [ ] **Step 1: Create `web/components/DisplayToolbar.tsx`**

```typescript
// web/components/DisplayToolbar.tsx
import type { DisplayMode } from "./DisplayShell";

const DISPLAY_TABS: { mode: DisplayMode; label: string; title: string }[] = [
  { mode: "a", label: "A", title: "Terminal" },
  { mode: "b", label: "B", title: "Brief" },
  { mode: "c", label: "C", title: "Pillar Stack" },
];

export default function DisplayToolbar({
  activeDisplay,
  generatedAt,
  onSwitch,
}: {
  activeDisplay: DisplayMode;
  generatedAt: string;
  onSwitch: (mode: DisplayMode) => void;
}) {
  return (
    <header className="display-toolbar" aria-label="Display mode selector">
      <div className="display-toolbar-brand">
        <span className="c-logo" aria-hidden="true">
          <span /><span /><span /><span />
        </span>
        <strong>Momentum</strong>
      </div>
      <nav className="display-toolbar-tabs" aria-label="Choose display style">
        {DISPLAY_TABS.map(({ mode, label, title }) => (
          <button
            key={mode}
            type="button"
            className={`display-toolbar-tab${activeDisplay === mode ? " active" : ""}`}
            onClick={() => onSwitch(mode)}
            aria-pressed={activeDisplay === mode}
            title={title}
          >
            <span className="display-toolbar-tab-label">{label}</span>
            <span className="display-toolbar-tab-title">{title}</span>
          </button>
        ))}
      </nav>
      <div className="display-toolbar-right">
        {generatedAt ? (
          <span className="display-toolbar-timestamp mono">{generatedAt}</span>
        ) : null}
        <a href="/admin" className="display-toolbar-admin">Admin</a>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Add toolbar styles to `web/app/globals.css`**

Append to `globals.css`:

```css
/* ── Display Toolbar ── */
.display-toolbar {
  display: flex;
  align-items: center;
  gap: 18px;
  height: 52px;
  padding: 0 28px;
  background: #0f1318;
  border-bottom: 1px solid #2a3542;
  position: sticky;
  top: 0;
  z-index: 100;
}

.display-toolbar-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-right: 8px;
}

.display-toolbar-brand strong {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #e8e8e8;
}

.display-toolbar-tabs {
  display: flex;
  gap: 2px;
}

.display-toolbar-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #6a7a88;
  cursor: pointer;
  transition: color 150ms, border-color 150ms;
}

.display-toolbar-tab.active {
  color: #e8e8e8;
  border-bottom: 2px solid #5fa8d3;
  border-radius: 0;
}

.display-toolbar-tab:hover:not(.active) { color: #aab8c4; }

.display-toolbar-tab-label {
  font-family: var(--font-mono, monospace);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.display-toolbar-tab-title {
  font-size: 0.78rem;
  font-weight: 500;
}

.display-toolbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 20px;
}

.display-toolbar-timestamp {
  font-size: 0.72rem;
  color: #4e5e6a;
}

.display-toolbar-admin {
  font-size: 0.72rem;
  color: #4e5e6a;
  text-decoration: none;
}

.display-toolbar-admin:hover { color: #8a9aaa; }
```

- [ ] **Step 3: Commit Tasks 3 + 4 together**

```bash
git add web/app/page.tsx web/components/DisplayShell.tsx web/components/DisplayToolbar.tsx web/app/globals.css
git commit -m "feat: add DisplayShell + DisplayToolbar, strip page.tsx to thin shell

Landing page now renders active display (default C) with localStorage
persistence. A/B/C switcher is always visible at top. Dev shell moved
to /admin."
```

- [ ] **Step 4: Manual verification**

Start the dev server (`cd web && npm run dev`) and confirm:
1. `http://localhost:3000` renders Display C (Pillar Stack) — NOT the health tables
2. The toolbar is visible at top with Terminal / Brief / Pillar Stack tabs
3. Clicking each tab switches the display
4. Refreshing the page preserves the last-selected display
5. `http://localhost:3000/admin` shows the health tables, portfolio analyzer, backtest panel
6. No console errors

---

## Layer 2 — Design Tokens

### Task 5: Typography — Inter + JetBrains Mono

**Files:**
- Modify: `web/app/layout.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Update `web/app/layout.tsx` to load fonts**

Replace the entire file with:

```typescript
// web/app/layout.tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Momentum — Sector Rotation Dashboard",
  description: "Seven-pillar sector rotation dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Update `globals.css` — font variables, `.mono` utility, `.a-shell` color tokens**

Find the `:root` block and `body` rule at the top of `globals.css`. Replace them with:

```css
:root {
  color-scheme: dark;
  --bg: #080b0e;
  --band: #111820;
  --panel: #151d25;
  --line: #2b3742;
  --text: #f2f6f8;
  --muted: #a9bac5;
  --soft: #d6e1e7;
  --good: #5bd28f;
  --warn: #f2c14e;
  --bad: #ff6b6b;
  --accent: #6ec6ff;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans, Arial, Helvetica, sans-serif);
  letter-spacing: 0;
}

/* Mono utility — use on all numerics, tickers, state labels, timestamps */
.mono {
  font-family: var(--font-mono, monospace);
  font-feature-settings: "tnum";
}
```

Then add the `.a-shell` color tokens block after the `.handoff-main` rule. Find `.handoff-main` and add **after** it:

```css
/* Display A (Terminal) dark-theme tokens */
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

- [ ] **Step 3: Verify fonts load**

```bash
cd web && npm run build 2>&1 | tail -20
```
Expected: build succeeds, output mentions `Inter` and `JetBrains_Mono` in the font optimization section.

- [ ] **Step 4: Commit**

```bash
git add web/app/layout.tsx web/app/globals.css
git commit -m "feat: load Inter + JetBrains Mono, add .mono utility, .a-shell tokens"
```

---

### Task 6: Migrate StatePill to semantic colors + slim per-display top bars

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Add the `stateColor` import at the top of `dashboard-screens-client.tsx`**

After the existing imports block, add:

```typescript
import { stateColor, stateShortLabel } from "../lib/state-colors";
```

- [ ] **Step 2: Replace the `StatusPill` component in `dashboard-screens-client.tsx`**

Find:
```typescript
function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${statusClass(status)}`}>{status || "unknown"}</span>;
}
```

Replace with:

```typescript
function StatusPill({ status, light = false }: { status: string; light?: boolean }) {
  const bg = stateColor(status, light);
  const label = stateShortLabel(status) || status || "unknown";
  return (
    <span
      className="state-pill mono"
      style={{ background: bg, color: "#fff", padding: "2px 9px", borderRadius: "11px",
               fontSize: "0.72rem", fontWeight: 600, letterSpacing: "0.03em",
               display: "inline-block", lineHeight: 1.4 }}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 3: Add `state-pill` class to `globals.css`**

Append to `globals.css`:

```css
/* ── State Pill ── */
.state-pill {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 11px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  line-height: 1.4;
  color: #fff;
  white-space: nowrap;
}
```

- [ ] **Step 4: Remove display-switching buttons from `ATopBar`**

In `dashboard-screens-client.tsx`, find `ATopBar`. It currently renders a `<nav className="a-tabs">` with `SCREENS.map(...)` buttons. Remove the entire `<nav className="a-tabs">` element. Leave the brand mark and timestamp.

The `ATopBar` after the change should look like:

```typescript
function ATopBar({
  activeScreen,
  setActiveScreen,
  generatedAt,
}: {
  activeScreen: ScreenId;
  setActiveScreen: (screen: ScreenId) => void;
  generatedAt: string;
}) {
  const labels: { id: ScreenId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "deepdive", label: "Deep Dive" },
    { id: "rotation", label: "Rotation" },
  ];
  return (
    <header className="a-topbar">
      <div className="a-brand"><i /> <strong>SENTIMENT BOARD</strong><span>v2 / momentum</span></div>
      <nav className="a-screen-tabs" aria-label="Display A screen selector">
        {labels.map((item) => (
          <button
            type="button"
            key={item.id}
            className={activeScreen === item.id ? "active" : ""}
            onClick={() => setActiveScreen(item.id)}
            aria-pressed={activeScreen === item.id}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="a-live"><i /> LIVE | {generatedAt || "latest run"}</div>
    </header>
  );
}
```

- [ ] **Step 5: Remove display-switching from `CTopBar`**

`CTopBar` already shows screen-level tabs (Heatmap / Rotation / Deep dive). Remove any reference to the old `SCREENS` constant from it. The current `CTopBar` already only shows screen-level nav — verify it does not render A/B/C display tabs. If it does, remove them. Leave the brand, screen tabs, timestamp, and icon buttons unchanged.

- [ ] **Step 6: Remove display-switching from `BMasthead`**

`BMasthead` renders `SCREENS.map(...)` in its nav. Replace with screen-level tabs only:

```typescript
function BMasthead({
  activeScreen,
  setActiveScreen,
  compact = false,
}: {
  activeScreen: ScreenId;
  setActiveScreen: (screen: ScreenId) => void;
  compact?: boolean;
}) {
  const labels: { id: ScreenId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "deepdive", label: "Deep Dive" },
    { id: "rotation", label: "Rotation" },
  ];
  return (
    <header className={compact ? "b-masthead compact" : "b-masthead"}>
      <strong>The Sentiment Brief</strong>
      <span>{compact ? (activeScreen === "deepdive" ? "DEEP-DIVE" : "THE ROTATION MAP") : "EVENING EDITION"}</span>
      <nav aria-label="Display B screen selector">
        {labels.map((item) => (
          <button
            type="button"
            key={item.id}
            className={activeScreen === item.id ? "active" : ""}
            onClick={() => setActiveScreen(item.id)}
            aria-pressed={activeScreen === item.id}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </header>
  );
}
```

- [ ] **Step 7: Verify build**

```bash
cd web && npx tsc --noEmit 2>&1 | head -30
```
Expected: no new errors

- [ ] **Step 8: Commit**

```bash
git add web/app/dashboard-screens-client.tsx web/app/globals.css
git commit -m "feat: migrate StatePill to 6-color semantic system, slim display top bars"
```

---

## Layer 3 — Components

### Task 7: Sparkline utility (pure function)

**Files:**
- Create: `web/lib/sparkline.ts`

- [ ] **Step 1: Create the sparkline generator**

```typescript
// web/lib/sparkline.ts

/**
 * Generates a deterministic SVG path string for a sparkline.
 * Shape encodes the state — no real price data needed.
 * Seeded from the ticker symbol so it's stable across renders.
 */
export function sparkPath(ticker: string, state: string, w: number, h: number): string {
  const N = 60;
  const seed = ticker.split("").reduce((a, c) => a * 31 + c.charCodeAt(0), 7);

  function rnd(i: number): number {
    return ((Math.sin(seed * 9301 + i * 49297) * 233280) % 1 + 1) % 1;
  }

  function shapeY(i: number): number {
    const t = i / (N - 1);
    const s = state.toUpperCase();

    if (s.includes("STAGE_2_BULLISH") || s === "BUY") {
      return 0.15 + 0.7 * t + 0.08 * rnd(i);
    }
    if (s === "HOLD") {
      return 0.30 + 0.4 * t + 0.10 * rnd(i);
    }
    if (s.includes("WARNING") || s === "WARN") {
      if (t < 0.7) return 0.15 + 0.7 * (t / 0.7) + 0.08 * rnd(i);
      return 0.85 - 0.18 * ((t - 0.7) / 0.3) + 0.08 * rnd(i);
    }
    if (s.includes("EXIT")) {
      if (t < 0.55) return 0.15 + 0.7 * (t / 0.55) + 0.08 * rnd(i);
      return 0.85 - 0.45 * ((t - 0.55) / 0.45) + 0.08 * rnd(i);
    }
    if (s.includes("BEARISH") || s === "BEAR") {
      return 0.85 - 0.7 * t + 0.08 * rnd(i);
    }
    // STAGE_1_BASING / default: flat noisy
    return 0.4 + 0.2 * rnd(i);
  }

  const points = Array.from({ length: N }, (_, i) => {
    const x = (i / (N - 1)) * w;
    const y = h - (shapeY(i) * (h - 4) + 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return points.join(" ");
}
```

- [ ] **Step 2: Smoke-test the generator in Node**

```bash
cd web && node -e "
const { sparkPath } = require('./lib/sparkline.ts');
" 2>&1 || echo "Note: .ts files need tsc; checking via tsc instead"
cd web && npx tsc --noEmit 2>&1 | grep sparkline
```
Expected: no TypeScript errors from `sparkline.ts`

- [ ] **Step 3: Commit**

```bash
git add web/lib/sparkline.ts
git commit -m "feat: add deterministic sparkline path generator (state→shape encoding)"
```

---

### Task 8: Sparkline React component

**Files:**
- Create: `web/components/Sparkline.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create `web/components/Sparkline.tsx`**

```typescript
// web/components/Sparkline.tsx
import { sparkPath } from "../lib/sparkline";
import { stateColor } from "../lib/state-colors";

export default function Sparkline({
  ticker,
  state,
  w = 120,
  h = 36,
  color,
}: {
  ticker: string;
  state: string;
  w?: number;
  h?: number;
  color?: string;
}) {
  const strokeColor = color ?? stateColor(state);
  const path = sparkPath(ticker, state, w, h);
  const gradientId = `sg-${ticker}-${w}`;
  const areaPath = `${path} L${w},${h} L0,${h} Z`;

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      preserveAspectRatio="none"
      aria-label={`${ticker} price trend, ${state.replaceAll("_", " ")}`}
      role="img"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity={0.28} />
          <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <path d={path} stroke={strokeColor} strokeWidth={1.4} fill="none" />
    </svg>
  );
}
```

- [ ] **Step 2: Add sparkline CSS to `globals.css`**

Append to `globals.css`:

```css
/* ── Sparkline ── */
.sparkline {
  display: block;
  overflow: visible;
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | grep -E "Sparkline|sparkline" | head -10
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/components/Sparkline.tsx web/app/globals.css
git commit -m "feat: add Sparkline component (state-encoded, gradient fill)"
```

---

### Task 9: PickCard component

**Files:**
- Create: `web/components/PickCard.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create `web/components/PickCard.tsx`**

```typescript
// web/components/PickCard.tsx
import type { SnapshotRow } from "../lib/api";
import { stateColor, stateShortLabel } from "../lib/state-colors";
import Sparkline from "./Sparkline";

function fmtSigned(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "n/a";
  return (n >= 0 ? "+" : "") + n.toFixed(d);
}

export default function PickCard({
  row,
  light = false,
  onSelect,
}: {
  row: SnapshotRow;
  light?: boolean;
  onSelect: (ticker: string) => void;
}) {
  const color = stateColor(row.state, light);
  const label = stateShortLabel(row.state);
  const momPct = row.momentum_pct !== null && row.momentum_pct !== undefined
    ? fmtSigned(row.momentum_pct * 100, 1) + "%"
    : "n/a";

  return (
    <button
      type="button"
      className="pick-card"
      style={{ "--state-color": color } as React.CSSProperties}
      onClick={() => onSelect(row.ticker)}
      aria-label={`${row.display_label}: S ${fmtSigned(row.s_score)}, ${label}`}
    >
      <div className="pick-card-head">
        <strong className="pick-card-ticker mono">{row.ticker}</strong>
        <span className="pick-card-pill mono" style={{ background: color }}>{label}</span>
      </div>
      <span className="pick-card-class">{row.asset_class}</span>
      <Sparkline ticker={row.ticker} state={row.state} w={120} h={36} />
      <div className="pick-card-scores mono">
        <span className={row.s_score >= 0 ? "good" : "bad"}>S {fmtSigned(row.s_score)}</span>
        <span className={(row.f_score ?? 0) >= 0 ? "good" : "bad"}>F {fmtSigned(row.f_score)}</span>
      </div>
      <div className="pick-card-footer mono">
        <span className={(row.momentum_pct ?? 0) >= 0 ? "good" : "bad"}>MOM {momPct}</span>
        <span>{row.quadrant}</span>
      </div>
    </button>
  );
}
```

- [ ] **Step 2: Add PickCard CSS to `globals.css`**

Append to `globals.css`:

```css
/* ── PickCard ── */
.pick-card {
  background: var(--panel, #151d25);
  border: 1px solid var(--line, #2b3742);
  border-left: 3px solid var(--state-color, #666);
  border-radius: 6px;
  padding: 12px 14px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-left-color 150ms ease;
}

.pick-card:hover { border-left-color: var(--accent, #5fa8d3); }

.pick-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pick-card-ticker {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text, #f2f6f8);
}

.pick-card-pill {
  color: #fff;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  padding: 2px 9px;
  border-radius: 11px;
  line-height: 1.4;
}

.pick-card-class {
  font-size: 0.72rem;
  color: var(--muted, #a9bac5);
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.pick-card-scores {
  display: flex;
  gap: 12px;
  font-size: 0.82rem;
  font-weight: 500;
}

.pick-card-footer {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--muted, #a9bac5);
}

/* Light theme overrides for C and B shells */
.c-shell .pick-card,
.b-shell .pick-card {
  background: #fff;
  border-color: #e6e1d8;
  color: #1a1714;
}

.c-shell .pick-card-ticker,
.b-shell .pick-card-ticker { color: #1a1714; }

.c-shell .pick-card-class,
.b-shell .pick-card-class { color: #7a7066; }

.c-shell .pick-card-footer,
.b-shell .pick-card-footer { color: #7a7066; }
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | grep -E "PickCard|pick-card" | head -10
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/components/PickCard.tsx web/app/globals.css
git commit -m "feat: add PickCard component with sparkline, semantic state color, signed scores"
```

---

### Task 10: TransitionsBanner component

**Files:**
- Create: `web/components/TransitionsBanner.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create `web/components/TransitionsBanner.tsx`**

```typescript
// web/components/TransitionsBanner.tsx
import type { SnapshotTransition } from "../lib/api";
import { stateColor, stateShortLabel } from "../lib/state-colors";

function compactLabel(state: string): string {
  return stateShortLabel(state) || state.replaceAll("_", " ");
}

function TransitionRow({
  transition,
  onSelect,
  light,
}: {
  transition: SnapshotTransition;
  onSelect: (ticker: string) => void;
  light: boolean;
}) {
  const dotColor = stateColor(transition.to, light);
  return (
    <button
      type="button"
      className="transition-row mono"
      onClick={() => onSelect(transition.ticker)}
      title={`${transition.ticker}: ${transition.from} → ${transition.to} on ${transition.date || "unknown date"}`}
    >
      <span className="transition-dot" style={{ background: dotColor }} aria-hidden="true" />
      <strong className="transition-ticker">{transition.ticker}</strong>
      <span className="transition-text">
        {compactLabel(transition.from)} → {compactLabel(transition.to)}
      </span>
      <time className="transition-date">{transition.date || "—"}</time>
    </button>
  );
}

export default function TransitionsBanner({
  transitions,
  onSelect,
  light = false,
}: {
  transitions: SnapshotTransition[];
  onSelect: (ticker: string) => void;
  light?: boolean;
}) {
  if (!transitions.length) return null;
  const visible = transitions.slice(0, 8);

  return (
    <section className="transitions-banner" aria-label="Recent state transitions">
      <div className="transitions-banner-head">
        <span className="mono">Recent transitions</span>
        <span className="mono">last {visible.length}</span>
      </div>
      {visible.map((t) => (
        <TransitionRow
          key={`${t.ticker}-${t.from}-${t.to}-${t.date}`}
          transition={t}
          onSelect={onSelect}
          light={light}
        />
      ))}
    </section>
  );
}
```

- [ ] **Step 2: Add TransitionsBanner CSS to `globals.css`**

Append to `globals.css`:

```css
/* ── TransitionsBanner ── */
.transitions-banner {
  background: var(--panel, #151d25);
  border: 1px solid var(--line, #2b3742);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 16px;
}

.transitions-banner-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted, #a9bac5);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line, #2b3742);
  margin-bottom: 4px;
}

.transition-row {
  display: grid;
  grid-template-columns: 16px 64px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid var(--line, #2b3742);
  background: transparent;
  border-left: none;
  border-right: none;
  border-top: none;
  cursor: pointer;
  text-align: left;
  width: 100%;
  font-size: 0.84rem;
  color: var(--text, #f2f6f8);
}

.transition-row:last-child { border-bottom: none; }
.transition-row:hover { opacity: 0.8; }

.transition-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: block;
  flex-shrink: 0;
}

.transition-ticker { font-weight: 700; }

.transition-text { color: var(--muted, #a9bac5); font-size: 0.82rem; }

.transition-date {
  color: var(--muted, #a9bac5);
  font-size: 0.78rem;
  text-align: right;
}

/* Light theme overrides */
.c-shell .transitions-banner,
.b-shell .transitions-banner {
  background: #fff;
  border-color: #e6e1d8;
}

.c-shell .transitions-banner-head,
.b-shell .transitions-banner-head,
.c-shell .transition-row,
.b-shell .transition-row { border-color: #e6e1d8; }

.c-shell .transition-row,
.b-shell .transition-row { color: #1a1714; }

.c-shell .transition-text,
.b-shell .transition-text,
.c-shell .transition-date,
.b-shell .transition-date { color: #7a7066; }
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | grep -E "Transitions|transition" | head -10
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/components/TransitionsBanner.tsx web/app/globals.css
git commit -m "feat: add TransitionsBanner — 8-row state changes panel with semantic dot colors"
```

---

## Layer 4 — Overview Polish

### Task 11: StatusTiles component

**Files:**
- Create: `web/components/StatusTiles.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create `web/components/StatusTiles.tsx`**

```typescript
// web/components/StatusTiles.tsx
import type { DashboardSnapshotPayload } from "../lib/api";

type TileProps = {
  label: string;
  value: string;
  sub: string;
  valueColor?: string;
};

function Tile({ label, value, sub, valueColor }: TileProps) {
  return (
    <div className="status-tile">
      <span className="status-tile-label">{label}</span>
      <span className="status-tile-value mono" style={valueColor ? { color: valueColor } : undefined}>
        {value}
      </span>
      <span className="status-tile-sub mono">{sub}</span>
    </div>
  );
}

export default function StatusTiles({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload;
}) {
  const warnings = (snapshot.summary.state_counts.WARNING ?? 0) +
                   (snapshot.summary.state_counts.EXIT ?? 0);
  const bullish  = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;

  const regime       = warnings > bullish ? "CAUTION" : "RISK-ON";
  const regimeColor  = warnings > bullish ? "#ef4f4a" : "#26d65b";

  const cyclePhase   = String(snapshot.run?.metadata?.cycle_phase ?? "—").toUpperCase();
  const cycleDanger  = ["LATE", "RECESS"].includes(cyclePhase);
  const cycleColor   = cycleDanger ? "#e6b450" : undefined;

  const warningColor = warnings > 0 ? "#ef4f4a" : "#26d65b";

  return (
    <div className="status-tiles" aria-label="Dashboard status summary">
      <Tile
        label="Risk Regime"
        value={regime}
        sub={`${warnings} warning rows`}
        valueColor={regimeColor}
      />
      <Tile
        label="Cycle Phase"
        value={cyclePhase}
        sub="run-journal context"
        valueColor={cycleColor}
      />
      <Tile
        label="Active Warnings"
        value={String(warnings)}
        sub="warning + exit rows"
        valueColor={warningColor}
      />
    </div>
  );
}
```

- [ ] **Step 2: Add StatusTiles CSS to `globals.css`**

Append to `globals.css`:

```css
/* ── StatusTiles ── */
.status-tiles {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.status-tile {
  background: var(--panel, #151d25);
  border: 1px solid var(--line, #2b3742);
  border-radius: 6px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.status-tile-label {
  font-family: var(--font-sans, sans-serif);
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted, #a9bac5);
}

.status-tile-value {
  font-size: 1.4rem;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text, #f2f6f8);
}

.status-tile-sub {
  font-size: 0.78rem;
  color: var(--muted, #a9bac5);
}

/* Light theme overrides */
.c-shell .status-tile,
.b-shell .status-tile { background: #fff; border-color: #e6e1d8; }

.c-shell .status-tile-label,
.b-shell .status-tile-label { color: #7a7066; }

.c-shell .status-tile-value,
.b-shell .status-tile-value { color: #1a1714; }

.c-shell .status-tile-sub,
.b-shell .status-tile-sub { color: #7a7066; }

@media (max-width: 767px) {
  .status-tiles { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/StatusTiles.tsx web/app/globals.css
git commit -m "feat: add StatusTiles — 3-tile row (Regime / Phase / Warnings)"
```

---

### Task 12: PicksGrid component

**Files:**
- Create: `web/components/PicksGrid.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create `web/components/PicksGrid.tsx`**

```typescript
// web/components/PicksGrid.tsx
import type { SnapshotRow } from "../lib/api";
import PickCard from "./PickCard";

function selectPicks(rows: SnapshotRow[]): SnapshotRow[] {
  const bullish = rows
    .filter((r) => r.state === "STAGE_2_BULLISH")
    .sort((a, b) => b.s_score - a.s_score);
  const hold = rows
    .filter((r) => r.state === "HOLD")
    .sort((a, b) => b.s_score - a.s_score);
  return [...bullish, ...hold].slice(0, 8);
}

export default function PicksGrid({
  rows,
  light = false,
  onSelect,
}: {
  rows: SnapshotRow[];
  light?: boolean;
  onSelect: (ticker: string) => void;
}) {
  const picks = selectPicks(rows);

  return (
    <section className="picks-grid-section" aria-label="Active picks">
      <div className="picks-grid-head">
        <strong className="mono">Active Picks</strong>
        {picks.length > 0 ? (
          <span className="picks-grid-count mono">{picks.length}</span>
        ) : null}
      </div>
      {picks.length > 0 ? (
        <div className="picks-grid">
          {picks.map((row) => (
            <PickCard key={row.ticker} row={row} light={light} onSelect={onSelect} />
          ))}
        </div>
      ) : (
        <p className="picks-grid-empty">
          No active picks — all instruments below conviction threshold.
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Add PicksGrid CSS to `globals.css`**

Append to `globals.css`:

```css
/* ── PicksGrid ── */
.picks-grid-section { margin-bottom: 24px; }

.picks-grid-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.picks-grid-head strong {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted, #a9bac5);
}

.picks-grid-count {
  font-size: 0.72rem;
  color: var(--muted, #a9bac5);
  background: var(--line, #2b3742);
  border-radius: 4px;
  padding: 1px 6px;
}

.picks-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.picks-grid-empty {
  color: var(--muted, #a9bac5);
  font-style: italic;
  font-size: 0.9rem;
  padding: 12px 0;
}

@media (max-width: 1199px) {
  .picks-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 767px) {
  .picks-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/PicksGrid.tsx web/app/globals.css
git commit -m "feat: add PicksGrid — 4-up pick cards above heatmap, BULLISH then HOLD by s_score"
```

---

### Task 13: Wire A and C overview screens

Integrate `StatusTiles`, `TransitionsBanner`, and `PicksGrid` into `AOverviewScreen` and `COverviewScreen` in `dashboard-screens-client.tsx`.

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Add component imports at the top of `dashboard-screens-client.tsx`**

After the existing import for `chart-primitives`, add:

```typescript
import StatusTiles from "../components/StatusTiles";
import TransitionsBanner from "../components/TransitionsBanner";
import PicksGrid from "../components/PicksGrid";
```

- [ ] **Step 2: Update `AOverviewScreen`**

Find the `AOverviewScreen` function. After the opening `<section className="a-screen">` tag and `<ABlufStrip>`, and before the `<AStatusStrip>`, add the three new components. Replace `<AStatusStrip>` entirely with `<StatusTiles>`:

```typescript
function AOverviewScreen({
  snapshot,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const actions = snapshot.screens.overview?.actions ?? [];
  const transitions = snapshot.screens.overview?.transitions ?? [];
  const positions = snapshot.screens.overview?.positions ?? [];
  const warningPositions = positions.filter((position) => {
    const row = rowByTicker(snapshot.rows, position.ticker);
    return row && ["WARNING", "EXIT", "BEARISH_STAGE_4"].includes(row.state);
  });
  const navigate = (ticker: string) => {
    onSelectTicker(ticker);
    setActiveScreen("deepdive");
  };
  return (
    <section className="a-screen">
      <ABlufStrip snapshot={snapshot} />
      <StatusTiles snapshot={snapshot} />
      <TransitionsBanner
        transitions={transitions}
        onSelect={navigate}
        light={false}
      />
      <PicksGrid rows={snapshot.rows} light={false} onSelect={navigate} />
      <div className="a-body-grid">
        <ATerminalHeatmap rows={snapshot.rows} onSelectTicker={navigate} />
        <aside className="a-right-rail">
          <section className="a-panel">
            <div className="a-section-head">
              <strong>TRANSITIONS</strong>
              <span>latest saved decisions</span>
              <em>{actions.length} EVENTS</em>
            </div>
            {actions.slice(0, 9).map((decision) => (
              <button type="button" className="a-transition-row" key={`${decision.ticker}-${decision.action}`} onClick={() => navigate(decision.ticker)}>
                <i className={statusClass(decision.action)} />
                <strong>{decision.ticker}</strong>
                <span>{decision.action}</span>
                <em>{decision.rationale || `state=${decision.action}`}</em>
              </button>
            ))}
            {!actions.length ? <p className="a-empty">No saved decisions in the latest run.</p> : null}
          </section>
          <section className="a-panel">
            <div className="a-section-head">
              <strong>WATCHLIST | MY POSITIONS</strong>
              <span>saved local portfolio</span>
              <em>{positions.length} HOLDINGS</em>
            </div>
            {positions.slice(0, 6).map((position) => {
              const row = rowByTicker(snapshot.rows, position.ticker);
              return (
                <button type="button" className="a-position-row" key={`${position.source_name}-${position.ticker}`} onClick={() => navigate(position.ticker)}>
                  <i className={stateToneForClass(row?.state || "")} />
                  <strong>{position.ticker}</strong>
                  <span>{position.identity}</span>
                  <em>{row?.state.replaceAll("_", " ") || "not in universe"}</em>
                </button>
              );
            })}
            <p className="a-callout">
              {warningPositions.length
                ? `Action this week: ${warningPositions.map((p) => p.ticker).join(", ")} need review because they are in WARNING/EXIT gates.`
                : "No saved position is currently in a warning/exit state."}
            </p>
          </section>
        </aside>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Update `COverviewScreen`**

Find the `COverviewScreen` function. Add `StatusTiles`, `TransitionsBanner` (replacing the existing right-rail transitions card), and `PicksGrid` above the `PillarHeatmap`. The right rail keeps positions and bullish cohort but its transitions card is removed (since `TransitionsBanner` handles it at the top level).

```typescript
function COverviewScreen({
  snapshot,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const actions = snapshot.screens.overview?.actions ?? [];
  const transitions = snapshot.screens.overview?.transitions ?? [];
  const positions = snapshot.screens.overview?.positions ?? [];
  const bullish = snapshot.rows.filter((row) => row.state === "STAGE_2_BULLISH").slice(0, 8);
  const navigate = (ticker: string) => {
    onSelectTicker(ticker);
    setActiveScreen("deepdive");
  };
  return (
    <section className="c-screen c-overview-screen" aria-label="Display C heatmap overview">
      <CWeatherStrip snapshot={snapshot} />
      <div className="c-status-block">
        <StatusTiles snapshot={snapshot} />
        <TransitionsBanner transitions={transitions} onSelect={navigate} light={true} />
        <PicksGrid rows={snapshot.rows} light={true} onSelect={navigate} />
      </div>
      <div className="c-overview-grid">
        <PillarHeatmap
          rows={snapshot.rows}
          sourceNote={`Provider: ${snapshot.run?.provider || "unknown"}. Rows: ${snapshot.summary.universe_count}. Decisions: ${snapshot.decisions.length}.`}
          onSelectTicker={navigate}
        />
        <aside className="c-right-rail">
          <div className="c-rail-card">
            <div className="c-sec-head">
              <strong>Your positions</strong>
              <span>{positions.length ? `${positions.length} saved` : "not connected"}</span>
            </div>
            {positions.slice(0, 6).map((position) => (
              <PositionRailRow key={`${position.source_name}-${position.ticker}`} position={position} />
            ))}
            {!positions.length ? (
              <p className="c-rail-empty">No saved local portfolio available yet.</p>
            ) : null}
          </div>
          <div className="c-rail-card">
            <div className="c-sec-head"><strong>Bullish cohort</strong><span>{bullish.length} rows</span></div>
            {bullish.map((row) => (
              <button type="button" className="c-cohort-row" key={row.ticker} onClick={() => navigate(row.ticker)}>
                <strong>{row.ticker}</strong>
                <span>{row.identity}</span>
                <em>{fmt(row.s_score)}</em>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add `.c-status-block` layout CSS to `globals.css`**

Append to `globals.css`:

```css
.c-status-block {
  padding: 20px 32px 0;
}
```

- [ ] **Step 5: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | head -30
```
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add web/app/dashboard-screens-client.tsx web/app/globals.css
git commit -m "feat: wire StatusTiles + TransitionsBanner + PicksGrid into A and C overview screens"
```

---

### Task 14: Wire B overview screen

`BOverviewScreen` keeps its editorial layout. Add `TransitionsBanner` above the transition stories. `StatusTiles` and `PicksGrid` are **not** added — B already has a "By the numbers" sidebar.

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Update `BOverviewScreen`**

Find `BOverviewScreen`. Locate the `<BSectionRule title="This week's transitions" ...>` element. Replace it with `<TransitionsBanner>`:

```typescript
// Inside BOverviewScreen, inside <main>, replace:
//   <BSectionRule title="This week's transitions" sub="..." />
//   {stories.map(...)}
// with:

<TransitionsBanner
  transitions={snapshot.screens.overview?.transitions ?? []}
  onSelect={(ticker) => {
    onSelectTicker(ticker);
    setActiveScreen("deepdive");
  }}
  light={true}
/>
{stories.map((decision) => {
  const row = rowByTicker(snapshot.rows, decision.ticker);
  return (
    <article className="b-story" key={`${decision.ticker}-${decision.action}`}>
      <button type="button" onClick={() => {
        onSelectTicker(decision.ticker);
        setActiveScreen("deepdive");
      }}>
        <span>{decision.ticker} | {decision.identity || row?.identity || "instrument"}</span>
        <h3>{decision.ticker}: {decision.action.replaceAll("_", " ").toLowerCase()}.</h3>
      </button>
      <p>{decision.rationale || (row ? fieldNarrative(row) : "Latest saved decision has no additional rationale.")}</p>
      {row ? <em>S {fmt(row.s_score)} / F {fmt(row.f_score)} / RRG {row.quadrant}</em> : null}
    </article>
  );
})}
```

Note: the `stories` derivation above `BOverviewScreen`'s JSX remains unchanged.

- [ ] **Step 2: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors

- [ ] **Step 3: Full build check**

```bash
cd web && npm run build 2>&1 | tail -30
```
Expected: build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add web/app/dashboard-screens-client.tsx
git commit -m "feat: add TransitionsBanner to B editorial overview above transition stories"
```

---

### Task 15: Final verification

- [ ] **Step 1: Start dev server and verify Display C (default)**

```bash
cd web && npm run dev
```

Open `http://localhost:3000`. Confirm:
- Loads Display C (Pillar Stack) directly — no health tables
- DisplayToolbar visible at top: Terminal / Brief / Pillar Stack
- StatusTiles: 3 tiles (Risk Regime, Cycle Phase, Active Warnings)
- TransitionsBanner visible below tiles (or absent if no transitions in snapshot)
- PicksGrid: 4-up cards with sparklines below banner
- 7-pillar heatmap below picks grid

- [ ] **Step 2: Verify Display A (Terminal)**

Click "Terminal" in the toolbar. Confirm:
- Dark terminal theme loads
- StatusTiles present with dark panel style
- TransitionsBanner in dark style
- PicksGrid with dark PickCards
- Sparklines show state-encoded shapes

- [ ] **Step 3: Verify Display B (Editorial)**

Click "Brief". Confirm:
- Editorial/newspaper layout loads
- TransitionsBanner appears above transition stories
- No StatusTiles (correct — B keeps its own "By the numbers")
- No PicksGrid (correct)

- [ ] **Step 4: Verify state colors**

Inspect a state pill on any display. Confirm:
- `STAGE_2_BULLISH` → green (#1A8A4E dark / #2E8B57 light)
- `HOLD` → blue (#5C9DCB dark / #3A78B4 light) — **not** the same as green
- `WARNING` → amber
- `EXIT` → red-orange
- `BEARISH_STAGE_4` → dark red (distinct from EXIT)

- [ ] **Step 5: Verify font rendering**

Inspect any numeric value (S-score, F-score, momentum %). Confirm it renders in JetBrains Mono (monospaced with tabular figures). Confirm prose/labels render in Inter.

- [ ] **Step 6: Verify /admin**

Open `http://localhost:3000/admin`. Confirm:
- Health tables visible
- Portfolio analyzer visible
- Backtest panel visible
- DisplayToolbar is visible (it's in the root layout above all pages)

- [ ] **Step 7: Verify display persistence**

Switch to Display A. Refresh the page. Confirm Display A is still active (localStorage preserved).

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "chore: dashboard design recovery complete

Layer 1: DisplayShell + DisplayToolbar + /admin route
Layer 2: Inter + JetBrains Mono, 6-state semantic colors, .mono utility
Layer 3: Sparkline, PickCard, TransitionsBanner components
Layer 4: StatusTiles, PicksGrid, wired into A/B/C overview screens

Closes design drift identified in 2026-06-11 audit."
```
