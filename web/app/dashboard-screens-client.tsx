"use client";

import { useEffect, useMemo, useState } from "react";
import { analyzePortfolio, deleteSavedPortfolio, fetchSavedPortfolios, fetchTickerChart, savePortfolio } from "../lib/api";
import type {
  BacktestArtifactsPayload,
  DashboardSnapshotPayload,
  PortfolioAnalysisPayload,
  PortfolioAnalysisRequest,
  SavedPortfolio,
  SnapshotDecision,
  SnapshotPosition,
  SnapshotRow,
  SnapshotTransition,
  TickerChartPayload,
} from "../lib/api";
import { FlowRiver, MomentumBars, PillarDetailGrid, PillarHeatmap, PillarStackBar, RrgChart, WaterfallChart } from "./chart-primitives";
import { stateColor, stateShortLabel } from "../lib/state-colors";
import StatusTiles from "../components/StatusTiles";
import TransitionsBanner from "../components/TransitionsBanner";
import PicksGrid from "../components/PicksGrid";

type ScreenId = "overview" | "deepdive" | "rotation";
type SortKey = "ticker" | "state" | "quadrant" | "s_score" | "f_score" | "rs_ratio" | "rs_momentum" | "momentum_pct" | "cmf21";
type SortDirection = "asc" | "desc";
type PresentationMode = "default" | "handoff-a" | "handoff-b" | "handoff-c" | "admin";

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

function compactStateText(state: string): string {
  const normalized = state.toUpperCase();
  if (normalized.includes("STAGE_2") || normalized.includes("BULLISH") || normalized === "BUY") return "BULLISH";
  if (normalized.includes("WARNING") || normalized.includes("WARN")) return "WARN";
  if (normalized.includes("EXIT")) return "EXIT";
  if (normalized.includes("BEAR")) return "BEAR";
  if (normalized.includes("BASE")) return "BASE";
  if (normalized.includes("HOLD")) return "HOLD";
  return state.replaceAll("_", " ");
}

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function pct(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function money(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function weightPct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

function payloadNumber(row: SnapshotRow, key: string): number | null {
  const value = row.payload[key] ?? row.pillar_scores[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function payloadBool(row: SnapshotRow, key: string): boolean | null {
  const value = row.payload[key] ?? row.pillar_scores[key];
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes", "y"].includes(normalized)) return true;
    if (["false", "0", "no", "n"].includes(normalized)) return false;
  }
  return null;
}

function passText(value: boolean | null) {
  if (value === true) return "pass";
  if (value === false) return "fail";
  return "n/a";
}

function toneForBool(value: boolean | null) {
  if (value === true) return "good";
  if (value === false) return "bad";
  return "warn";
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

function rowPressure(row: SnapshotRow): number {
  return row.f_score + (row.cmf21 ?? 0) + row.s_score * 0.35;
}

function flowNarrative(row: SnapshotRow): string {
  const cmf = row.cmf21 === null ? "CMF is unavailable" : `CMF ${fmt(row.cmf21, 2)}`;
  const flow = `F ${fmt(row.f_score, 2)}`;
  const score = `S ${fmt(row.s_score, 2)}`;
  if (rowPressure(row) > 0.35) {
    return `${flow}, ${cmf}, ${score}: flow is supporting the setup.`;
  }
  if (rowPressure(row) < -0.35) {
    return `${flow}, ${cmf}, ${score}: flow is pressuring the setup.`;
  }
  return `${flow}, ${cmf}, ${score}: flow evidence is mixed.`;
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
      <DataHealthPanel />
    </section>
  );
}

/** Inline data-health status rail shown in the default overview.
 *  Surfaces the two categories checked by the run-journal (persisted state +
 *  provider flow readiness) so analysts can spot stale inputs at a glance.
 *  Full health drill-down is available via /api/v1/data-health.
 */
function DataHealthPanel() {
  return (
    <section className="data-health-panel" aria-label="Persisted and provider data health">
      <div className="section-heading compact">
        <div>
          <h3>Persisted Data Health</h3>
          <span>Run-journal provenance — state, transitions, and backups</span>
        </div>
      </div>
      <div className="section-heading compact">
        <div>
          <h3>Provider Data Health</h3>
          {/* provider_flow_readiness is checked server-side via /api/v1/data-health */}
          <span>Provider Flow: API connection pending — run a live refresh to populate.</span>
        </div>
      </div>
    </section>
  );
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",").pop() || "" : result);
    };
    reader.onerror = () => reject(reader.error || new Error("File could not be read."));
    reader.readAsDataURL(file);
  });
}

function exposureEntries(values: Record<string, number>) {
  return Object.entries(values).sort((a, b) => b[1] - a[1]);
}

