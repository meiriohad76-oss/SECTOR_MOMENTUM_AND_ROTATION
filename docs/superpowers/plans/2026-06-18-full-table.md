# Full 7-Pillar Matrix Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sortable full-universe table (all tickers × 7 pillar scores) to the C1 overview screen as a collapsible `<details>` panel.

**Architecture:** Pure frontend. All data is already in `snapshot.rows[]` from `/api/v1/dashboard-snapshot` — no backend changes. New `FullTable` component uses client-side sort state. Placed in `COverviewScreen` below the heatmap using the existing `<details>/<summary>` collapsed panel pattern.

**Tech Stack:** TypeScript, React (client component), CSS. No frontend test framework — verification is `tsc --noEmit` from `web/`.

---

## File Map

| File | Role |
|---|---|
| `web/components/FullTable.tsx` | New sortable table component |
| `web/app/globals.css` | Table styles |
| `web/app/dashboard-screens-client.tsx` | Wire `FullTable` into `COverviewScreen` |

---

## Task 1: Create `FullTable` component

**Files:**
- Create: `web/components/FullTable.tsx`

- [ ] **Step 1: Create the component file**

Create `web/components/FullTable.tsx` with this content:

```tsx
// web/components/FullTable.tsx
"use client";
import { useState } from "react";
import type { SnapshotRow } from "../lib/api";
import { stateColor, stateShortLabel } from "../lib/state-colors";

const PILLARS = [
  "cmf21",
  "mom_12_1",
  "rs_ratio",
  "mansfield_rs",
  "breadth_50d",
  "cycle_tilt",
  "rs_momentum",
] as const;

const PILLAR_LABELS: Record<string, string> = {
  cmf21:        "CMF",
  mom_12_1:     "MOM",
  rs_ratio:     "RS-R",
  mansfield_rs: "MRS",
  breadth_50d:  "BRD",
  cycle_tilt:   "CYC",
  rs_momentum:  "RS-M",
};

type SortKey =
  | "ticker"
  | "asset_class"
  | "state"
  | "s_score"
  | "f_score"
  | (typeof PILLARS)[number];

function fmtCell(v: number | string | boolean | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isFinite(v) ? v.toFixed(2) : "—";
  return String(v);
}

function sortValue(
  row: SnapshotRow,
  key: SortKey
): string | number | null {
  if (key === "ticker")      return row.ticker;
  if (key === "asset_class") return row.asset_class;
  if (key === "state")       return row.state;
  if (key === "s_score")     return row.s_score;
  if (key === "f_score")     return row.f_score;
  const pv = row.pillar_scores[key];
  return typeof pv === "number" ? pv : null;
}

export default function FullTable({ rows }: { rows: SnapshotRow[] }) {
  const [sortKey, setSortKey]   = useState<SortKey>("s_score");
  const [sortAsc, setSortAsc]   = useState(false);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      // Text columns default ascending; numeric columns default descending
      setSortAsc(key === "ticker" || key === "asset_class" || key === "state");
    }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = sortValue(a, sortKey);
    const bv = sortValue(b, sortKey);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    if (typeof av === "string" && typeof bv === "string") {
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sortAsc
      ? (av as number) - (bv as number)
      : (bv as number) - (av as number);
  });

  const columns: { key: SortKey; label: string }[] = [
    { key: "ticker",      label: "Ticker"  },
    { key: "asset_class", label: "Class"   },
    { key: "state",       label: "State"   },
    { key: "s_score",     label: "S"       },
    { key: "f_score",     label: "F"       },
    ...PILLARS.map((p) => ({ key: p as SortKey, label: PILLAR_LABELS[p] ?? p })),
  ];

  return (
    <details className="full-table-panel">
      <summary className="full-table-summary">
        All {rows.length} tickers — 7-pillar matrix
      </summary>
      <div className="full-table-scroll">
        <table className="full-table">
          <thead>
            <tr>
              {columns.map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => handleSort(key)}
                  className={sortKey === key ? "ft-sorted" : ""}
                  aria-sort={
                    sortKey === key
                      ? sortAsc
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  {label}
                  {sortKey === key ? (sortAsc ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.ticker}>
                <td className="ft-ticker">{row.ticker}</td>
                <td className="ft-class">{row.asset_class}</td>
                <td className="ft-state">
                  <span
                    className="state-pill mono"
                    style={{
                      background: stateColor(row.state),
                      color: "#fff",
                      padding: "1px 7px",
                      borderRadius: "9px",
                      fontSize: "0.68rem",
                      fontWeight: 600,
                      display: "inline-block",
                    }}
                  >
                    {stateShortLabel(row.state)}
                  </span>
                </td>
                <td className={`ft-num ${row.s_score >= 0 ? "ft-pos" : "ft-neg"}`}>
                  {fmtCell(row.s_score)}
                </td>
                <td className={`ft-num ${row.f_score >= 0 ? "ft-pos" : "ft-neg"}`}>
                  {fmtCell(row.f_score)}
                </td>
                {PILLARS.map((p) => {
                  const pv = row.pillar_scores[p];
                  const num = typeof pv === "number" ? pv : null;
                  return (
                    <td
                      key={p}
                      className={`ft-num ${num !== null ? (num >= 0 ? "ft-pos" : "ft-neg") : ""}`}
                    >
                      {fmtCell(pv)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

---

## Task 2: Add CSS styles

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Append table styles to globals.css**

Open `web/app/globals.css` and append the following block at the end of the file:

```css
/* ── Full 7-Pillar Matrix Table ───────────────────────── */
.full-table-panel {
  margin: 18px 0 0;
}
.full-table-summary {
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.65;
  padding: 6px 0;
  user-select: none;
}
.full-table-summary:hover {
  opacity: 1;
}
.full-table-scroll {
  overflow-x: auto;
  margin-top: 10px;
}
.full-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.75rem;
  font-family: var(--font-mono, monospace);
}
.full-table th {
  text-align: right;
  padding: 5px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.12);
  cursor: pointer;
  white-space: nowrap;
  font-weight: 600;
  opacity: 0.7;
  user-select: none;
}
.full-table th:first-child,
.full-table th:nth-child(2),
.full-table th:nth-child(3) {
  text-align: left;
}
.full-table th:hover,
.full-table th.ft-sorted {
  opacity: 1;
}
.full-table td {
  padding: 4px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  text-align: right;
  white-space: nowrap;
}
.full-table tbody tr:hover {
  background: rgba(255,255,255,0.04);
}
.ft-ticker { text-align: left; font-weight: 600; }
.ft-class  { text-align: left; opacity: 0.7; }
.ft-state  { text-align: left; }
.ft-num    { font-variant-numeric: tabular-nums; }
.ft-pos    { color: #4caf87; }
.ft-neg    { color: #e07070; }
```

- [ ] **Step 2: Verify TypeScript still compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

---

## Task 3: Wire `FullTable` into `COverviewScreen`

**Files:**
- Modify: `web/app/dashboard-screens-client.tsx`

- [ ] **Step 1: Add the import**

At the top of `web/app/dashboard-screens-client.tsx`, find the block of existing imports (around line 1–20). Add:

```tsx
import FullTable from "../components/FullTable";
```

- [ ] **Step 2: Find `COverviewScreen` and add `FullTable`**

In `dashboard-screens-client.tsx`, find `function COverviewScreen` (around line 984). Locate the JSX return statement. Find the closing `</section>` of the C1 overview screen.

Immediately before the closing `</section>`, add the `FullTable`:

```tsx
      <FullTable rows={snapshot.rows} />
    </section>
```

The exact insertion point: look for the last block inside the `<section className="c-screen c-overview-screen"` element. Add `<FullTable rows={snapshot.rows} />` as the last child before `</section>`.

- [ ] **Step 3: Verify TypeScript compiles**

```powershell
cd "c:\Users\meiri\momentum and flow\web"
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Smoke-check in browser**

With the dev server running at `http://localhost:3100/?presentation=c`:
- Open the page
- Scroll to the bottom of the C1 overview
- Click the "All N tickers — 7-pillar matrix" `<details>` toggle
- Verify the table expands and shows all tickers
- Click a column header — verify rows sort
- Click the same header again — verify sort direction reverses

- [ ] **Step 5: Commit**

```powershell
cd "c:\Users\meiri\momentum and flow"
git add web/components/FullTable.tsx web/app/globals.css web/app/dashboard-screens-client.tsx
git commit -m "feat: full 7-pillar matrix table on C1 overview — sortable, collapsed by default"
```
