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