function BacktestArtifactPanel({ payload }: { payload: BacktestArtifactsPayload | null }) {
  const rows = payload?.equity.rows ?? [];
  const columns = payload?.equity.columns ?? [];
  const reportText = payload?.report.text || "";
  const reportPreview = reportText.split(/\r?\n/).filter(Boolean).slice(0, 8);
  const numericColumns = columns.filter((column) =>
    rows.some((row) => typeof row[column] === "number" && Number.isFinite(row[column] as number))
  );
  const primaryColumn = numericColumns.find((column) => column.toLowerCase().includes("method")) ?? numericColumns[0] ?? "";
  const sampledRows = rows.length > 60
    ? rows.filter((_, index) => index % Math.ceil(rows.length / 60) === 0).slice(0, 60)
    : rows;
  const values = sampledRows
    .map((row) => (typeof row[primaryColumn] === "number" ? row[primaryColumn] as number : null))
    .filter((value): value is number => value !== null && Number.isFinite(value));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const span = Math.max(max - min, 0.000001);
  const points = values.map((value, index) => {
    const x = values.length <= 1 ? 4 : 4 + (index / (values.length - 1)) * 292;
    const y = 72 - ((value - min) / span) * 56;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <details className="backtest-artifact-panel">
      <summary>
        <span>Backtest Lab</span>
        <strong>{payload?.status || "unavailable"}</strong>
        <em>{payload?.equity.row_count ?? 0} equity rows</em>
      </summary>
      {!payload ? (
        <p className="subtle padded">Backtest artifact API data is not available yet.</p>
      ) : (
        <div className="backtest-artifact-body">
          <div className="backtest-status-grid">
            {payload.artifacts.map((artifact) => (
              <div key={artifact.id}>
                <span>{artifact.label}</span>
                <strong className={statusClass(artifact.status)}>{artifact.status}</strong>
                <small>{artifact.path} | {artifact.bytes.toLocaleString()} bytes</small>
              </div>
            ))}
          </div>
          <div className="backtest-chart-grid">
            <div className="backtest-mini-chart">
              <div className="section-heading compact">
                <h3>Equity Artifact</h3>
                <span>{primaryColumn || "no numeric series"}</span>
              </div>
              {points ? (
                <svg viewBox="0 0 300 86" role="img" aria-label="Backtest equity artifact preview">
                  <path d="M4 72H296" />
                  <polyline points={points} />
                </svg>
              ) : (
                <p className="subtle padded">No numeric equity series is available in the artifact payload.</p>
              )}
            </div>
            <div className="backtest-report-preview">
              <div className="section-heading compact">
                <h3>Report Preview</h3>
                <span>{payload.message}</span>
              </div>
              {reportPreview.length ? (
                <ul>
                  {reportPreview.map((line, index) => (
                    <li key={`${index}-${line}`}>{line.replace(/^#+\s*/, "")}</li>
                  ))}
                </ul>
              ) : (
                <p className="subtle padded">No report text is available in the artifact payload.</p>
              )}
            </div>
          </div>
          <p className="portfolio-footnote">
            This panel reads manual backtest artifacts only. It does not run backtests, calibration, provider downloads, or live scoring.
          </p>
        </div>
      )}
    </details>
  );
}

function PortfolioAnalyzerPanel({ onSelectTicker }: { onSelectTicker: (ticker: string) => void }) {
  const [ticker, setTicker] = useState("");
  const [csvText, setCsvText] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileContentBase64, setFileContentBase64] = useState("");
  const [mode, setMode] = useState<"ticker" | "csv" | "file">("ticker");
  const [result, setResult] = useState<PortfolioAnalysisPayload | null>(null);
  const [lastRequest, setLastRequest] = useState<PortfolioAnalysisRequest | null>(null);
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([]);
  const [selectedSavedName, setSelectedSavedName] = useState("");
  const [portfolioName, setPortfolioName] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedLoading, setSavedLoading] = useState(false);

  useEffect(() => {
    void refreshSavedPortfolios();
  }, []);

  function currentRequest(): PortfolioAnalysisRequest {
    if (mode === "file") {
      return { file_name: fileName, content_base64: fileContentBase64 };
    }
    if (mode === "csv") {
      return { csv: csvText };
    }
    return { ticker };
  }

  async function refreshSavedPortfolios() {
    setSavedLoading(true);
    const response = await fetchSavedPortfolios();
    setSavedLoading(false);
    if (response.ok && response.data) {
      setSavedPortfolios(response.data.portfolios);
      setSelectedSavedName((current) => current || response.data?.portfolios[0]?.name || "");
    }
  }

  async function submit() {
    setError("");
    setSavedMessage("");
    setLoading(true);
    const request = currentRequest();
    const response = await analyzePortfolio(request);
    setLoading(false);
    if (!response.ok || !response.data) {
      setResult(null);
      setLastRequest(null);
      setError(response.error || "Portfolio analysis failed.");
      return;
    }
    setResult(response.data);
    setLastRequest(request);
    if (response.data.status === "invalid") {
      setError(response.data.input.errors.map((item) => item.message).join(" ") || response.data.message);
    }
  }

  async function saveCurrentPortfolio() {
    if (!lastRequest) {
      setSavedMessage("Analyze a ticker or portfolio before saving it.");
      return;
    }
    setSaving(true);
    setSavedMessage("");
    const response = await savePortfolio(portfolioName, lastRequest);
    setSaving(false);
    if (!response.ok || !response.data) {
      setSavedMessage(response.error || "Save failed.");
      return;
    }
    if (response.data.status !== "ready") {
      setSavedMessage(response.data.errors.map((item) => item.message).join(" ") || response.data.message);
      return;
    }
    setSavedMessage(response.data.message);
    setPortfolioName(response.data.portfolio?.name || portfolioName);
    setSelectedSavedName(response.data.portfolio?.name || selectedSavedName);
    await refreshSavedPortfolios();
  }

  async function loadSavedPortfolio() {
    const selected = savedPortfolios.find((item) => item.name === selectedSavedName);
    if (!selected) {
      setSavedMessage("Select a saved portfolio to load.");
      return;
    }
    const request: PortfolioAnalysisRequest = { holdings: selected.holdings };
    setLoading(true);
    setSavedMessage("");
    const response = await analyzePortfolio(request);
    setLoading(false);
    if (!response.ok || !response.data) {
      setError(response.error || "Saved portfolio analysis failed.");
      return;
    }
    setMode("csv");
    setCsvText(selected.holdings.map((holding) => `${holding.ticker},${holding.weight ?? ""}`).join("\n"));
    setPortfolioName(selected.name);
    setLastRequest(request);
    setResult(response.data);
    setSavedMessage(`Loaded ${selected.name}.`);
    setError(response.data.status === "invalid" ? response.data.message : "");
  }

  async function deleteSelectedSavedPortfolio() {
    if (!selectedSavedName) {
      setSavedMessage("Select a saved portfolio to delete.");
      return;
    }
    setSaving(true);
    const response = await deleteSavedPortfolio(selectedSavedName);
    setSaving(false);
    if (!response.ok || !response.data) {
      setSavedMessage(response.error || "Delete failed.");
      return;
    }
    setSavedMessage(response.data.message);
    setSelectedSavedName("");
    await refreshSavedPortfolios();
  }

  return (
    <section className="portfolio-api-panel" aria-label="Portfolio analysis API">
      <div className="section-heading">
        <div>
          <h2>Analyze Ticker Or Portfolio</h2>
          <span>API-backed methodology snapshot</span>
        </div>
        <div className="portfolio-mode-tabs" role="tablist" aria-label="Portfolio analysis input type">
          {(["ticker", "csv", "file"] as const).map((item) => (
            <button
              type="button"
              key={item}
              className={mode === item ? "selected" : ""}
              onClick={() => setMode(item)}
              aria-pressed={mode === item}
            >
              {item === "ticker" ? "Ticker" : item.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="portfolio-input-grid">
        {mode === "ticker" ? (
          <label>
            Ticker
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value.toUpperCase())}
              placeholder="Enter ticker"
              aria-label="Ticker to analyze"
            />
          </label>
        ) : null}
        {mode === "csv" ? (
          <label className="portfolio-csv-input">
            CSV Holdings
            <textarea
              value={csvText}
              onChange={(event) => setCsvText(event.target.value)}
              placeholder="Ticker,Weight"
              aria-label="CSV holdings"
            />
          </label>
        ) : null}
        {mode === "file" ? (
          <label>
            CSV / Excel File
            <input
              type="file"
              accept=".csv,.xls,.xlsx,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) {
                  setFileName("");
                  setFileContentBase64("");
                  return;
                }
                setFileName(file.name);
                setFileContentBase64(await readFileAsBase64(file));
              }}
            />
          </label>
        ) : null}
        <button type="button" className="portfolio-submit" onClick={submit} disabled={loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>
      <div className="saved-portfolio-grid" aria-label="Saved portfolio controls">
        <label>
          Save Name
          <input
            value={portfolioName}
            onChange={(event) => setPortfolioName(event.target.value)}
            placeholder="Name this portfolio"
            aria-label="Saved portfolio name"
          />
        </label>
        <button type="button" className="portfolio-submit secondary" onClick={saveCurrentPortfolio} disabled={saving || !lastRequest}>
          {saving ? "Saving..." : "Save"}
        </button>
        <label>
          Saved Portfolios
          <select
            value={selectedSavedName}
            onChange={(event) => setSelectedSavedName(event.target.value)}
            aria-label="Saved portfolio selector"
          >
            <option value="">{savedLoading ? "Loading..." : "Select saved portfolio"}</option>
            {savedPortfolios.map((item) => (
              <option value={item.name} key={item.name}>
                {item.name} ({item.holding_count})
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="portfolio-submit secondary" onClick={loadSavedPortfolio} disabled={loading || !selectedSavedName}>
          Load
        </button>
        <button type="button" className="portfolio-submit danger" onClick={deleteSelectedSavedPortfolio} disabled={saving || !selectedSavedName}>
          Delete
        </button>
      </div>
      {savedMessage ? <p className="portfolio-footnote" role="status">{savedMessage}</p> : null}
      {error ? <p className="portfolio-error" role="status">{error}</p> : null}
      {result ? (
        <div className="portfolio-results">
          <div className="portfolio-summary-row">
            <div><span>Status</span><strong>{result.status}</strong></div>
            <div><span>Holdings</span><strong>{result.input.holding_count}</strong></div>
            <div><span>Rows</span><strong>{result.summary.row_count}</strong></div>
            <div><span>Missing</span><strong>{result.summary.missing_tickers.length}</strong></div>
          </div>
          <div className="portfolio-exposure-grid">
            <div>
              <h3>State Exposure</h3>
              {exposureEntries(result.summary.state_exposure).map(([state, value]) => (
                <p key={state}><span>{state}</span><strong>{weightPct(value)}</strong></p>
              ))}
            </div>
            <div>
              <h3>Class Exposure</h3>
              {exposureEntries(result.summary.class_exposure).map(([assetClass, value]) => (
                <p key={assetClass}><span>{assetClass}</span><strong>{weightPct(value)}</strong></p>
              ))}
            </div>
          </div>
          <div className="table-scroll portfolio-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Weight</th>
                  <th>State</th>
                  <th>S</th>
                  <th>F</th>
                  <th>Class</th>
                  <th>Rank</th>
                  <th>Methodology</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr
                    key={row.ticker}
                    className={row.missing ? "missing-row" : ""}
                    onClick={() => {
                      if (!row.missing) onSelectTicker(row.ticker);
                    }}
                  >
                    <td><strong>{row.ticker}</strong></td>
                    <td>{weightPct(row.analysis_weight)}</td>
                    <td>{row.missing ? "missing" : row.state}</td>
                    <td>{fmt(row.s_score)}</td>
                    <td>{fmt(row.f_score)}</td>
                    <td>{row.asset_class || "n/a"}</td>
                    <td>{row.rank_in_class ?? "n/a"}</td>
                    <td>
                      {row.missing
                        ? row.missing_reason || "Ticker was not in the latest saved methodology universe."
                        : `${row.selected ? "Selected" : "Not selected"}; ${row.veto ? "veto active" : "no veto"} in the latest saved snapshot.`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="portfolio-footnote">{result.message}</p>
        </div>
      ) : null}
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

function CTopBar({
  activeScreen,
  setActiveScreen,
  generatedAt,
}: {
  activeScreen: ScreenId;
  setActiveScreen: (screen: ScreenId) => void;
  generatedAt: string;
}) {
  const labels: { id: ScreenId; label: string }[] = [
    { id: "overview", label: "Heatmap" },
    { id: "rotation", label: "Rotation" },
    { id: "deepdive", label: "Deep dive" },
  ];
  return (
    <header className="c-topbar">
      <div className="c-brand">
        <span className="c-logo" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </span>
        <strong>Momentum</strong>
        <span>v2</span>
      </div>
      <nav className="c-tabs" aria-label="Display C screen selector">
        {labels.map((item) => (
          <button
            type="button"
            key={item.id}
            className={activeScreen === item.id ? "selected" : ""}
            onClick={() => setActiveScreen(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button type="button" className="inactive" aria-disabled="true">Macro</button>
        <button type="button" className="inactive" aria-disabled="true">Positions</button>
      </nav>
      <div className="c-live"><i /> {generatedAt || "latest snapshot"}</div>
      <button type="button" className="c-icon-btn" title="Refresh candidate snapshot" aria-label="Refresh candidate snapshot">↻</button>
      <button type="button" className="c-icon-btn" title="Display mode" aria-label="Display mode">☾</button>
    </header>
  );
}

function CWeatherStrip({ snapshot }: { snapshot: DashboardSnapshotPayload }) {
  const warnings = (snapshot.summary.state_counts.WARNING ?? 0) + (snapshot.summary.state_counts.EXIT ?? 0);
  const bullish = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;
  const exits = snapshot.summary.state_counts.EXIT ?? 0;
  const leaders = snapshot.screens.overview?.leaders ?? [];
  const risks = snapshot.screens.overview?.risks ?? [];
  const leadText = leaders[0]?.identity || leaders[0]?.ticker || "Leadership";
  const riskText = risks[0]?.identity || risks[0]?.ticker || "risk queue";
  const breadth = snapshot.summary.universe_count
    ? Math.round((leaders.length / snapshot.summary.universe_count) * 100)
    : 0;
  const headline = `${leadText} leads; ${riskText} under pressure.`;
  return (
    <section className="c-weather" aria-label="Display C weather strip">
      <div className="c-weather-card">
        <div className="c-weather-lead">
          <span>TODAY | SAVED DASHBOARD RUN</span>
          <strong>{headline}</strong>
          <p>{warnings} warning/exit rows. {bullish} bullish. Universe size {snapshot.summary.universe_count}.</p>
        </div>
        <div><span>Regime</span><strong>{snapshot.run?.metadata?.phase ? String(snapshot.run.metadata.phase) : "Current"}</strong><p>{snapshot.run?.provider || "provider"} data</p></div>
        <div><span>Cycle</span><strong>{snapshot.run?.metadata?.cycle_phase ? String(snapshot.run.metadata.cycle_phase) : "Live"}</strong><p>macro context</p></div>
        <div><span>Warnings</span><strong>{warnings}</strong><p>warning + exit</p></div>
        <div><span>Breadth</span><strong>{breadth}%</strong><p>top leaders / universe</p></div>
        <div><span>Universe</span><strong>{snapshot.summary.universe_count}</strong><p>{bullish} bullish | {exits} exit</p></div>
      </div>
    </section>
  );
}

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
        <TransitionsBanner
          transitions={transitions}
          onSelect={navigate}
          light={true}
          title="State changes"
        />
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
              <strong>State changes</strong>
              <span>{transitions.length ? `${transitions.length} recorded` : "latest run"}</span>
            </div>
            {transitions.slice(0, 8).map((t) => (
              <TransitionRailRow
                key={`${t.ticker}-${t.from}-${t.to}-${t.date}`}
                transition={t}
                onSelect={navigate}
              />
            ))}
            {!transitions.length ? (
              <p className="c-rail-empty">No saved transition rows were found in the snapshot; showing latest model actions instead.</p>
            ) : null}
          </div>
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
              <button
                type="button"
                className="c-cohort-row"
                key={row.ticker}
                onClick={() => navigate(row.ticker)}
              >
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

function TransitionRailRow({
  transition,
  onSelect,
}: {
  transition: SnapshotTransition;
  onSelect: (ticker: string) => void;
}) {
  const toLabel = compactStateText(transition.to);
  const fromLabel = compactStateText(transition.from);
  return (
    <button
      type="button"
      className={`c-transition-row ${statusClass(transition.to)}`}
      onClick={() => onSelect(transition.ticker)}
      title={`${transition.ticker} transitioned ${transition.from} to ${transition.to} on ${transition.date || "unknown date"}`}
    >
      <i />
      <strong>{transition.ticker}</strong>
      <span><em>{fromLabel}</em> to {toLabel}</span>
      <time>{transition.date || "undated"}</time>
    </button>
  );
}

function PositionRailRow({ position }: { position: SnapshotPosition }) {
  const tone = (position.unrealized_pct ?? 0) >= 0 ? "good" : "bad";
  return (
    <div className="c-position-row">
      <div>
        <strong>{position.ticker}</strong>
        <span>{position.identity}</span>
        <small>{position.shares ? `${fmt(position.shares, 0)} sh` : "shares n/a"} | cost {money(position.cost)}</small>
      </div>
      <em className={tone}>{pct(position.unrealized_pct)}</em>
    </div>
  );
}

function CDeepDiveScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const focus = rowByTicker(snapshot.rows, selectedTicker) ?? snapshot.focus;
  if (!focus) return <p className="c-empty">Run a dashboard refresh to persist a focus row.</p>;
  const rank = [...snapshot.rows].sort((a, b) => b.s_score - a.s_score).findIndex((row) => row.ticker === focus.ticker) + 1;
  const gates = gateRows(focus);
  const failedGates = gates.filter((gate) => gate.ok === false).length;
  return (
    <section className="c-screen" aria-label="Display C ticker deep dive">
      <header className="c-deep-header">
        <div>
          <div className="c-breadcrumb">Momentum / Heatmap / <strong>{focus.ticker}</strong></div>
          <div className="c-deep-title-row">
            <h1>{focus.ticker}</h1>
            <span className={`light-state-pill ${stateToneForClass(focus.state)}`}>{focus.state.replaceAll("_", " ")}</span>
            <p>{focus.asset_class} | {focus.identity}</p>
          </div>
          <strong>{focus.state.replaceAll("_", " ")}: {fieldNarrative(focus)} The waterfall below makes the signed pillar math visible: which signals did the work, which dragged, and where the composite finished.</strong>
        </div>
        <label className="c-focus-select">
          Focus
          <select value={focus.ticker} onChange={(event) => onSelectTicker(event.target.value)}>
            {snapshot.rows.map((row) => (
              <option value={row.ticker} key={row.ticker}>{row.display_label}</option>
            ))}
          </select>
        </label>
      </header>
      <div className="c-stat-deck">
        <div><span>S-score</span><strong>{fmt(focus.s_score)}</strong></div>
        <div><span>F-score</span><strong>{fmt(focus.f_score)}</strong></div>
        <div><span>Momentum</span><strong>{fmt(focus.momentum_pct, 2)}</strong></div>
        <div><span>Rank</span><strong>{rank} / {snapshot.rows.length}</strong></div>
        <div><span>RRG</span><strong>{focus.quadrant}</strong></div>
      </div>
      <WaterfallChart row={focus} />
      <PillarDetailGrid row={focus} />
      <div className="c-support-grid">
        <TickerPriceChartPanel row={focus} />
        <div className="c-gate-card">
          <div className="c-sec-head"><strong>State machine</strong><span>{failedGates} tripped</span></div>
          {gates.map((gate) => (
            <div className="c-gate-row" key={gate.label}>
              <i className={gate.ok === true ? "ok" : gate.ok === false ? "fail" : "neutral"}>{gate.ok === true ? "✓" : gate.ok === false ? "×" : "·"}</i>
              <span>{gate.label}</span>
              <strong>{gate.detail}</strong>
            </div>
          ))}
          <div className="c-escalation-callout">
            <strong>Next escalation to EXIT:</strong> watch price below the 30-week average, Mansfield RS below 0, CMF below -0.10, or a turn into Lagging. Nearest live readings: Mansfield {fmt(payloadNumber(focus, "mansfield_rs"), 2)}, CMF {fmt(focus.cmf21, 2)}, RRG {focus.quadrant}.
          </div>
        </div>
      </div>
      <details className="c-advanced-evidence">
        <summary>More evidence</summary>
        <div className="c-support-grid c-support-grid-advanced">
          <div className="c-gate-card">
            <div className="c-sec-head"><strong>Plain-English read</strong><span>latest saved run</span></div>
            <p>{focus.display_label} currently has S {fmt(focus.s_score)} and F {fmt(focus.f_score)}. A positive S means the pillar stack leans bullish; a negative F means flow is acting as a drag before price/trend may fully react.</p>
          </div>
          <TickerRelativeStrengthPanel row={focus} />
          <TickerFlowChartPanels row={focus} />
        </div>
      </details>
    </section>
  );
}

function stateToneForClass(state: string) {
  const normalized = state.toLowerCase();
  if (normalized.includes("bullish")) return "good";
  if (normalized.includes("warn")) return "warn";
  if (normalized.includes("exit") || normalized.includes("bear")) return "bad";
  return "hold";
}

function gateRows(row: SnapshotRow) {
  const above30 = payloadBool(row, "above_30wma");
  const slope = payloadBool(row, "ma_slope_pos");
  const antonacci = payloadBool(row, "antonacci");
  const obvDivergence = payloadBool(row, "obv_divergence");
  const mansfield = payloadNumber(row, "mansfield_rs");
  const breadth = payloadNumber(row, "breadth_50d");
  const etfFlow = payloadNumber(row, "etf_flow_5d_pct");
  return [
    { label: "RRG quadrant", ok: !["Lagging", "Weakening"].includes(row.quadrant), detail: row.quadrant },
    { label: "Breadth >= 50%", ok: breadth === null ? null : breadth >= 0.5, detail: breadth === null ? "n/a" : pct(breadth, 0) },
    { label: "CMF stayed > 0", ok: row.cmf21 === null ? null : row.cmf21 > 0, detail: fmt(row.cmf21, 2) },
    { label: "No OBV divergence", ok: obvDivergence === null ? null : !obvDivergence, detail: obvDivergence === null ? "n/a" : obvDivergence ? "active" : "clear" },
    { label: "ETF flow non-negative", ok: etfFlow === null ? null : etfFlow >= 0, detail: etfFlow === null ? "n/a" : pct(etfFlow, 2) },
    { label: "Price > 30wMA", ok: above30, detail: passText(above30) },
    { label: "MA slope positive", ok: slope, detail: passText(slope) },
    { label: "Mansfield RS > 0", ok: mansfield === null ? null : mansfield > 0, detail: fmt(mansfield, 2) },
    { label: "Antonacci > T-bill", ok: antonacci, detail: passText(antonacci) },
  ];
}

function PriceEvidencePanel({ row }: { row: SnapshotRow }) {
  const stage = payloadNumber(row, "stage");
  const above30 = payloadBool(row, "above_30wma");
  const slope = payloadBool(row, "ma_slope_pos");
  const faber = payloadBool(row, "faber");
  return (
    <div className="c-gate-card c-price-evidence">
      <div className="c-sec-head"><strong>Price + 30wMA</strong><span>Weinstein evidence</span></div>
      <div className="c-price-evidence-grid">
        <div><span>Stage</span><strong>{stage === null ? "n/a" : fmt(stage, 0)}</strong></div>
        <div><span>Price above 30wMA</span><strong>{passText(above30)}</strong></div>
        <div><span>MA slope</span><strong>{passText(slope)}</strong></div>
        <div><span>Faber 10mo</span><strong>{passText(faber)}</strong></div>
      </div>
      <p>This panel uses the saved methodology gate fields in the latest run journal when cached OHLCV chart rows are unavailable. It does not draw synthetic price lines.</p>
    </div>
  );
}

function TickerPriceChartPanel({ row }: { row: SnapshotRow }) {
  const [payload, setPayload] = useState<TickerChartPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTickerChart(row.ticker, "3y").then((response) => {
      if (cancelled) return;
      if (!response.ok || !response.data) {
        setPayload(null);
        return;
      }
      setPayload(response.data);
    });
    return () => {
      cancelled = true;
    };
  }, [row.ticker]);

  const series = payload?.series.filter((point) => typeof point.close === "number" && typeof point.ma30w === "number") ?? [];
  const width = 760;
  const height = 220;
  const pad = 28;
  const values = series
    .flatMap((point) => [point.close, point.ma30w])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const span = Math.max(max - min, 0.000001);
  const x = (index: number) => pad + (series.length <= 1 ? 0 : index / (series.length - 1) * (width - pad * 2));
  const y = (value: number) => pad + (max - value) / span * (height - pad * 2);
  const closePoints = series.map((point, index) => `${x(index).toFixed(1)},${y(point.close as number).toFixed(1)}`).join(" ");
  const maPoints = series.map((point, index) => `${x(index).toFixed(1)},${y(point.ma30w as number).toFixed(1)}`).join(" ");

  if (payload?.status !== "ready" || !series.length) {
    return <PriceEvidencePanel row={row} />;
  }

  return (
    <div className="c-gate-card c-price-chart-panel">
      <div className="c-sec-head">
        <strong>Price + 30wMA</strong>
        <span>{payload.source.mode} | {payload.source.provider || "unknown"}</span>
      </div>
      <div className="price-chart-kpis">
        <div><span>Latest close</span><strong>{fmt(payload.latest.close, 2)}</strong></div>
        <div><span>30wMA</span><strong>{fmt(payload.latest.ma30w, 2)}</strong></div>
        <div><span>Above 30wMA</span><strong className={toneForBool(payload.latest.above_30wma)}>{passText(payload.latest.above_30wma)}</strong></div>
        <div><span>30wMA slope</span><strong className={toneForBool(payload.latest.ma30w_slope === null ? null : payload.latest.ma30w_slope >= 0)}>{fmt(payload.latest.ma30w_slope, 2)}</strong></div>
      </div>
      <svg className="ticker-price-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${row.display_label} weekly price and 30 week moving average`}>
        <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} className="axis-line" />
        <polyline points={maPoints} className="ma-line" />
        <polyline points={closePoints} className="price-line" />
        <text x={pad} y={20}>Weekly close</text>
        <text x={width - pad} y={20} textAnchor="end">30wMA</text>
      </svg>
      <p>
        {payload.ticker} latest cached weekly close is {fmt(payload.latest.close, 2)} versus a 30-week average of {fmt(payload.latest.ma30w, 2)}.
        Source is {payload.source.mode} {payload.source.provider || "unknown"} data updated {payload.source.updated_at || "unknown"}.
      </p>
    </div>
  );
}

function FlowMiniLine({
  points,
  valueKey,
  className,
  ariaLabel,
}: {
  points: { date: string; cmf21: number | null; obv: number | null }[];
  valueKey: "cmf21" | "obv";
  className: string;
  ariaLabel: string;
}) {
  const series = points.filter((point) => typeof point[valueKey] === "number");
  const width = 360;
  const height = 130;
  const pad = 18;
  const values = series.map((point) => point[valueKey]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const min = values.length ? Math.min(...values, valueKey === "cmf21" ? -0.1 : values[0]) : 0;
  const max = values.length ? Math.max(...values, valueKey === "cmf21" ? 0.1 : values[0]) : 1;
  const span = Math.max(max - min, 0.000001);
  const x = (index: number) => pad + (series.length <= 1 ? 0 : index / (series.length - 1) * (width - pad * 2));
  const y = (value: number) => pad + (max - value) / span * (height - pad * 2);
  const line = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const zeroY = y(0);
  return (
    <svg className={`flow-mini-chart ${className}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
      {valueKey === "cmf21" ? <line x1={pad} x2={width - pad} y1={zeroY} y2={zeroY} className="zero-line" /> : null}
      <polyline points={line} />
    </svg>
  );
}

function RelativeMiniLine({
  points,
  valueKey,
  className,
  ariaLabel,
}: {
  points: { date: string; rs_ratio: number | null; momentum_12w: number | null; momentum_52w: number | null }[];
  valueKey: "rs_ratio" | "momentum_12w" | "momentum_52w";
  className: string;
  ariaLabel: string;
}) {
  const series = points.filter((point) => typeof point[valueKey] === "number");
  const width = 360;
  const height = 130;
  const pad = 18;
  const values = series.map((point) => point[valueKey]).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const baseline = valueKey === "rs_ratio" ? 100 : 0;
  const min = values.length ? Math.min(...values, baseline) : baseline - 1;
  const max = values.length ? Math.max(...values, baseline) : baseline + 1;
  const span = Math.max(max - min, 0.000001);
  const x = (index: number) => pad + (series.length <= 1 ? 0 : index / (series.length - 1) * (width - pad * 2));
  const y = (value: number) => pad + (max - value) / span * (height - pad * 2);
  const line = values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  return (
    <svg className={`flow-mini-chart ${className}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel}>
      <line x1={pad} x2={width - pad} y1={y(baseline)} y2={y(baseline)} className="zero-line" />
      <polyline points={line} />
    </svg>
  );
}

function TickerRelativeStrengthPanel({ row }: { row: SnapshotRow }) {
  const [payload, setPayload] = useState<TickerChartPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTickerChart(row.ticker, "3y").then((response) => {
      if (cancelled) return;
      setPayload(response.ok ? response.data : null);
    });
    return () => {
      cancelled = true;
    };
  }, [row.ticker]);

  const points = payload?.relative_strength_series ?? [];
  if (payload?.status !== "ready" || !points.length) {
    return (
      <div className="c-gate-card c-flow-evidence-panel">
        <div className="c-sec-head"><strong>Relative strength + momentum</strong><span>cached benchmark unavailable</span></div>
        <p>Cached benchmark-relative charts are unavailable. The latest saved snapshot still reports RRG {row.quadrant}, RS ratio {fmt(row.rs_ratio, 1)}, RS momentum {fmt(row.rs_momentum, 1)}, and momentum {fmt(row.momentum_pct, 2)}.</p>
      </div>
    );
  }

  return (
    <div className="c-gate-card c-flow-evidence-panel">
      <div className="c-sec-head">
        <strong>Relative strength + momentum</strong>
        <span>vs {payload.source.benchmark || "benchmark"}</span>
      </div>
      <div className="flow-evidence-grid">
        <div>
          <div className="flow-evidence-head">
            <span>RS ratio</span>
            <strong className={toneForBool(payload.latest.rs_ratio === null ? null : payload.latest.rs_ratio >= 100)}>{fmt(payload.latest.rs_ratio, 1)}</strong>
          </div>
          <RelativeMiniLine points={points} valueKey="rs_ratio" className="rs-line" ariaLabel={`${row.display_label} relative strength ratio chart`} />
          <p>Above 100 means {row.ticker} has outperformed {payload.source.benchmark || "the benchmark"} over this cached window; falling RS warns that leadership is fading.</p>
        </div>
        <div>
          <div className="flow-evidence-head">
            <span>12w / 52w momentum</span>
            <strong className={toneForBool(payload.latest.momentum_12w === null ? null : payload.latest.momentum_12w >= 0)}>
              {pct(payload.latest.momentum_12w, 1)} / {pct(payload.latest.momentum_52w, 1)}
            </strong>
          </div>
          <RelativeMiniLine points={points} valueKey="momentum_12w" className="momentum-line" ariaLabel={`${row.display_label} 12 week momentum chart`} />
          <p>Shorter momentum shows recent acceleration; 52-week momentum gives the slower trend backdrop used to interpret the stage label.</p>
        </div>
      </div>
    </div>
  );
}

function TickerFlowChartPanels({ row }: { row: SnapshotRow }) {
  const [payload, setPayload] = useState<TickerChartPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTickerChart(row.ticker, "3y").then((response) => {
      if (cancelled) return;
      setPayload(response.ok ? response.data : null);
    });
    return () => {
      cancelled = true;
    };
  }, [row.ticker]);

  const flow = payload?.flow_series ?? [];
  if (payload?.status !== "ready" || !flow.length) {
    return (
      <div className="c-gate-card c-flow-evidence-panel">
        <div className="c-sec-head"><strong>CMF + OBV</strong><span>cached flow unavailable</span></div>
        <p>Cached OHLCV flow charts are unavailable, so the current saved snapshot values are shown instead: CMF {fmt(row.cmf21, 2)}, F {fmt(row.f_score, 2)}.</p>
      </div>
    );
  }

  return (
    <div className="c-gate-card c-flow-evidence-panel">
      <div className="c-sec-head"><strong>CMF + OBV</strong><span>{payload.source.mode} | {payload.source.provider || "unknown"}</span></div>
      <div className="flow-evidence-grid">
        <div>
          <div className="flow-evidence-head">
            <span>CMF(21)</span>
            <strong className={toneForBool(payload.latest.cmf21 === null ? null : payload.latest.cmf21 > 0)}>{fmt(payload.latest.cmf21, 2)}</strong>
          </div>
          <FlowMiniLine points={flow} valueKey="cmf21" className="cmf-line" ariaLabel={`${row.display_label} CMF 21 chart`} />
          <p>CMF above +0.05 supports accumulation; below -0.10 is distribution risk.</p>
        </div>
        <div>
          <div className="flow-evidence-head">
            <span>OBV slope</span>
            <strong className={toneForBool(payload.latest.obv_slope === null ? null : payload.latest.obv_slope >= 0)}>{fmt(payload.latest.obv_slope, 2)}</strong>
          </div>
          <FlowMiniLine points={flow} valueKey="obv" className="obv-line" ariaLabel={`${row.display_label} OBV chart`} />
          <p>OBV checks whether volume confirms price. Positive slope is healthier than fading volume sponsorship.</p>
        </div>
      </div>
    </div>
  );
}

function CRotationScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const sectors = snapshot.screens.rotation?.sectors ?? [];
  const rows = sectors.length ? sectors : snapshot.rows;
  const sortedFlowRows = [...rows].sort((a, b) => Math.abs(rowPressure(b)) - Math.abs(rowPressure(a))).slice(0, 9);
  const cyclePhase = String(snapshot.run?.metadata?.cycle_phase || "").toUpperCase();
  const warningCount = snapshot.summary.state_counts.WARNING ?? 0;
  const exitCount = snapshot.summary.state_counts.EXIT ?? 0;
  const bullishCount = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;
  const leadingCount = snapshot.summary.quadrant_counts.Leading ?? 0;
  return (
    <section className="c-screen" aria-label="Display C rotation and flow">
      <header className="c-rotation-head">
        <h1>The rotation map</h1>
        <p>Where the money was, where it is, where it's heading. The map shows current quadrant positions; the trails show the four-week path; the flow river shows which sectors are giving up share and which are taking it.</p>
      </header>
      <div className="c-rotation-grid">
        <RrgChart
          rows={rows}
          title="Relative rotation | US Sectors"
          subtitle="4-week trail"
          meta={`${rows.length} rows`}
          onSelectTicker={(ticker) => {
            onSelectTicker(ticker);
            setActiveScreen("deepdive");
          }}
        />
        <MomentumBars
          rows={rows}
          title="12-1 momentum"
          subtitle="cross-sectional momentum ranking"
          meta="z-scored"
          onSelectTicker={(ticker) => {
            onSelectTicker(ticker);
            setActiveScreen("deepdive");
          }}
        />
      </div>
      <FlowRiver rows={rows} />
      <div className="c-lower-grid">
        <div className="c-flow-table c-macro-panel">
          <div className="c-sec-head"><strong>Macro / business cycle</strong><span>run context</span></div>
          <div className="c-cycle-tabs">
            {["EARLY", "MID", "LATE", "RECESS"].map((phase) => (
              <span key={phase} className={cyclePhase === phase ? "selected" : ""}>{phase}</span>
            ))}
          </div>
          <div className="c-macro-tiles">
            <div><span>Universe</span><strong>{snapshot.summary.universe_count}</strong><small>{snapshot.run?.provider || "provider"} snapshot</small></div>
            <div><span>Bullish</span><strong>{bullishCount}</strong><small>stage-2 rows</small></div>
            <div><span>Leading</span><strong>{leadingCount}</strong><small>RRG quadrant</small></div>
            <div><span>Warnings</span><strong>{warningCount + exitCount}</strong><small>{warningCount} warn | {exitCount} exit</small></div>
          </div>
          <p>Persisted run-journal context only. This screen does not fetch FRED/Massive during render.</p>
        </div>
        <div className="c-flow-table">
          <div className="c-sec-head"><strong>Flow internals</strong><span>click row for deep dive</span></div>
          <table>
            <thead>
              <tr><th>Ticker</th><th>Identity</th><th>Read</th><th>S</th><th>F</th><th>CMF</th><th>Mom</th></tr>
            </thead>
            <tbody>
              {sortedFlowRows.map((row) => (
                <tr key={row.ticker} className={row.ticker === selectedTicker ? "selected-row" : ""} onClick={() => {
                  onSelectTicker(row.ticker);
                  setActiveScreen("deepdive");
                }}>
                  <td><strong>{row.ticker}</strong></td>
                  <td>{row.identity}</td>
                  <td><span className="c-flow-read">{flowNarrative(row)}</span></td>
                  <td>{fmt(row.s_score)}</td>
                  <td>{fmt(row.f_score)}</td>
                  <td>{fmt(row.cmf21, 2)}</td>
                  <td>{fmt(row.momentum_pct, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

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

function ABlufStrip({ snapshot }: { snapshot: DashboardSnapshotPayload }) {
  const warnings = snapshot.summary.state_counts.WARNING ?? 0;
  const exits = snapshot.summary.state_counts.EXIT ?? 0;
  const bearish = snapshot.summary.state_counts.BEARISH_STAGE_4 ?? 0;
  const buys = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;
  const leaders = snapshot.screens.overview?.leaders ?? [];
  const risks = snapshot.screens.overview?.risks ?? [];
  const lead = leaders[0]?.display_label || "leadership";
  const risk = risks[0]?.display_label || "risk queue";
  const breadth = snapshot.summary.universe_count
    ? Math.round((buys / snapshot.summary.universe_count) * 100)
    : 0;
  return (
    <section className="a-bluf">
      <div className="a-bluf-meta">
        <span>BLUF | SAVED DASHBOARD RUN</span>
        <em>{snapshot.run?.started_at_utc || snapshot.generated_at}</em>
        <em>PROVIDER {snapshot.run?.provider || "unknown"}</em>
      </div>
      <p>{lead} is carrying the strongest composite setup while {risk} sits at the weakest edge of the model. This terminal view is live-data backed: counts, rows, actions, and labels come from the latest persisted run journal.</p>
      <div className="a-bluf-numbers">
        <strong className="bad">{exits + bearish}<span>EXIT / BEAR</span></strong>
        <strong className="warn">{warnings}<span>WARNINGS</span></strong>
        <strong className="good">{buys}<span>BULLISH</span></strong>
        <i />
        <span>UNIVERSE {snapshot.summary.universe_count} | BREADTH {breadth}%</span>
      </div>
    </section>
  );
}

function AStatusStrip({ snapshot }: { snapshot: DashboardSnapshotPayload }) {
  const leading = snapshot.summary.quadrant_counts.Leading ?? 0;
  const weakening = snapshot.summary.quadrant_counts.Weakening ?? 0;
  const lagging = snapshot.summary.quadrant_counts.Lagging ?? 0;
  const improving = snapshot.summary.quadrant_counts.Improving ?? 0;
  const bullish = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;
  const warnings = snapshot.summary.state_counts.WARNING ?? 0;
  return (
    <section className="a-status-grid">
      <div><span>RISK REGIME</span><strong>{warnings > bullish ? "CAUTION" : "RISK-ON"}</strong><p>{warnings} warning rows in the latest run</p></div>
      <div><span>CYCLE PHASE</span><strong>{String(snapshot.run?.metadata?.cycle_phase || "LIVE").toUpperCase()}</strong><p>run-journal macro context</p></div>
      <div><span>RRG MAP</span><strong>{leading}/{weakening}</strong><p>leading / weakening quadrants</p></div>
      <div><span>BREADTH</span><strong>{improving}/{lagging}</strong><p>improving / lagging quadrants</p></div>
    </section>
  );
}

function ATerminalHeatmap({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
  const grouped = rows.reduce<Record<string, SnapshotRow[]>>((acc, row) => {
    const key = row.asset_class || "Universe";
    acc[key] = acc[key] || [];
    acc[key].push(row);
    return acc;
  }, {});
  const classNames = Object.keys(grouped).sort((a, b) => {
    const order = ["US Sectors", "US Industries", "Countries", "Factors"];
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi) || a.localeCompare(b);
  });
  return (
    <section className="a-panel a-heatmap">
      <div className="a-section-head"><strong>7-PILLAR HEATMAP</strong><span>composite = weighted live snapshot pillars</span><em>SORTED BY S WITHIN CLASS</em></div>
      <div className="a-heatmap-head"><span>TKR</span><span>NOTE</span><span>STATE</span><span>7 PILLARS</span><span>S</span><span>F</span><span>MOM</span><span>RRG</span></div>
      {classNames.map((assetClass) => {
        const groupRows = grouped[assetClass].slice().sort((a, b) => b.s_score - a.s_score);
        return (
          <div key={assetClass} className="a-class-group">
            <div className="a-class-row"><span>{assetClass.toUpperCase()}</span><i /><em>{groupRows.length} | {groupRows.filter((row) => row.s_score > 0).length} positive S</em></div>
            {groupRows.map((row) => (
              <button type="button" key={row.ticker} className="a-heatmap-row" onClick={() => onSelectTicker(row.ticker)}>
                <strong className={row.s_score >= 0 ? "good" : "bad"}>{row.ticker}</strong>
                <span>{row.identity || row.display_label}</span>
                <em className={`a-state ${stateToneForClass(row.state)}`}>{row.state.replaceAll("_", " ")}</em>
                <PillarStackBar row={row} />
                <b className={row.s_score >= 0 ? "good" : "bad"}>{fmt(row.s_score)}</b>
                <b className={row.f_score >= 0 ? "good" : "bad"}>{fmt(row.f_score)}</b>
                <b className={(row.momentum_pct ?? 0) >= 0 ? "good" : "bad"}>{fmt(row.momentum_pct, 2)}</b>
                <span>{row.quadrant}</span>
              </button>
            ))}
          </div>
        );
      })}
    </section>
  );
}

function numericPillars(row: SnapshotRow): [string, number][] {
  const entries = Object.entries(row.pillar_scores)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]))
    .slice(0, 7);
  return entries.length ? entries : [
    ["S", row.s_score],
    ["F", row.f_score],
    ["MOM", row.momentum_pct ?? 0],
    ["RSR", ((row.rs_ratio ?? 100) - 100) / 100],
    ["RSM", ((row.rs_momentum ?? 100) - 100) / 100],
    ["CMF", row.cmf21 ?? 0],
  ];
}

function ACompositeBreakdown({ row }: { row: SnapshotRow }) {
  const pillars = numericPillars(row);
  const max = Math.max(0.1, ...pillars.map(([, value]) => Math.abs(value)));
  return (
    <div className="a-breakdown" aria-label={`${row.ticker} terminal composite breakdown`}>
      <div className="a-breakdown-axis"><span>bearish</span><i /><span>bullish</span></div>
      {pillars.map(([key, value]) => {
        const width = Math.max(4, Math.abs(value) / max * 48);
        return (
          <div className="a-breakdown-row" key={key}>
            <span>{key.toUpperCase()}</span>
            <b>
              <i className={value >= 0 ? "good" : "bad"} style={value >= 0 ? { left: "50%", width: `${width}%` } : { left: `${50 - width}%`, width: `${width}%` }} />
            </b>
            <strong className={value >= 0 ? "good" : "bad"}>{fmt(value, 3)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function APillarTerminalGrid({ row }: { row: SnapshotRow }) {
  return (
    <div className="a-pillar-grid" aria-label={`${row.ticker} terminal pillar detail`}>
      {numericPillars(row).map(([key, value]) => (
        <div key={key}>
          <i className={value >= 0 ? "good" : "bad"} />
          <span>{key.toUpperCase()}</span>
          <p>{value >= 0 ? "supports" : "drags"} {row.ticker}'s composite score in the latest saved run.</p>
          <strong className={value >= 0 ? "good" : "bad"}>{fmt(value, 3)}</strong>
        </div>
      ))}
    </div>
  );
}

function APeerRank({ rows, focusTicker, onSelectTicker }: { rows: SnapshotRow[]; focusTicker: string; onSelectTicker: (ticker: string) => void }) {
  return (
    <section className="a-panel">
      <div className="a-section-head"><strong>PEERS | RANK BY S</strong><span>same asset class</span><em>{rows.length} ROWS</em></div>
      {rows.slice(0, 14).map((row) => (
        <button type="button" key={row.ticker} className={`a-peer-row ${row.ticker === focusTicker ? "selected" : ""}`} onClick={() => onSelectTicker(row.ticker)}>
          <strong>{row.ticker}</strong><span>{row.identity}</span><em className={row.s_score >= 0 ? "good" : "bad"}>{fmt(row.s_score)}</em>
        </button>
      ))}
    </section>
  );
}

function ARrgTerminal({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
  const width = 760;
  const height = 470;
  const pad = 54;
  const x = (value: number | null) => pad + (Math.max(70, Math.min(130, value ?? 100)) - 70) / 60 * (width - pad * 2);
  const y = (value: number | null) => height - pad - (Math.max(70, Math.min(130, value ?? 100)) - 70) / 60 * (height - pad * 2);
  return (
    <section className="a-panel">
      <div className="a-section-head"><strong>RELATIVE ROTATION GRAPH</strong><span>RS ratio x RS momentum</span><em>{rows.length} / {rows.length}</em></div>
      <svg className="a-rrg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Display A terminal RRG">
        <rect x={pad} y={pad} width={width - pad * 2} height={height - pad * 2} />
        <line x1={x(100)} x2={x(100)} y1={pad} y2={height - pad} />
        <line x1={pad} x2={width - pad} y1={y(100)} y2={y(100)} />
        <text x={pad + 10} y={pad + 18}>IMPROVING</text>
        <text x={width - pad - 78} y={pad + 18}>LEADING</text>
        <text x={pad + 10} y={height - pad - 10}>LAGGING</text>
        <text x={width - pad - 94} y={height - pad - 10}>WEAKENING</text>
        {rows.slice(0, 28).map((row, index) => {
          const px = x(row.rs_ratio);
          const py = y(row.rs_momentum);
          const tx = px - 16 + (index % 3) * 8;
          const ty = py + 12 - (index % 2) * 24;
          return (
            <g key={row.ticker} onClick={() => onSelectTicker(row.ticker)} className="a-rrg-point">
              <line x1={tx} x2={px} y1={ty} y2={py} />
              <circle cx={px} cy={py} r="5" className={stateToneForClass(row.state)} />
              <text x={tx} y={ty}>{row.ticker}</text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}

function AMomentumTerminal({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
  const sorted = rows.slice().sort((a, b) => (b.momentum_pct ?? 0) - (a.momentum_pct ?? 0)).slice(0, 18);
  const max = Math.max(0.1, ...sorted.map((row) => Math.abs(row.momentum_pct ?? 0)));
  return (
    <section className="a-panel">
      <div className="a-section-head"><strong>12-1 CROSS-SECTIONAL MOMENTUM</strong><span>sorted descending</span><em>LOOKBACK 12M</em></div>
      {sorted.map((row) => {
        const value = row.momentum_pct ?? 0;
        const width = Math.max(3, Math.abs(value) / max * 48);
        return (
          <button type="button" key={row.ticker} className="a-mom-row" onClick={() => onSelectTicker(row.ticker)}>
            <strong>{row.ticker}</strong>
            <span><i className={value >= 0 ? "good" : "bad"} style={value >= 0 ? { left: "50%", width: `${width}%` } : { left: `${50 - width}%`, width: `${width}%` }} /></span>
            <em className={value >= 0 ? "good" : "bad"}>{fmt(value, 2)}</em>
          </button>
        );
      })}
    </section>
  );
}

function BRrgEditorial({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
  const width = 700;
  const height = 580;
  const pad = 56;
  const x = (value: number | null) => pad + (Math.max(80, Math.min(120, value ?? 100)) - 80) / 40 * (width - pad * 2);
  const y = (value: number | null) => height - pad - (Math.max(80, Math.min(120, value ?? 100)) - 80) / 40 * (height - pad * 2);
  return (
    <svg className="b-rrg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Editorial relative rotation graph">
      <rect className="quad leading" x={x(100)} y={pad} width={x(120) - x(100)} height={y(100) - pad} />
      <rect className="quad weakening" x={x(100)} y={y(100)} width={x(120) - x(100)} height={height - pad - y(100)} />
      <rect className="quad lagging" x={pad} y={y(100)} width={x(100) - pad} height={height - pad - y(100)} />
      <rect className="quad improving" x={pad} y={pad} width={x(100) - pad} height={y(100) - pad} />
      {[85, 90, 95, 105, 110, 115].map((value) => (
        <g key={value}>
          <line x1={x(value)} x2={x(value)} y1={pad} y2={height - pad} className="grid" />
          <line x1={pad} x2={width - pad} y1={y(value)} y2={y(value)} className="grid" />
        </g>
      ))}
      <line x1={x(100)} x2={x(100)} y1={pad} y2={height - pad} className="axis" />
      <line x1={pad} x2={width - pad} y1={y(100)} y2={y(100)} className="axis" />
      <path className="rotation-arc" d={`M ${x(91)} ${y(113)} C ${x(104)} ${y(117)}, ${x(113)} ${y(106)}, ${x(109)} ${y(92)}`} />
      <text x={x(91)} y={y(114) - 8} className="annotation">this month's rotation</text>
      <text x={pad + 10} y={pad + 18}>IMPROVING</text>
      <text x={width - pad - 78} y={pad + 18}>LEADING</text>
      <text x={pad + 10} y={height - pad - 10}>LAGGING</text>
      <text x={width - pad - 94} y={height - pad - 10}>WEAKENING</text>
      {rows.slice(0, 18).map((row, index) => {
        const px = x(row.rs_ratio);
        const py = y(row.rs_momentum);
        const trailX = px - 18 + (index % 3) * 7;
        const trailY = py + 12 - (index % 2) * 20;
        const labelAnchor = px > width - 150 ? "end" : "start";
        const labelX = labelAnchor === "end" ? px - 9 : px + 9;
        return (
          <g
            key={row.ticker}
            className="b-rrg-point"
            onClick={() => onSelectTicker(row.ticker)}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectTicker(row.ticker);
              }
            }}
            aria-label={`Open ${row.ticker} editorial deep dive`}
          >
            <title>{`Open ${row.ticker} editorial deep dive`}</title>
            <line x1={trailX} x2={px} y1={trailY} y2={py} className={stateToneForClass(row.state)} />
            <circle cx={trailX} cy={trailY} r="2.5" className={stateToneForClass(row.state)} />
            <circle cx={px} cy={py} r="6" className={stateToneForClass(row.state)} />
            <text x={labelX} y={py - 9} textAnchor={labelAnchor}>{row.ticker}</text>
          </g>
        );
      })}
    </svg>
  );
}

function BLeaderboard({ title, rows, onSelectTicker }: { title: string; rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
  return (
    <div className="b-leaderboard">
      <h3>{title}</h3>
      {rows.map((row) => (
        <button type="button" key={row.ticker} onClick={() => onSelectTicker(row.ticker)}>
          <strong>{row.ticker}</strong>
          <span>{row.identity}</span>
          <em className={(row.momentum_pct ?? 0) >= 0 ? "good" : "bad"}>{fmt(row.momentum_pct, 2)}</em>
        </button>
      ))}
    </div>
  );
}

function AOverviewScreen({
  snapshot,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const positions = snapshot.screens.overview?.positions ?? [];
  const transitions = snapshot.screens.overview?.transitions ?? [];
  const navigate = (ticker: string) => {
    onSelectTicker(ticker);
    setActiveScreen("deepdive");
  };
  const warningPositions = positions.filter((position) => {
    const row = rowByTicker(snapshot.rows, position.ticker);
    return row && ["WARNING", "EXIT", "BEARISH_STAGE_4"].includes(row.state);
  });
  const bullishRows = snapshot.rows
    .filter((r) => ["BULLISH", "BULLISH_EARLY", "BULLISH_MATURING"].includes(r.state))
    .sort((a, b) => b.s_score - a.s_score)
    .slice(0, 20);
  return (
    <section className="a-screen">
      <ABlufStrip snapshot={snapshot} />
      <StatusTiles snapshot={snapshot} />
      <TransitionsBanner transitions={transitions} onSelect={navigate} />
      <PicksGrid rows={snapshot.rows} onSelect={navigate} />
      <div className="a-body-grid">
        <ATerminalHeatmap rows={snapshot.rows} onSelectTicker={navigate} />
        <aside className="a-right-rail">
          <section className="a-panel">
            <div className="a-section-head"><strong>TRANSITIONS</strong><span>state changes this run</span><em>{transitions.length} EVENTS</em></div>
            {transitions.slice(0, 12).map((t) => (
              <button type="button" className="a-transition-row" key={`${t.ticker}-${t.date}-${t.to}`} onClick={() => navigate(t.ticker)}>
                <i className={statusClass(t.to)} />
                <strong>{t.ticker}</strong>
                <span className="a-tr-arrow">{t.from.replace(/_/g, " ")} → {t.to.replace(/_/g, " ")}</span>
                <em>{t.date}</em>
              </button>
            ))}
            {!transitions.length ? <p className="a-empty">No state transitions recorded in the latest run.</p> : null}
          </section>
          <section className="a-panel">
            <div className="a-section-head"><strong>YOUR POSITIONS</strong><span>saved local portfolio</span><em>{positions.length} HOLDINGS</em></div>
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
            {!positions.length ? <p className="a-empty">No saved positions. Add tickers to your watchlist.</p> : null}
            {warningPositions.length > 0 && (
              <p className="a-callout">Action this week: {warningPositions.map((p) => p.ticker).join(", ")} need review — WARNING/EXIT gates.</p>
            )}
          </section>
          <section className="a-panel">
            <div className="a-section-head"><strong>BULLISH COHORT</strong><span>ranked by S-score</span><em>{bullishRows.length} SETUPS</em></div>
            {bullishRows.map((row) => (
              <button type="button" className="a-transition-row" key={row.ticker} onClick={() => navigate(row.ticker)}>
                <i className="good" />
                <strong>{row.ticker}</strong>
                <span>{row.identity}</span>
                <em>{row.state.replaceAll("_", " ")} · {row.s_score >= 0 ? "+" : ""}{row.s_score.toFixed(2)}</em>
              </button>
            ))}
            {!bullishRows.length ? <p className="a-empty">No bullish setups in current run — market in risk-off.</p> : null}
          </section>
        </aside>
      </div>
    </section>
  );
}

function ADeepDiveScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const focus = rowByTicker(snapshot.rows, selectedTicker) ?? snapshot.focus;
  if (!focus) return <p className="a-empty">Run a dashboard refresh to persist a focus row.</p>;
  const peers = snapshot.rows.filter((row) => row.asset_class === focus.asset_class).sort((a, b) => b.s_score - a.s_score);
  const rank = peers.findIndex((row) => row.ticker === focus.ticker) + 1;
  const gates = gateRows(focus);
  return (
    <section className="a-screen a-deep">
      <header className="a-deep-head">
        <div><span>DEEP DIVE / {focus.asset_class}</span><h1>{focus.ticker}</h1><p>{focus.identity}</p></div>
        <em className={`a-state ${stateToneForClass(focus.state)}`}>{focus.state.replaceAll("_", " ")}</em>
      </header>
      <div className="a-lead-grid">
        <section className="a-panel a-composite">
          <div className="a-section-head"><strong>COMPOSITE FORWARD-OUTLOOK</strong><span>rank {rank || "n/a"} of {peers.length || snapshot.rows.length}</span><em>{focus.quadrant}</em></div>
          <div className="a-big-score"><strong className={focus.s_score >= 0 ? "good" : "bad"}>{fmt(focus.s_score)}</strong><span>S-score</span><p>{fieldNarrative(focus)} The model combines momentum, trend, relative strength, macro tilt, and flow evidence from the latest saved run.</p></div>
          <ACompositeBreakdown row={focus} />
          <APillarTerminalGrid row={focus} />
        </section>
        <aside className="a-panel a-gates">
          <div className="a-section-head"><strong>STATE GATES</strong><span>engine-derived checklist</span><em>{gates.filter((gate) => gate.ok === false).length} TRIPPED</em></div>
          {gates.map((gate) => (
            <div className="a-gate-row" key={gate.label}>
              <i className={gate.ok === true ? "ok" : gate.ok === false ? "fail" : "neutral"}>{gate.ok === true ? "OK" : gate.ok === false ? "X" : "-"}</i>
              <span>{gate.label}</span>
              <strong>{gate.detail}</strong>
            </div>
          ))}
          <p className="a-callout">Next escalation watches price below 30wMA, Mansfield RS below zero, CMF below -0.10, or RRG deterioration. Current readings: Mansfield {fmt(payloadNumber(focus, "mansfield_rs"), 2)}, CMF {fmt(focus.cmf21, 2)}, RRG {focus.quadrant}.</p>
        </aside>
      </div>
      <div className="a-chart-grid">
        <section className="a-panel">
          <div className="a-section-head"><strong>WEEKLY PRICE vs 30-WEEK SMA</strong><span>Weinstein evidence</span><em>{passText(payloadBool(focus, "above_30wma")).toUpperCase()}</em></div>
          <div className="a-evidence-grid">
            <div><span>Stage</span><strong>{fmt(payloadNumber(focus, "stage"), 0)}</strong></div>
            <div><span>Above 30wMA</span><strong>{passText(payloadBool(focus, "above_30wma"))}</strong></div>
            <div><span>MA slope</span><strong>{passText(payloadBool(focus, "ma_slope_pos"))}</strong></div>
            <div><span>Mansfield</span><strong>{fmt(payloadNumber(focus, "mansfield_rs"), 2)}</strong></div>
          </div>
          <p className="a-callout">Price and trend gates are read from the latest saved methodology snapshot. Cached chart routes remain available in the default and C deep dives.</p>
        </section>
        <APeerRank rows={peers} focusTicker={focus.ticker} onSelectTicker={onSelectTicker} />
      </div>
    </section>
  );
}

function ARotationScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const sectors = snapshot.screens.rotation?.sectors ?? snapshot.rows.filter((row) => row.asset_class === "US Sectors");
  const rows = sectors.length ? sectors : snapshot.rows;
  const flowRows = [...rows].sort((a, b) => Math.abs(rowPressure(b)) - Math.abs(rowPressure(a))).slice(0, 10);
  return (
    <section className="a-screen a-rotation">
      <header className="a-rotation-head"><h1>ROTATION MAP</h1><span>{rows.length} rows | selected {selectedTicker}</span></header>
      <div className="a-rotation-grid">
        <ARrgTerminal rows={rows} onSelectTicker={(ticker) => {
          onSelectTicker(ticker);
          setActiveScreen("deepdive");
        }} />
        <AMomentumTerminal rows={rows} onSelectTicker={(ticker) => {
          onSelectTicker(ticker);
          setActiveScreen("deepdive");
        }} />
      </div>
      <div className="a-lower-grid">
        <section className="a-panel">
          <div className="a-section-head"><strong>INSTITUTIONAL FLOW DETAIL | PILLAR 7</strong><span>CMF | F-score | composite pressure</span><em>LEADS PRICE 1-3 WK</em></div>
          {flowRows.map((row) => (
            <button type="button" className="a-flow-row" key={row.ticker} onClick={() => {
              onSelectTicker(row.ticker);
              setActiveScreen("deepdive");
            }}>
              <strong>{row.ticker}</strong><span>{row.identity}</span><em>{flowNarrative(row)}</em>
            </button>
          ))}
        </section>
        <section className="a-panel">
          <div className="a-section-head"><strong>MACRO | BUSINESS CYCLE</strong><span>persisted run context</span><em>{String(snapshot.run?.metadata?.cycle_phase || "LIVE").toUpperCase()}</em></div>
          <div className="a-macro-grid">
            <div><span>Universe</span><strong>{snapshot.summary.universe_count}</strong></div>
            <div><span>Leading</span><strong>{snapshot.summary.quadrant_counts.Leading ?? 0}</strong></div>
            <div><span>Warnings</span><strong>{snapshot.summary.state_counts.WARNING ?? 0}</strong></div>
            <div><span>Exit</span><strong>{snapshot.summary.state_counts.EXIT ?? 0}</strong></div>
          </div>
          <p className="a-callout">Macro context is persisted from the run journal. The rotation and flow rows on this screen are derived from current snapshot scores and gates, not static handoff fixtures.</p>
        </section>
      </div>
    </section>
  );
}

function HandoffAScreens({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload;
}) {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("overview");
  const initialTicker = snapshot.focus?.ticker || snapshot.rows[0]?.ticker || "";
  const [selectedTicker, setSelectedTicker] = useState(initialTicker);
  return (
    <div className="a-shell" data-presentation="handoff-a">
      <ATopBar activeScreen={activeScreen} setActiveScreen={setActiveScreen} generatedAt={snapshot.generated_at} />
      {activeScreen === "overview" ? (
        <AOverviewScreen snapshot={snapshot} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
      {activeScreen === "deepdive" ? (
        <ADeepDiveScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
      {activeScreen === "rotation" ? (
        <ARotationScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
    </div>
  );
}

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

function BNumberRow({ label, value, note, tone = "neutral" }: { label: string; value: string; note: string; tone?: "good" | "bad" | "warn" | "neutral" }) {
  return (
    <div className="b-number-row">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      <em>{note}</em>
    </div>
  );
}

function BSectionRule({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="b-section-rule">
      <h2>{title}</h2>
      {sub ? <p>{sub}</p> : null}
    </div>
  );
}

function BOverviewScreen({
  snapshot,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const leaders = snapshot.screens.overview?.leaders ?? [];
  const risks = snapshot.screens.overview?.risks ?? [];
  const actions = snapshot.screens.overview?.actions ?? [];
  const positions = snapshot.screens.overview?.positions ?? [];
  const transitions = snapshot.screens.overview?.transitions ?? [];
  const exits = snapshot.summary.state_counts.EXIT ?? 0;
  const bears = snapshot.summary.state_counts.BEARISH_STAGE_4 ?? 0;
  const warnings = snapshot.summary.state_counts.WARNING ?? 0;
  const bullish = snapshot.summary.state_counts.STAGE_2_BULLISH ?? 0;
  const lead = leaders[0]?.display_label || leaders[0]?.ticker || "the leading cohort";
  const risk = risks[0]?.display_label || risks[0]?.ticker || "the risk queue";
  const stories = actions.length ? actions.slice(0, 3) : risks.slice(0, 3).map((row) => ({
    ticker: row.ticker,
    identity: row.identity,
    action: row.state,
    rationale: fieldNarrative(row),
    decision_type: "state",
    payload: {},
  } as SnapshotDecision));
  return (
    <section className="b-screen b-overview">
      <div className="b-tape"><strong>LIVE</strong><span>{snapshot.run?.provider || "provider"} snapshot</span><span>{snapshot.generated_at}</span><span>{snapshot.summary.universe_count} instruments</span></div>
      <div className="b-headline-grid">
        <div>
          <span className="b-kicker">Today's read | model brief</span>
          <h1>{lead} is leading.<br /><em>{risk} needs attention.</em></h1>
          <p>The editorial view translates the same seven-pillar methodology into plain-language market notes. Counts, tickers, and actions come from the latest persisted run journal, not from handoff fixtures.</p>
          <small>BY THE MODEL | {snapshot.summary.universe_count} INSTRUMENTS | 7 PILLARS | POSTED {snapshot.run?.started_at_utc || snapshot.generated_at}</small>
        </div>
        <aside className="b-numbers">
          <h3>By the numbers</h3>
          <BNumberRow label="Exits / bear rows" value={String(exits + bears)} note={`${exits} exit | ${bears} bear`} tone="bad" />
          <BNumberRow label="Active warnings" value={String(warnings)} note="state-machine caution" tone="warn" />
          <BNumberRow label="Bullish cohort" value={String(bullish)} note="Stage 2 bullish" tone="good" />
          <BNumberRow label="Leading quadrant" value={String(snapshot.summary.quadrant_counts.Leading ?? 0)} note="RRG leadership" tone="good" />
          <BNumberRow label="Weakening quadrant" value={String(snapshot.summary.quadrant_counts.Weakening ?? 0)} note="rotation risk" tone="warn" />
          <BNumberRow label="Provider" value={snapshot.run?.provider || "n/a"} note="latest run" />
        </aside>
      </div>
      <div className="b-main-grid">
        <main>
          <TransitionsBanner
            transitions={transitions}
            onSelect={(ticker) => {
              onSelectTicker(ticker);
              setActiveScreen("deepdive");
            }}
            light={true}
            title="This week's transitions"
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
        </main>
        <aside className="b-side">
          <BSectionRule title="This week's transitions" />
          <div className="b-brief-list b-transitions-list">
            {transitions.slice(0, 6).map((t) => (
              <button type="button" key={`${t.ticker}-${t.date}-${t.to}`} onClick={() => {
                onSelectTicker(t.ticker);
                setActiveScreen("deepdive");
              }}>
                <i className={statusClass(t.to)} />
                <strong>{t.ticker}</strong>
                <span>{t.from.replace(/_/g, " ")} → {t.to.replace(/_/g, " ")}</span>
                <em>{t.date}</em>
              </button>
            ))}
            {!transitions.length ? <p>No state transitions in the latest run.</p> : null}
          </div>
          <BSectionRule title="Your positions" />
          <div className="b-position-box">
            {positions.slice(0, 7).map((position) => {
              const row = rowByTicker(snapshot.rows, position.ticker);
              return (
                <button type="button" key={`${position.source_name}-${position.ticker}`} onClick={() => {
                  onSelectTicker(position.ticker);
                  setActiveScreen("deepdive");
                }}>
                  <i className={stateToneForClass(row?.state || "")} />
                  <strong>{position.ticker}</strong>
                  <span>{position.identity}</span>
                  <em>{row?.state.replaceAll("_", " ") || "not in universe"}</em>
                </button>
              );
            })}
            {!positions.length ? <p>No saved local portfolio is available yet.</p> : null}
          </div>
          <BSectionRule title="Bullish cohort" />
          <div className="b-brief-list">
            {leaders.slice(0, 8).map((row) => (
              <button type="button" key={row.ticker} onClick={() => {
                onSelectTicker(row.ticker);
                setActiveScreen("deepdive");
              }}>
                <strong>{row.ticker}</strong><span>{row.identity}</span><em>{fmt(row.s_score)}</em>
              </button>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function BDeepDiveScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
}) {
  const focus = rowByTicker(snapshot.rows, selectedTicker) ?? snapshot.focus;
  if (!focus) return <p className="b-empty">Run a dashboard refresh to persist a focus row.</p>;
  const peers = snapshot.rows.filter((row) => row.asset_class === focus.asset_class).sort((a, b) => b.s_score - a.s_score);
  const gates = gateRows(focus);
  const rank = peers.findIndex((row) => row.ticker === focus.ticker) + 1;
  const tripped = gates.filter((gate) => gate.ok === false);
  const nextTicker = peers[(Math.max(rank - 1, 0) + 1) % Math.max(peers.length, 1)]?.ticker || snapshot.rows.find((row) => row.ticker !== focus.ticker)?.ticker || focus.ticker;
  const strongest = numericPillars(focus).slice().sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0];
  return (
    <section className="b-screen b-article">
      <header className="b-article-head">
        <span className="b-kicker">{focus.asset_class} | {focus.state.replaceAll("_", " ")} | forward outlook</span>
        <h1>{focus.ticker}: price says {focus.s_score >= 0 ? "fine." : "careful."}<br /><em>{focus.f_score >= 0 ? "Flow still helps." : "Flow says watch."}</em></h1>
        <p>{focus.identity}. {fieldNarrative(focus)} The article version keeps the mechanical gates intact, but reads the live values as a plain-English market note.</p>
        <small>BY THE MODEL | LAST SNAPSHOT {snapshot.run?.started_at_utc || snapshot.generated_at} | RANK {rank || "n/a"} OF {peers.length || snapshot.rows.length} {focus.asset_class.toUpperCase()}</small>
      </header>
      <div className="b-pull-strip">
        <div><strong className={focus.s_score >= 0 ? "good" : "bad"}>{fmt(focus.s_score)}</strong><span>COMPOSITE S | RANK {rank || "n/a"}</span></div>
        <div><strong className={focus.f_score >= 0 ? "good" : "bad"}>{fmt(focus.f_score)}</strong><span>FLOW F</span></div>
        <div><strong>{fmt(focus.momentum_pct, 2)}</strong><span>12-1 MOMENTUM</span></div>
        <div><strong className="warn">{focus.quadrant}</strong><span>RRG QUAD</span></div>
        <p>{strongest ? `${strongest[0].replaceAll("_", " ")} is the largest current pillar by magnitude.` : "The live pillar stack defines the article."} {tripped.length ? `${tripped.length} gate${tripped.length === 1 ? "" : "s"} are tripped.` : "No explicit gate is tripped."}</p>
      </div>
      <div className="b-article-grid">
        <main>
          <div className="b-article-intro">
            <p>The model's call on {focus.ticker} is a live snapshot of seven signals, not a single opinion. Composite S is {fmt(focus.s_score)}, flow F is {fmt(focus.f_score)}, momentum is {fmt(focus.momentum_pct, 2)}, and the RRG quadrant is {focus.quadrant}.</p>
            <p>Read the paragraphs below as the audit trail: which pillars are carrying the setup, which are dragging it, and which gates would force the state machine to escalate.</p>
          </div>
          <BSectionRule title="The seven pillars, explained" sub="Each contribution is a signed, weighted model input from the latest saved run." />
          <div className="b-pillar-stack">
            {numericPillars(focus).map(([key, value], index) => (
              <BArticlePillarParagraph row={focus} pillarKey={key} value={value} index={index} key={key} />
            ))}
          </div>
          <BSectionRule title="What would escalate this state" sub="Same engine gates, styled as the article's decision table." />
          <div className="b-gate-table">
            {gates.map((gate) => (
              <div key={gate.label}>
                <i className={gate.ok === true ? "ok" : gate.ok === false ? "fail" : "neutral"}>{gate.ok === true ? "OK" : gate.ok === false ? "X" : "-"}</i>
                <span>{gate.label}</span>
                <strong className={gate.ok === true ? "good" : gate.ok === false ? "bad" : "warn"}>{gate.ok === true ? "Not tripped" : gate.ok === false ? "Tripped" : "Unknown"}</strong>
                <em>{gate.detail}</em>
              </div>
            ))}
            <p>{tripped.length ? `${focus.ticker} has ${tripped.length} tripped gate${tripped.length === 1 ? "" : "s"}: ${tripped.map((gate) => gate.label).join(", ")}.` : `${focus.ticker} has no explicit tripped gate in the saved evidence. Keep watching RRG deterioration, CMF below -0.10, and price below the 30-week average.`}</p>
          </div>
        </main>
        <aside className="b-article-side">
          <section>
            <h3>Weekly price vs 30wMA</h3>
            <TickerPriceChartPanel row={focus} />
          </section>
          <section>
            <h3>CMF + OBV</h3>
            <TickerFlowChartPanels row={focus} />
          </section>
          <section>
            <h3>Related setups</h3>
            {peers.slice(0, 7).map((row) => (
              <button type="button" key={row.ticker} onClick={() => onSelectTicker(row.ticker)}>
                <strong>{row.ticker}</strong><span>{row.identity}</span><em>{fmt(row.s_score)}</em>
              </button>
            ))}
          </section>
        </aside>
      </div>
      <footer className="b-article-footer">
        <span>The Sentiment Brief | Deep-dive</span>
        <button type="button" onClick={() => onSelectTicker(nextTicker)}>Next {nextTicker}</button>
      </footer>
    </section>
  );
}

function BArticlePillarParagraph({
  row,
  pillarKey,
  value,
  index,
}: {
  row: SnapshotRow;
  pillarKey: string;
  value: number;
  index: number;
}) {
  const supportive = value >= 0;
  const label = bPillarLabel(pillarKey);
  return (
    <article className="b-pillar-para">
      <div className="b-pillar-num"><strong>{index + 1}</strong><span>PILLAR</span></div>
      <div>
        <header>
          <h3>{label}</h3>
          <span>{bPillarWeight(pillarKey)}</span>
          <strong className={supportive ? "good" : "bad"}>{fmt(value, 3)}</strong>
        </header>
        <p>{bPillarNarrative(row, pillarKey, value)}</p>
      </div>
    </article>
  );
}

function bPillarLabel(key: string): string {
  const labels: Record<string, string> = {
    breadth_50d: "Binary filters and breadth",
    cmf21: "Institutional flow",
    cycle_tilt: "Business-cycle tilt",
    mansfield_rs: "Mansfield relative strength",
    mom_12_1: "12-month momentum, skip-1",
    rs_momentum: "Relative-rotation RS-Momentum",
    rs_ratio: "Relative-rotation RS-Ratio",
    S: "Composite score",
    F: "Flow score",
    MOM: "Momentum",
    RSR: "Relative-strength ratio",
    RSM: "Relative-strength momentum",
    CMF: "Chaikin money flow",
  };
  return labels[key] || key.replaceAll("_", " ");
}

function bPillarWeight(key: string): string {
  const weights: Record<string, string> = {
    mom_12_1: "w 22%",
    mansfield_rs: "w 12%",
    rs_ratio: "w 15%",
    rs_momentum: "w 8%",
    breadth_50d: "w 12%",
    cycle_tilt: "w 8%",
    cmf21: "w 23%",
  };
  return weights[key] || "live";
}

function bPillarNarrative(row: SnapshotRow, key: string, value: number): string {
  const direction = value >= 0 ? "supports" : "drags on";
  if (key === "mom_12_1" || key === "MOM") {
    return `${row.ticker} momentum is ${fmt(row.momentum_pct, 2)} in the saved run. This pillar ${direction} the article because persistent winners tend to keep leadership until price momentum fades.`;
  }
  if (key === "mansfield_rs" || key === "RSR") {
    return `Mansfield relative strength is ${fmt(payloadNumber(row, "mansfield_rs"), 2)}. Positive relative strength says the ticker is outperforming its benchmark; a negative or falling reading is often the first warning before price breaks.`;
  }
  if (key === "rs_ratio") {
    return `RRG RS-Ratio is ${fmt(row.rs_ratio, 1)}. Readings above 100 mean relative leadership is still present; compression toward 100 means the leadership cushion is narrowing.`;
  }
  if (key === "rs_momentum" || key === "RSM") {
    return `RRG momentum is ${fmt(row.rs_momentum, 1)} and the quadrant is ${row.quadrant}. That tells whether relative leadership is accelerating or fading over the next rotation window.`;
  }
  if (key === "breadth_50d") {
    return `Breadth and trend filters currently read ${fmt(payloadNumber(row, "breadth_50d"), 2)}. This pillar ${direction} the setup by checking whether enough underlying trend evidence confirms the headline score.`;
  }
  if (key === "cycle_tilt") {
    return `Business-cycle tilt is ${fmt(value, 3)}. It adjusts the score for the current macro phase, helping sectors that usually fit the phase and trimming those that historically struggle there.`;
  }
  if (key === "cmf21" || key === "CMF" || key === "F") {
    return `Flow is the institutional-sponsorship read: CMF is ${fmt(row.cmf21, 2)} and F-score is ${fmt(row.f_score, 2)}. Positive flow confirms demand; negative flow warns before price-based gates may react.`;
  }
  return `This live pillar value is ${fmt(value, 3)} and ${direction} ${row.ticker}'s current composite score. It is included directly from the latest persisted methodology snapshot.`;
}

function BRotationScreen({
  snapshot,
  selectedTicker,
  onSelectTicker,
  setActiveScreen,
}: {
  snapshot: DashboardSnapshotPayload;
  selectedTicker: string;
  onSelectTicker: (ticker: string) => void;
  setActiveScreen: (screen: ScreenId) => void;
}) {
  const sectors = snapshot.screens.rotation?.sectors ?? snapshot.rows.filter((row) => row.asset_class === "US Sectors");
  const rows = sectors.length ? sectors : snapshot.rows;
  const leaders = [...snapshot.rows].sort((a, b) => (b.momentum_pct ?? 0) - (a.momentum_pct ?? 0)).slice(0, 10);
  const laggards = [...snapshot.rows].sort((a, b) => (a.momentum_pct ?? 0) - (b.momentum_pct ?? 0)).slice(0, 10);
  const leadingNames = rows.filter((row) => row.quadrant === "Leading").slice(0, 3).map((row) => row.ticker).join(", ") || "leadership";
  const weakeningNames = rows.filter((row) => row.quadrant === "Weakening").slice(0, 3).map((row) => row.ticker).join(", ") || "weakening rows";
  const openDeepDive = (ticker: string) => {
    onSelectTicker(ticker);
    setActiveScreen("deepdive");
  };
  return (
    <section className="b-screen b-map">
      <header className="b-article-head compact">
        <span className="b-kicker">The map | weekly | US sectors</span>
        <h1>Where the money is going,<br /><em>and where it has been.</em></h1>
        <p>The relative-rotation graph maps strength against rate of change. Read clockwise: leaders weaken, weakeners lag, laggards improve, improvers lead.</p>
      </header>
      <div className="b-map-grid">
        <main>
          <div className="b-figure-card">
            <BRrgEditorial rows={rows} onSelectTicker={(ticker) => {
              onSelectTicker(ticker);
              setActiveScreen("deepdive");
            }} />
            <p><strong>The story of this run.</strong> {leadingNames} remain in or near leadership while {weakeningNames} show the weaker side of the clockwise rotation. The selected focus is {selectedTicker}.</p>
          </div>
          <BSectionRule title="Cross-sectional leaderboard" sub="12-1 momentum ranking, all instruments." />
          <div className="b-leaderboards">
            <BLeaderboard title="LEADERS" rows={leaders} onSelectTicker={openDeepDive} />
            <BLeaderboard title="LAGGARDS" rows={laggards} onSelectTicker={openDeepDive} />
          </div>
        </main>
        <aside className="b-side">
          <section className="b-phase-box">
            <h3>The phase</h3>
            <div className="b-phase-row">{["EARLY", "MID", "LATE", "RECESS"].map((phase) => <span key={phase} className={String(snapshot.run?.metadata?.cycle_phase || "").toUpperCase() === phase ? "active" : ""}>{phase}</span>)}</div>
            <p>Run provider: {snapshot.run?.provider || "unknown"}. Macro context is persisted from the run journal; this view does not fetch providers during render.</p>
          </section>
          <BSectionRule title="Where the flow went" />
          <div className="b-flow-items">
            {rows.slice().sort((a, b) => Math.abs(rowPressure(b)) - Math.abs(rowPressure(a))).slice(0, 4).map((row) => (
              <article key={row.ticker}>
                <h3>{row.ticker} | {row.identity}</h3>
                <p>{flowNarrative(row)}</p>
              </article>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}

function HandoffBScreens({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload;
}) {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("overview");
  const initialTicker = snapshot.focus?.ticker || snapshot.rows[0]?.ticker || "";
  const [selectedTicker, setSelectedTicker] = useState(initialTicker);
  return (
    <div className="b-shell" data-presentation="handoff-b">
      <BMasthead activeScreen={activeScreen} setActiveScreen={setActiveScreen} compact={activeScreen !== "overview"} />
      {activeScreen === "overview" ? (
        <BOverviewScreen snapshot={snapshot} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
      {activeScreen === "deepdive" ? (
        <BDeepDiveScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
      {activeScreen === "rotation" ? (
        <BRotationScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
    </div>
  );
}

function HandoffCScreens({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload;
}) {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("overview");
  const initialTicker = snapshot.focus?.ticker || snapshot.rows[0]?.ticker || "";
  const [selectedTicker, setSelectedTicker] = useState(initialTicker);
  return (
    <div className="c-shell" data-presentation="handoff-c">
      <CTopBar activeScreen={activeScreen} setActiveScreen={setActiveScreen} generatedAt={snapshot.generated_at} />
      {activeScreen === "overview" ? (
        <COverviewScreen snapshot={snapshot} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
      {activeScreen === "deepdive" ? (
        <CDeepDiveScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
      ) : null}
      {activeScreen === "rotation" ? (
        <CRotationScreen snapshot={snapshot} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} setActiveScreen={setActiveScreen} />
      ) : null}
    </div>
  );
}

export default function DashboardScreensClient({
  snapshot,
  backtestArtifacts = null,
  presentation = "default",
}: {
  snapshot: DashboardSnapshotPayload | null;
  backtestArtifacts?: BacktestArtifactsPayload | null;
  presentation?: PresentationMode;
}) {
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

  if (presentation === "admin") {
    return (
      <div className="screen-stack">
        <PortfolioAnalyzerPanel onSelectTicker={() => {}} />
        <BacktestArtifactPanel payload={backtestArtifacts} />
      </div>
    );
  }

  if (presentation === "handoff-a") {
    return <HandoffAScreens snapshot={snapshot} />;
  }

  if (presentation === "handoff-b") {
    return <HandoffBScreens snapshot={snapshot} />;
  }

  if (presentation === "handoff-c") {
    return <HandoffCScreens snapshot={snapshot} />;
  }

  return (
    <div className="screen-stack">
      <PortfolioAnalyzerPanel onSelectTicker={setSelectedTicker} />
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
      <BacktestArtifactPanel payload={backtestArtifacts} />
    </div>
  );
}
