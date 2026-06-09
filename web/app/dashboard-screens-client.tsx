"use client";

import { useMemo, useState } from "react";
import type { DashboardSnapshotPayload, SnapshotDecision, SnapshotRow } from "../lib/api";
import { FlowRiver, MomentumBars, PillarHeatmap, RrgChart, WaterfallChart } from "./chart-primitives";

type ScreenId = "overview" | "deepdive" | "rotation";
type SortKey = "ticker" | "state" | "quadrant" | "s_score" | "f_score" | "rs_ratio" | "rs_momentum" | "momentum_pct" | "cmf21";
type SortDirection = "asc" | "desc";

const SCREENS: { id: ScreenId; label: string; title: string }[] = [
  { id: "overview", label: "A", title: "Overview" },
  { id: "deepdive", label: "B", title: "Deep Dive" },
  { id: "rotation", label: "C", title: "Rotation" },
];

const QUADRANTS = ["Leading", "Weakening", "Lagging", "Improving", "Unknown"];

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "healthy" || normalized === "info" || normalized.includes("bullish") || normalized === "buy") return "good";
  if (normalized === "stale" || normalized.includes("bearish") || normalized === "sell") return "bad";
  return "warn";
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${statusClass(status)}`}>{status || "unknown"}</span>;
}

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function valueForSort(row: SnapshotRow, key: SortKey): string | number {
  if (key === "ticker" || key === "state" || key === "quadrant") return String(row[key] ?? "");
  const value = row[key];
  return typeof value === "number" ? value : Number.NEGATIVE_INFINITY;
}

function sortRows(rows: SnapshotRow[], key: SortKey, direction: SortDirection): SnapshotRow[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = valueForSort(a, key);
    const bv = valueForSort(b, key);
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * multiplier;
    return String(av).localeCompare(String(bv)) * multiplier;
  });
}

function rowByTicker(rows: SnapshotRow[], ticker: string): SnapshotRow | null {
  const normalized = ticker.toUpperCase();
  return rows.find((row) => row.ticker === normalized) ?? null;
}

function fieldNarrative(row: SnapshotRow): string {
  const momentum = row.momentum_pct === null || row.momentum_pct === undefined
    ? "momentum is unavailable"
    : `momentum is ${fmt(row.momentum_pct * 100, 1)}%`;
  const flow = row.cmf21 === null || row.cmf21 === undefined
    ? "CMF flow is unavailable"
    : `CMF flow is ${fmt(row.cmf21, 2)}`;
  return `${row.display_label}: S ${fmt(row.s_score)}, F ${fmt(row.f_score)}, ${momentum}, ${flow}, RRG ${row.quadrant}.`;
}

function SnapshotCard({
  row,
  selected,
  onSelect,
}: {
  row: SnapshotRow;
  selected: boolean;
  onSelect: (ticker: string) => void;
}) {
  return (
    <button
      type="button"
      className={`snapshot-card interactive-card ${selected ? "selected" : ""}`}
      onClick={() => onSelect(row.ticker)}
      aria-pressed={selected}
      title={fieldNarrative(row)}
    >
      <div>
        <strong>{row.display_label}</strong>
        <span>{row.asset_class} | {row.quadrant}</span>
      </div>
      <StatusPill status={row.state} />
      <dl>
        <div><dt>S</dt><dd>{fmt(row.s_score)}</dd></div>
        <div><dt>F</dt><dd>{fmt(row.f_score)}</dd></div>
        <div><dt>RS-R</dt><dd>{fmt(row.rs_ratio, 1)}</dd></div>
        <div><dt>RS-M</dt><dd>{fmt(row.rs_momentum, 1)}</dd></div>
      </dl>
    </button>
  );
}

function ActionRow({ decision, onSelect }: { decision: SnapshotDecision; onSelect: (ticker: string) => void }) {
  return (
    <button type="button" className="action-row interactive-card" onClick={() => onSelect(decision.ticker)}>
      <StatusPill status={decision.action} />
      <strong>{decision.ticker} | {decision.identity}</strong>
      <span>{decision.rationale || "No rationale recorded."}</span>
    </button>
  );
}

function SortControl({
  sortKey,
  sortDirection,
  onChange,
}: {
  sortKey: SortKey;
  sortDirection: SortDirection;
  onChange: (key: SortKey, direction: SortDirection) => void;
}) {
  return (
    <div className="sort-controls" aria-label="Sort snapshot rows">
      <label>
        Sort
        <select value={sortKey} onChange={(event) => onChange(event.target.value as SortKey, sortDirection)}>
          <option value="s_score">S score</option>
          <option value="f_score">F score</option>
          <option value="rs_ratio">RS ratio</option>
          <option value="rs_momentum">RS momentum</option>
          <option value="momentum_pct">Momentum</option>
          <option value="cmf21">CMF flow</option>
          <option value="ticker">Ticker</option>
          <option value="state">State</option>
          <option value="quadrant">Quadrant</option>
        </select>
      </label>
      <button type="button" onClick={() => onChange(sortKey, sortDirection === "asc" ? "desc" : "asc")}>
        {sortDirection === "asc" ? "Ascending" : "Descending"}
      </button>
    </div>
  );
}

function OverviewScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("s_score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const leaders = snapshot.screens.overview?.leaders ?? [];
  const risks = snapshot.screens.overview?.risks ?? [];
  const actions = snapshot.screens.overview?.actions ?? [];
  const sortedLeaders = useMemo(() => sortRows(leaders, sortKey, sortDirection).slice(0, 8), [leaders, sortKey, sortDirection]);
  const sortedRisks = useMemo(() => sortRows(risks, sortKey, sortDirection).slice(0, 8), [risks, sortKey, sortDirection]);

  return (
    <section className="screen-section" aria-label="Display A overview">
      <div className="section-heading">
        <div>
          <h2>A | Overview</h2>
          <span>{snapshot.summary.universe_count} instruments | selected {selectedTicker}</span>
        </div>
        <SortControl sortKey={sortKey} sortDirection={sortDirection} onChange={(key, direction) => {
          setSortKey(key);
          setSortDirection(direction);
        }} />
      </div>
      <div className="snapshot-columns">
        <div>
          <h3>Leaders</h3>
          {sortedLeaders.map((row) => (
            <SnapshotCard key={row.ticker} row={row} selected={row.ticker === selectedTicker} onSelect={onSelectTicker} />
          ))}
        </div>
        <div>
          <h3>Risk Queue</h3>
          {sortedRisks.map((row) => (
            <SnapshotCard key={row.ticker} row={row} selected={row.ticker === selectedTicker} onSelect={onSelectTicker} />
          ))}
        </div>
        <div>
          <h3>Actions</h3>
          {actions.slice(0, 8).map((decision) => (
            <ActionRow key={`${decision.action}-${decision.ticker}`} decision={decision} onSelect={onSelectTicker} />
          ))}
          {!actions.length ? <p className="subtle">No BLUF decisions in the latest journal snapshot.</p> : null}
        </div>
      </div>
      <div className="screen-chart-row">
        <PillarHeatmap rows={snapshot.rows} onSelectTicker={onSelectTicker} />
      </div>
    </section>
  );
}

function DeepDiveScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const focus = rowByTicker(snapshot.rows, selectedTicker) ?? snapshot.focus;
  const peers = snapshot.screens.deepdive?.peer_rows ?? snapshot.rows.slice(0, 12);
  const pillars = Object.entries(focus?.pillar_scores ?? {}).slice(0, 12);

  return (
    <section className="screen-section" aria-label="Display B deep dive">
      <div className="section-heading">
        <div>
          <h2>B | Deep Dive</h2>
          <span>{focus?.display_label || "No focus ticker"}</span>
        </div>
        <label className="ticker-select">
          Ticker focus
          <select value={selectedTicker} onChange={(event) => onSelectTicker(event.target.value)}>
            {snapshot.rows.map((row) => (
              <option value={row.ticker} key={row.ticker}>
                {row.display_label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {focus ? (
        <div className="deep-grid">
          <SnapshotCard row={focus} selected onSelect={onSelectTicker} />
          <div className="pillar-list" aria-label="Pillar score matrix">
            {pillars.map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <strong>{typeof value === "number" ? fmt(value, 3) : String(value)}</strong>
              </div>
            ))}
          </div>
          <p>
            {fieldNarrative(focus)} The current label combines trend, relative strength,
            momentum, and flow values from the latest saved dashboard run.
          </p>
          <div className="peer-strip" aria-label="Peer ticker selector">
            {peers.slice(0, 12).map((row) => (
              <button
                type="button"
                key={row.ticker}
                className={row.ticker === selectedTicker ? "selected" : ""}
                onClick={() => onSelectTicker(row.ticker)}
              >
                {row.ticker}
              </button>
            ))}
          </div>
          <div className="deep-chart-row">
            <WaterfallChart row={focus} />
          </div>
        </div>
      ) : (
        <p className="subtle padded">Run a dashboard refresh to persist a focus row.</p>
      )}
    </section>
  );
}

function RotationScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const sectors = snapshot.screens.rotation?.sectors ?? [];
  const counts = snapshot.summary.quadrant_counts ?? {};
  const firstNonEmpty = QUADRANTS.find((quadrant) => sectors.some((row) => row.quadrant === quadrant)) ?? "Leading";
  const [selectedQuadrant, setSelectedQuadrant] = useState(firstNonEmpty);
  const selectedRows = sectors.filter((row) => row.quadrant === selectedQuadrant);

  return (
    <section className="screen-section" aria-label="Display C rotation">
      <div className="section-heading">
        <div>
          <h2>C | Rotation</h2>
          <span>{sectors.length} sector rows | {selectedQuadrant}</span>
        </div>
        <label className="ticker-select">
          Quadrant
          <select value={selectedQuadrant} onChange={(event) => setSelectedQuadrant(event.target.value)}>
            {QUADRANTS.map((quadrant) => (
              <option value={quadrant} key={quadrant}>
                {quadrant} ({counts[quadrant] ?? 0})
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="rotation-grid">
        {QUADRANTS.map((quadrant) => (
          <button
            type="button"
            className={`quadrant-box ${selectedQuadrant === quadrant ? "selected" : ""}`}
            key={quadrant}
            onClick={() => setSelectedQuadrant(quadrant)}
            aria-pressed={selectedQuadrant === quadrant}
          >
            <strong>{quadrant}</strong>
            <span>{counts[quadrant] ?? 0}</span>
            <ul>
              {sectors
                .filter((row) => row.quadrant === quadrant)
                .slice(0, 5)
                .map((row) => (
                  <li key={row.ticker}>{row.ticker} | {row.identity}</li>
                ))}
            </ul>
          </button>
        ))}
      </div>
      <div className="rotation-chart-grid">
        <RrgChart rows={sectors} onSelectTicker={onSelectTicker} />
        <MomentumBars rows={sectors} onSelectTicker={onSelectTicker} />
      </div>
      <div className="screen-chart-row">
        <FlowRiver rows={sectors} />
      </div>
      <div className="rotation-detail" aria-label="Selected quadrant instrument list">
        <div className="section-heading compact">
          <h3>{selectedQuadrant} instruments</h3>
          <span>Click a row to use it as the deep-dive focus</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Identity</th>
                <th>State</th>
                <th>S</th>
                <th>F</th>
                <th>RS Ratio</th>
                <th>RS Momentum</th>
              </tr>
            </thead>
            <tbody>
              {selectedRows.map((row) => (
                <tr
                  key={row.ticker}
                  className={row.ticker === selectedTicker ? "selected-row" : ""}
                  onClick={() => onSelectTicker(row.ticker)}
                >
                  <td><strong>{row.ticker}</strong></td>
                  <td>{row.identity}</td>
                  <td><StatusPill status={row.state} /></td>
                  <td>{fmt(row.s_score)}</td>
                  <td>{fmt(row.f_score)}</td>
                  <td>{fmt(row.rs_ratio, 1)}</td>
                  <td>{fmt(row.rs_momentum, 1)}</td>
                </tr>
              ))}
              {!selectedRows.length ? (
                <tr>
                  <td colSpan={7}>No instruments are currently in this quadrant.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default function DashboardScreensClient({ snapshot }: { snapshot: DashboardSnapshotPayload | null }) {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("overview");
  const initialTicker = snapshot?.focus?.ticker || snapshot?.rows[0]?.ticker || "";
  const [selectedTicker, setSelectedTicker] = useState(initialTicker);

  if (!snapshot || snapshot.status === "empty") {
    return (
      <section className="screen-section" aria-label="Dashboard snapshot unavailable">
        <div className="section-heading">
          <h2>A/B/C Screens</h2>
          <span>No persisted snapshot</span>
        </div>
        <p className="subtle padded">{snapshot?.message || "Run a dashboard refresh to create a journal-backed snapshot."}</p>
      </section>
    );
  }

  return (
    <div className="screen-stack">
      <nav className="screen-tabs" aria-label="Dashboard display selector">
        {SCREENS.map((screen) => (
          <button
            type="button"
            key={screen.id}
            className={activeScreen === screen.id ? "selected" : ""}
            onClick={() => setActiveScreen(screen.id)}
            aria-pressed={activeScreen === screen.id}
          >
            <strong>{screen.label}</strong>
            <span>{screen.title}</span>
          </button>
        ))}
      </nav>
      {activeScreen === "overview" ? (
        <OverviewScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
      {activeScreen === "deepdive" ? (
        <DeepDiveScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
      {activeScreen === "rotation" ? (
        <RotationScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
    </div>
  );
}
