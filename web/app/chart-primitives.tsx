"use client";

import type { SnapshotRow } from "../lib/api";
import Sparkline from "../components/Sparkline";

type PillarKey = "mom_12_1" | "mansfield_rs" | "rs_ratio" | "rs_momentum" | "breadth_50d" | "cycle_tilt" | "cmf21";

type PillarDef = {
  key: PillarKey;
  code: string;
  fullName: string;
  label: string;
  hue: string;
  weight: number;
  reading: string;
  evidence: string;
};

type PillarContribution = PillarDef & {
  raw: number;
  contribution: number;
};

const PILLARS: PillarDef[] = [
  { key: "mom_12_1", code: "MOM", fullName: "12-1 Momentum", label: "Momentum", hue: "#2e6fa3", weight: 0.22, reading: "12-1 price momentum contribution", evidence: "Jegadeesh & Titman 1993" },
  { key: "mansfield_rs", code: "MANS", fullName: "Mansfield RS", label: "Mansfield RS", hue: "#5d8ec0", weight: 0.12, reading: "relative strength against the benchmark", evidence: "Weinstein 1988" },
  { key: "rs_ratio", code: "RS-R", fullName: "RRG RS-Ratio", label: "RS ratio", hue: "#3f8862", weight: 0.15, reading: "RRG relative-strength ratio", evidence: "de Kempenaer 2004" },
  { key: "rs_momentum", code: "RS-M", fullName: "RRG RS-Momentum", label: "RS momentum", hue: "#6da884", weight: 0.08, reading: "RRG relative-strength momentum", evidence: "classic rotation signal" },
  { key: "breadth_50d", code: "FILT", fullName: "Binary Filters", label: "Trend filter", hue: "#9d7838", weight: 0.12, reading: "market breadth and trend filter", evidence: "Faber + Stage2 + Antonacci" },
  { key: "cycle_tilt", code: "CYC", fullName: "Business-Cycle Tilt", label: "Cycle tilt", hue: "#a85a3a", weight: 0.08, reading: "business-cycle adjustment", evidence: "Stovall 1996 / Fidelity" },
  { key: "cmf21", code: "FLOW", fullName: "Institutional Flow", label: "Flow", hue: "#7a3a5d", weight: 0.23, reading: "money-flow pressure", evidence: "Chaikin / Granville / Chordia-Swaminathan" },
];

const CLASS_ORDER = [
  "US Sectors",
  "US Industries",
  "Countries",
  "Factors",
  "Themes",
  "Crypto",
  "Mega-Cap Stocks",
  "Other",
];

const C1_VISIBLE_ROW_TARGET = 67;
const C1_MIN_VISIBLE_ROWS_PER_CLASS = 3;

function classRank(assetClass: string): number {
  const index = CLASS_ORDER.indexOf(assetClass);
  return index >= 0 ? index : CLASS_ORDER.length;
}

function stateLabel(state: string): string {
  return state.replaceAll("_", " ");
}

function compactStateLabel(state: string): string {
  const normalized = state.toUpperCase();
  if (normalized.includes("STAGE_2") || normalized.includes("BULLISH") || normalized === "BUY") return "BULLISH";
  if (normalized.includes("WARNING") || normalized.includes("WARN")) return "WARN";
  if (normalized.includes("EXIT")) return "EXIT";
  if (normalized.includes("BEAR")) return "BEAR";
  if (normalized.includes("BASE")) return "BASE";
  if (normalized.includes("HOLD")) return "HOLD";
  return stateLabel(state);
}

function stateTone(state: string): "good" | "warn" | "bad" | "hold" {
  const normalized = state.toLowerCase();
  if (normalized.includes("bullish") || normalized === "buy") return "good";
  if (normalized.includes("exit") || normalized.includes("bear")) return "bad";
  if (normalized.includes("warn")) return "warn";
  return "hold";
}

function numeric(value: number | string | boolean | null | undefined): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function pillarValue(row: SnapshotRow, key: PillarKey): number {
  const value = numeric(row.pillar_scores[key]);
  if (value === null) return 0;
  if (key === "mom_12_1") return Math.max(-1, Math.min(1, value));
  if (key === "mansfield_rs") return Math.max(-1, Math.min(1, value / 100));
  if (key === "rs_ratio" || key === "rs_momentum") return Math.max(-1, Math.min(1, (value - 100) / 30));
  if (key === "breadth_50d") return Math.max(-1, Math.min(1, (value - 0.5) * 2));
  if (key === "cmf21") return Math.max(-1, Math.min(1, value / 0.25));
  return Math.max(-1, Math.min(1, value));
}

export function pillarContributions(row: SnapshotRow): PillarContribution[] {
  const raw = PILLARS.map((pillar) => ({ ...pillar, raw: pillarValue(row, pillar.key) }));
  const rawSum = raw.reduce((total, pillar) => total + pillar.raw, 0);
  if (Math.abs(rawSum) < 0.000001) {
    const equal = row.s_score / raw.length;
    return raw.map((pillar) => ({ ...pillar, contribution: equal }));
  }
  const scale = row.s_score / rawSum;
  return raw.map((pillar) => ({ ...pillar, contribution: pillar.raw * scale }));
}

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function signedFmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function momentumFmt(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  const scaled = Math.abs(value) <= 1 ? value * 100 : value;
  return `${scaled >= 0 ? "+" : ""}${scaled.toFixed(0)}%`;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function PillarLegend() {
  return (
    <div className="pillar-legend" aria-label="Pillar legend">
      {PILLARS.map((pillar) => (
        <span key={pillar.key}>
          <i style={{ background: pillar.hue }} />
          {pillar.code} <small>{Math.round(pillar.weight * 100)}%</small>
        </span>
      ))}
    </div>
  );
}

function LightStatePill({ state }: { state: string }) {
  return <span className={`light-state-pill ${stateTone(state)}`}>{compactStateLabel(state)}</span>;
}

function pillarReading(row: SnapshotRow, pillar: PillarContribution): string {
  if (pillar.key === "mom_12_1") return `${row.ticker} momentum input is ${fmt(pillar.raw, 2)}; this pillar contributes ${fmt(pillar.contribution, 2)} to S.`;
  if (pillar.key === "mansfield_rs") return `Relative strength input is ${fmt(pillar.raw, 2)}; positive values support Stage 2 evidence, negative values weaken it.`;
  if (pillar.key === "rs_ratio") return `RRG ratio is ${fmt(row.rs_ratio, 1)}; above 100 means relative strength is ahead of the benchmark.`;
  if (pillar.key === "rs_momentum") return `RRG momentum is ${fmt(row.rs_momentum, 1)} and quadrant is ${row.quadrant}; this captures acceleration or fading leadership.`;
  if (pillar.key === "breadth_50d") return `Trend-filter input is ${fmt(pillar.raw, 2)}; higher readings mean more confirmation from breadth and trend gates.`;
  if (pillar.key === "cycle_tilt") return `Cycle tilt input is ${fmt(pillar.raw, 2)}; macro context adjusts how much the setup is favored.`;
  return `CMF flow is ${fmt(row.cmf21, 2)} and F-score is ${fmt(row.f_score, 2)}; flow can confirm or veto price strength.`;
}

function pillarTooltip(row: SnapshotRow, pillar: PillarContribution): string {
  const sign = pillar.contribution >= 0 ? "bullish support" : "bearish drag";
  return `${pillar.code} ${pillar.fullName} for ${row.ticker}: ${pillarReading(row, pillar)} Weight ${Math.round(pillar.weight * 100)}%; normalized input ${fmt(pillar.raw, 2)}; contribution ${fmt(pillar.contribution, 2)} (${sign}).`;
}

function pillarSideTotals(row: SnapshotRow): { positiveTotal: number; negativeTotal: number } {
  const contributions = pillarContributions(row);
  const positiveTotal = contributions
    .filter((pillar) => pillar.contribution > 0)
    .reduce((total, pillar) => total + pillar.contribution, 0);
  const negativeTotal = contributions
    .filter((pillar) => pillar.contribution < 0)
    .reduce((total, pillar) => total + Math.abs(pillar.contribution), 0);
  return { positiveTotal, negativeTotal };
}

function c1VisibleRowCounts(grouped: Record<string, SnapshotRow[]>, classes: string[], target = C1_VISIBLE_ROW_TARGET): Record<string, number> {
  const counts = Object.fromEntries(classes.map((assetClass) => [assetClass, grouped[assetClass]?.length ?? 0]));
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  if (total <= target) return counts;

  const visibleCounts: Record<string, number> = {};
  const activeClasses = classes.filter((assetClass) => counts[assetClass] > 0);
  const minimum = Math.max(1, Math.min(C1_MIN_VISIBLE_ROWS_PER_CLASS, Math.floor(target / Math.max(1, activeClasses.length))));
  let used = 0;
  for (const assetClass of activeClasses) {
    const visible = Math.min(counts[assetClass], minimum);
    visibleCounts[assetClass] = visible;
    used += visible;
  }

  let remaining = Math.max(0, target - used);
  for (const assetClass of activeClasses) {
    if (!remaining) break;
    const count = counts[assetClass];
    const available = count - (visibleCounts[assetClass] ?? 0);
    if (available <= 0) continue;
    const proportional = Math.floor((count / total) * remaining);
    const extra = Math.min(available, Math.max(0, proportional));
    visibleCounts[assetClass] = (visibleCounts[assetClass] ?? 0) + extra;
    remaining -= extra;
  }

  while (remaining > 0) {
    const candidate = activeClasses
      .filter((assetClass) => (visibleCounts[assetClass] ?? 0) < counts[assetClass])
      .sort((a, b) => counts[b] - (visibleCounts[b] ?? 0) - (counts[a] - (visibleCounts[a] ?? 0)))[0];
    if (!candidate) break;
    visibleCounts[candidate] = (visibleCounts[candidate] ?? 0) + 1;
    remaining -= 1;
  }
  return visibleCounts;
}

export function PillarStackBar({ row, maxSide: maxSideOverride }: { row: SnapshotRow; maxSide?: number }) {
  const contributions = pillarContributions(row);
  const { positiveTotal, negativeTotal } = pillarSideTotals(row);
  const maxSide = Math.max(1, maxSideOverride ?? positiveTotal, maxSideOverride ?? negativeTotal);
  const midpoint = 50;
  let positiveOffset = 0;
  let negativeOffset = 0;
  return (
    <div className="pillar-stack" aria-label={`${row.ticker} pillar stack`}>
      <div className="pillar-quarter left" />
      <div className="pillar-quarter right" />
      <div className="pillar-midline" />
      {contributions.map((pillar) => {
        const width = Math.max(2, Math.abs(pillar.contribution) / maxSide * 44);
        let left = midpoint;
        if (pillar.contribution >= 0) {
          left = midpoint + positiveOffset;
          positiveOffset += width;
        } else {
          left = midpoint - negativeOffset - width;
          negativeOffset += width;
        }
        const style = { left: `${left}%`, width: `${width}%`, background: pillar.hue };
        const tooltip = pillarTooltip(row, pillar);
        return (
          <span
            key={pillar.key}
            className="pillar-segment"
            style={style}
            title={tooltip}
            data-tooltip={tooltip}
            data-pillar-code={pillar.code}
            role="img"
            aria-label={tooltip}
          />
        );
      })}
    </div>
  );
}

export function PillarHeatmap({
  rows,
  onSelectTicker,
  sourceNote,
}: {
  rows: SnapshotRow[];
  onSelectTicker: (ticker: string) => void;
  sourceNote?: string;
}) {
  const grouped = rows.reduce<Record<string, SnapshotRow[]>>((acc, row) => {
    const key = row.asset_class || "Other";
    acc[key] = acc[key] || [];
    acc[key].push(row);
    return acc;
  }, {});
  const classes = Object.keys(grouped).sort((a, b) => {
    const rank = classRank(a) - classRank(b);
    return rank || a.localeCompare(b);
  });
  const visibleCounts = c1VisibleRowCounts(grouped, classes);
  const sortedRows = rows.slice().sort((a, b) => b.s_score - a.s_score);
  const heatmapMaxSide = Math.max(
    1,
    ...rows.flatMap((row) => {
      const { positiveTotal, negativeTotal } = pillarSideTotals(row);
      return [positiveTotal, negativeTotal];
    }),
  );
  return (
    <section className="chart-card light-card pillar-heatmap-card" aria-label="Composite pillar-stack heatmap" title={sourceNote}>
      <div className="chart-heading c-heatmap-heading">
        <div>
          <h3>The composite, dissected</h3>
          <span>{rows.length} instruments | sorted by S</span>
          <p>Each row IS the composite. Seven segments to the right of the midline are bullish contributions; segments to the left are bearish. Length encodes magnitude. Read the row to see why the score is what it is.</p>
        </div>
      </div>
      <div className="c-pillar-legend-strip" aria-label="Pillar contribution legend and axis">
        <PillarLegend />
        <span className="composition-axis-copy">bearish left | bullish right</span>
      </div>
      <div className="composition-header">
        <span>TKR</span>
        <span>TREND</span>
        <span>COMPOSITION</span>
        <span>STATE</span>
        <span>S</span>
        <span>MOM</span>
      </div>
      {classes.map((assetClass) => (
        (() => {
          const classRows = grouped[assetClass].slice().sort((a, b) => b.s_score - a.s_score);
          const visible = classRows.slice(0, visibleCounts[assetClass] ?? classRows.length);
          const overflow = classRows.slice(visible.length);
          return (
            <div key={assetClass} className="composition-group">
              <div className="composition-class">
                {assetClass} | {classRows.length} | {classRows.filter((row) => row.s_score > 0).length} positive S
              </div>
              {visible.map((row) => (
                <CompositionRowButton key={row.ticker} row={row} maxSide={heatmapMaxSide} onSelectTicker={onSelectTicker} />
              ))}
              {overflow.length ? (
                <details className="composition-overflow">
                  <summary>{overflow.length} more live rows</summary>
                  {overflow.map((row) => (
                    <CompositionRowButton key={row.ticker} row={row} maxSide={heatmapMaxSide} onSelectTicker={onSelectTicker} />
                  ))}
                </details>
              ) : null}
            </div>
          );
        })()
      ))}
      {!sortedRows.length ? <p className="empty-chart-copy">No saved snapshot rows are available yet.</p> : null}
    </section>
  );
}

function CompositionRowButton({
  row,
  maxSide,
  onSelectTicker,
}: {
  row: SnapshotRow;
  maxSide: number;
  onSelectTicker: (ticker: string) => void;
}) {
  return (
    <button type="button" key={row.ticker} className="composition-row" onClick={() => onSelectTicker(row.ticker)}>
      <strong>{row.ticker}</strong>
      <Sparkline ticker={row.ticker} state={row.state} w={64} h={24} />
      <PillarStackBar row={row} maxSide={maxSide} />
      <LightStatePill state={row.state} />
      <span>{signedFmt(row.s_score)}</span>
      <span>{momentumFmt(row.momentum_pct)}</span>
    </button>
  );
}

export function WaterfallChart({ row }: { row: SnapshotRow }) {
  const contributions = pillarContributions(row);
  const cumulatives = contributions.reduce<number[]>((acc, pillar) => {
    acc.push((acc.at(-1) ?? 0) + pillar.contribution);
    return acc;
  }, [0]);
  const minY = Math.min(...cumulatives, row.s_score, -0.05) - 0.1;
  const maxY = Math.max(...cumulatives, row.s_score, 0.05) + 0.1;
  const width = 1280;
  const height = 280;
  const left = 64;
  const right = 64;
  const top = 30;
  const bottom = 70;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const y = (value: number) => top + (maxY - value) / (maxY - minY || 1) * plotH;
  const zeroY = y(0);
  const stepW = plotW / (contributions.length + 2);
  const colW = stepW * 0.7;

  return (
    <div className="chart-card light-card" aria-label={`${row.ticker} composite waterfall`}>
      <div className="chart-heading">
        <div>
          <h3>The composite, built pillar by pillar</h3>
          <p>Start at zero. Add each pillar contribution. End at the composite. The chart below makes the math visible: which pillars did the work, which dragged.</p>
        </div>
        <strong>S {fmt(row.s_score)}</strong>
      </div>
      <svg className="waterfall-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${row.display_label} waterfall to S score ${fmt(row.s_score)}`}>
        <line x1={left} x2={width - right + 12} y1={zeroY} y2={zeroY} className="axis-line" />
        <text x={20} y={y(maxY) + 4}>{fmt(maxY)}</text>
        <text x={20} y={zeroY + 4}>0.00</text>
        <text x={20} y={y(minY) + 4}>{fmt(minY)}</text>
        <text x={left - 8} y={height - 34} textAnchor="end">0.00</text>
        <text x={left - 8} y={height - 18} textAnchor="end" className="waterfall-weight">START</text>
        {contributions.map((pillar, index) => {
          const previous = cumulatives[index];
          const next = cumulatives[index + 1];
          const x = left + stepW * (index + 1);
          const barY = Math.min(y(previous), y(next));
          const barH = Math.max(3, Math.abs(y(previous) - y(next)));
          const connectorX = x + colW;
          const nextX = index === contributions.length - 1 ? left + stepW * 8 : left + stepW * (index + 2);
          const labelY = pillar.contribution >= 0 ? barY - 8 : barY + barH + 14;
          return (
            <g key={pillar.key}>
              <rect x={x} y={barY} width={colW} height={barH} fill={pillar.hue} opacity={pillar.contribution >= 0 ? 0.95 : 0.55} />
              <line x1={connectorX} x2={nextX} y1={y(next)} y2={y(next)} className="connector-line" />
              <text x={x + colW / 2} y={labelY} textAnchor="middle" className={pillar.contribution >= 0 ? "waterfall-positive" : "waterfall-negative"}>{fmt(pillar.contribution, 2)}</text>
              <text x={x + colW / 2} y={height - 34} textAnchor="middle">{pillar.code}</text>
              <text x={x + colW / 2} y={height - 18} textAnchor="middle" className="waterfall-weight">w {Math.round(pillar.weight * 100)}%</text>
            </g>
          );
        })}
        <rect x={left + stepW * 8} y={Math.min(zeroY, y(row.s_score))} width={colW} height={Math.max(3, Math.abs(zeroY - y(row.s_score)))} className="total-bar" />
        <text x={left + stepW * 8 + colW / 2} y={Math.min(zeroY, y(row.s_score)) - 8} textAnchor="middle">S {fmt(row.s_score)}</text>
        <text x={left + stepW * 8 + colW / 2} y={height - 34} textAnchor="middle">COMPOSITE</text>
        <text x={left + stepW * 8 + colW / 2} y={height - 18} textAnchor="middle" className="waterfall-weight">S</text>
      </svg>
    </div>
  );
}

export function PillarDetailGrid({ row }: { row: SnapshotRow }) {
  const contributions = pillarContributions(row);
  return (
    <section className="chart-card light-card c-pillar-detail" aria-label={`${row.ticker} seven pillar detail`}>
      <div className="c-sec-head">
        <strong>The seven pillars</strong>
        <span>weights sum to 1.00</span>
      </div>
      <div className="pillar-card-grid">
        {contributions.map((pillar) => (
          <div key={pillar.key} className="pillar-card" style={{ borderColor: pillar.hue }}>
            <i style={{ background: pillar.hue }} />
            <div>
              <span>{pillar.fullName} <small>w {Math.round(pillar.weight * 100)}%</small></span>
              <p>{pillarReading(row, pillar)}</p>
              <em>{pillar.evidence}</em>
            </div>
            <strong className={pillar.contribution >= 0 ? "good" : "bad"}>{fmt(pillar.contribution)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function rrgPoint(row: SnapshotRow) {
  const x = row.rs_ratio ?? (row.quadrant === "Leading" || row.quadrant === "Weakening" ? 108 : 92);
  const y = row.rs_momentum ?? (row.quadrant === "Leading" || row.quadrant === "Improving" ? 108 : 92);
  return {
    x: clamp(x, 70, 130),
    y: clamp(y, 70, 130),
  };
}

function stateColor(row: SnapshotRow) {
  const state = row.state.toLowerCase();
  if (state.includes("bullish") || state.includes("buy")) return "#20a47b";
  if (state.includes("exit") || state.includes("bearish")) return "#c74b4b";
  if (state.includes("warn")) return "#d18b25";
  return "#4f8cff";
}

function rrgTooltip(row: SnapshotRow): string {
  const ratio = fmt(row.rs_ratio, 1);
  const momentum = fmt(row.rs_momentum, 1);
  const ratioReading = (row.rs_ratio ?? 100) >= 100 ? "relative strength is above the benchmark" : "relative strength is below the benchmark";
  const momentumReading = (row.rs_momentum ?? 100) >= 100 ? "rotation momentum is improving" : "rotation momentum is fading";
  return `${row.display_label}: ${row.quadrant} quadrant. RS-ratio ${ratio} means ${ratioReading}; RS-momentum ${momentum} means ${momentumReading}. S ${fmt(row.s_score)} and F ${fmt(row.f_score)} summarize composite and flow support.`;
}

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
  const width = 680;
  const height = 420;
  const left = 44;
  const top = 24;
  const plotW = width - 72;
  const plotH = height - 62;
  const x = (value: number) => left + (value - 70) / 60 * plotW;
  const y = (value: number) => top + (130 - value) / 60 * plotH;
  const placedLabels: { x: number; y: number }[] = [];
  const entries = rows.slice(0, 30).map((row, index) => {
    const point = rrgPoint(row);
    const pointX = x(point.x);
    const pointY = y(point.y);
    const anchor: "start" | "end" = point.x > 118 ? "end" : "start";
    const labelX = anchor === "start" ? pointX + 10 : pointX - 10;
    let labelY = clamp(pointY + 4 + ((index % 3) - 1) * 7, top + 22, top + plotH - 14);
    for (let guard = 0; guard < 10; guard += 1) {
      const overlaps = placedLabels.some((label) => Math.abs(label.x - labelX) < 46 && Math.abs(label.y - labelY) < 15);
      if (!overlaps) break;
      const direction = labelY < top + plotH / 2 ? 1 : -1;
      labelY = clamp(labelY + direction * 15, top + 22, top + plotH - 14);
    }
    placedLabels.push({ x: labelX, y: labelY });
    return { row, point, pointX, pointY, labelX, labelY, anchor };
  });
  return (
    <div className="chart-card light-card" aria-label="Relative rotation graph">
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        {meta ? <strong>{meta}</strong> : null}
      </div>
      <svg className="rrg-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="RRG sector rotation chart">
        <rect x={left} y={top} width={plotW} height={plotH} rx={8} className="plot-bg" />
        <line x1={x(100)} x2={x(100)} y1={top} y2={top + plotH} className="axis-line" />
        <line x1={left} x2={left + plotW} y1={y(100)} y2={y(100)} className="axis-line" />
        <text x={left + 10} y={top + 18}>Improving</text>
        <text x={left + plotW - 88} y={top + 18}>Leading</text>
        <text x={left + 10} y={top + plotH - 10}>Lagging</text>
        <text x={left + plotW - 98} y={top + plotH - 10}>Weakening</text>
        {entries.map(({ row, point, pointX, pointY, labelX, labelY, anchor }) => {
          const drift = clamp(row.s_score, -1.5, 1.5) * 2.5;
          const trail = [
            { x: point.x - 5 - drift, y: point.y - 3 + drift },
            { x: point.x - 3 - drift, y: point.y - 2 + drift / 2 },
            { x: point.x - 1, y: point.y - 1 },
            point,
          ];
          const tooltip = rrgTooltip(row);
          return (
            <g
              key={row.ticker}
              className="rrg-point"
              onClick={() => onSelectTicker(row.ticker)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectTicker(row.ticker);
                }
              }}
              aria-label={tooltip}
              data-tooltip={tooltip}
            >
              <title>{tooltip}</title>
              <polyline points={trail.map((p) => `${x(p.x)},${y(p.y)}`).join(" ")} fill="none" stroke={stateColor(row)} strokeOpacity="0.34" strokeWidth="2" />
              <line x1={pointX} x2={labelX + (anchor === "start" ? -4 : 4)} y1={pointY} y2={labelY - 3} className="label-leader" />
              <circle cx={pointX} cy={pointY} r="5" fill={stateColor(row)} />
              <text className="rrg-label" x={labelX} y={labelY} textAnchor={anchor}>{row.ticker}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

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
  const sorted = rows
    .filter((row) => typeof row.momentum_pct === "number")
    .slice()
    .sort((a, b) => (b.momentum_pct ?? 0) - (a.momentum_pct ?? 0))
    .slice(0, 14);
  const maxAbs = Math.max(0.1, ...sorted.map((row) => Math.abs(row.momentum_pct ?? 0)));
  return (
    <div className="chart-card light-card momentum-bars" aria-label="Cross-sectional momentum bars">
      <div className="chart-heading">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        {meta ? <strong>{meta}</strong> : null}
      </div>
      {sorted.map((row) => {
        const value = row.momentum_pct ?? 0;
        const width = Math.max(3, Math.abs(value) / maxAbs * 48);
        return (
          <button type="button" key={row.ticker} className="momentum-row" onClick={() => onSelectTicker(row.ticker)}>
            <strong>{row.ticker}</strong>
            <span className="momentum-track">
              <i
                className={value >= 0 ? "positive" : "negative"}
                style={value >= 0 ? { left: "50%", width: `${width}%` } : { left: `${50 - width}%`, width: `${width}%` }}
              />
            </span>
            <span>{fmt(value, 2)}</span>
          </button>
        );
      })}
    </div>
  );
}

function flowMagnitude(row: SnapshotRow): number {
  return Math.max(0.05, Math.abs(row.f_score || row.cmf21 || row.s_score));
}

function flowLabel(row: SnapshotRow): string {
  const identity = row.identity || row.asset_class || "instrument";
  const compactIdentity = identity.length > 22 ? `${identity.slice(0, 20)}...` : identity;
  return `${row.ticker} | ${compactIdentity}`;
}

function flowTooltip(row: SnapshotRow, side: "outflow" | "inflow"): string {
  const direction = side === "inflow" ? "supporting inflow" : "weakening outflow";
  return `${row.display_label}: ${direction}. F-score ${fmt(row.f_score)}; CMF(21) ${fmt(row.cmf21, 2)}; S ${fmt(row.s_score)}. Higher magnitude means this row is exerting more pressure in the current flow river.`;
}

function flowLaneTooltip(source: SnapshotRow, target: SnapshotRow, width: number, pressure: number): string {
  return `Flow-river lane from ${source.display_label} to ${target.display_label}: relative pressure ${fmt(pressure, 2)} and lane width ${fmt(width, 1)} are derived from current saved F/CMF/S pressure. This is a rotation-pressure map, not a literal cash-transfer ledger.`;
}

export function FlowRiver({ rows }: { rows: SnapshotRow[] }) {
  const outflows = rows
    .filter((row) => (row.f_score < 0 || (row.cmf21 ?? 0) < 0 || row.s_score < 0))
    .slice()
    .sort((a, b) => Math.abs((b.f_score || b.cmf21 || b.s_score)) - Math.abs((a.f_score || a.cmf21 || a.s_score)))
    .slice(0, 5);
  const inflows = rows
    .filter((row) => (row.f_score > 0 || (row.cmf21 ?? 0) > 0 || row.s_score > 0))
    .slice()
    .sort((a, b) => (b.f_score + (b.cmf21 ?? 0) + b.s_score) - (a.f_score + (a.cmf21 ?? 0) + a.s_score))
    .slice(0, 5);
  const pairCount = Math.min(outflows.length, inflows.length);
  const width = 1100;
  const height = 260;
  const leftX = 220;
  const rightX = width - 280;
  const top = 46;
  const rowGap = 38;
  const totalOut = outflows.reduce((total, row) => total + flowMagnitude(row), 0);
  const totalIn = inflows.reduce((total, row) => total + flowMagnitude(row), 0);
  const balancedPressure = Math.min(totalOut, totalIn);
  const maxMagnitude = Math.max(
    0.1,
    ...outflows.map(flowMagnitude),
    ...inflows.map(flowMagnitude),
  );
  return (
    <div className="chart-card light-card" aria-label="Flow river">
      <div className="chart-heading">
        <div>
          <h3>The flow river</h3>
          <p>Data-derived map from current weakest flow/score rows into strongest flow/score rows. Strand width follows relative pressure magnitude.</p>
        </div>
        <strong>{pairCount} lanes | {fmt(balancedPressure, 2)} pressure</strong>
      </div>
      <svg className="flow-river" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Current flow river from weakening to strengthening instruments">
        <defs>
          <linearGradient id="flowRiverGradient" x1="0%" x2="100%" y1="0%" y2="0%">
            <stop offset="0%" stopColor="#b34a4a" stopOpacity="0.52" />
            <stop offset="52%" stopColor="#cfa490" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#1f7a4a" stopOpacity="0.48" />
          </linearGradient>
        </defs>
        <text x="22" y="20">NET OUTFLOWS</text>
        <text x={width - 22} y="20" textAnchor="end">NET INFLOWS</text>
        {outflows.flatMap((source, sourceIndex) => {
          const sourceMagnitude = flowMagnitude(source);
          return inflows.map((target, targetIndex) => {
            const targetMagnitude = flowMagnitude(target);
            const share = sourceMagnitude / Math.max(totalOut, 0.1) * targetMagnitude / Math.max(totalIn, 0.1);
            const y1 = top + sourceIndex * rowGap + (targetIndex - 2) * 2.4;
            const y2 = top + targetIndex * rowGap + (sourceIndex - 2) * 2.4;
            const strokeWidth = Math.max(1.5, share * 130);
            const pressure = share * balancedPressure;
            return (
              <path
                key={`${source.ticker}-${target.ticker}`}
                d={`M ${leftX} ${y1} C ${leftX + 190} ${y1}, ${rightX - 190} ${y2}, ${rightX} ${y2}`}
                fill="none"
                stroke="url(#flowRiverGradient)"
                strokeOpacity="0.2"
                strokeWidth={strokeWidth}
              >
                <title>{flowLaneTooltip(source, target, strokeWidth, pressure)}</title>
              </path>
            );
          });
        })}
        {Array.from({ length: pairCount }).map((_, index) => {
          const source = outflows[index];
          const target = inflows[index];
          const y1 = top + index * rowGap;
          const y2 = top + index * rowGap;
          const strokeWidth = 4 + flowMagnitude(source) / maxMagnitude * 8;
          const pressure = Math.min(flowMagnitude(source), flowMagnitude(target));
          return (
            <path
              key={`primary-${source.ticker}-${target.ticker}`}
              d={`M ${leftX} ${y1} C ${leftX + 190} ${y1}, ${rightX - 190} ${y2}, ${rightX} ${y2}`}
              fill="none"
              stroke="url(#flowRiverGradient)"
              strokeOpacity="0.48"
              strokeWidth={strokeWidth}
            >
              <title>{flowLaneTooltip(source, target, strokeWidth, pressure)}</title>
            </path>
          );
        })}
        {outflows.map((row, index) => {
          const y = top + index * rowGap;
          const h = 12 + flowMagnitude(row) / maxMagnitude * 24;
          const tooltip = flowTooltip(row, "outflow");
          return (
            <g key={`out-${row.ticker}`} aria-label={tooltip} data-tooltip={tooltip}>
              <title>{tooltip}</title>
              <rect className="flow-out-node" x={leftX - 18} y={y - h / 2} width="12" height={h} />
              <text x={leftX - 26} y={y - 2} textAnchor="end">{flowLabel(row)}</text>
              <text x={leftX - 26} y={y + 13} textAnchor="end" className="flow-value">-{fmt(flowMagnitude(row), 2)}</text>
            </g>
          );
        })}
        {inflows.map((row, index) => {
          const y = top + index * rowGap;
          const h = 12 + flowMagnitude(row) / maxMagnitude * 24;
          const tooltip = flowTooltip(row, "inflow");
          return (
            <g key={`in-${row.ticker}`} aria-label={tooltip} data-tooltip={tooltip}>
              <title>{tooltip}</title>
              <rect className="flow-in-node" x={rightX + 6} y={y - h / 2} width="12" height={h} />
              <text x={rightX + 26} y={y - 2}>{flowLabel(row)}</text>
              <text x={rightX + 26} y={y + 13} className="flow-value">+{fmt(flowMagnitude(row), 2)}</text>
            </g>
          );
        })}
        {!pairCount ? <text x="22" y="70">No opposing flow lanes are available in the latest snapshot.</text> : null}
      </svg>
      {pairCount ? (
        <p className="flow-caption">
          Current saved snapshot shows {fmt(balancedPressure, 2)} units of opposing rotation pressure: weakest support is led by {outflows[0].display_label}, while strongest sponsorship is led by {inflows[0].display_label}. Use this as a rotation map, not a literal dollar-transfer ledger.
        </p>
      ) : null}
    </div>
  );
}
