"use client";

import type { SnapshotRow } from "../lib/api";

type PillarKey = "mom_12_1" | "mansfield_rs" | "rs_ratio" | "rs_momentum" | "breadth_50d" | "cycle_tilt" | "cmf21";

type PillarDef = {
  key: PillarKey;
  code: string;
  label: string;
  hue: string;
  reading: string;
};

type PillarContribution = PillarDef & {
  raw: number;
  contribution: number;
};

const PILLARS: PillarDef[] = [
  { key: "mom_12_1", code: "MOM", label: "Momentum", hue: "#4f8cff", reading: "12-1 price momentum contribution" },
  { key: "mansfield_rs", code: "MANS", label: "Mansfield RS", hue: "#20a47b", reading: "relative strength against the benchmark" },
  { key: "rs_ratio", code: "RS-R", label: "RS ratio", hue: "#8f6ee8", reading: "RRG relative-strength ratio" },
  { key: "rs_momentum", code: "RS-M", label: "RS momentum", hue: "#d18b25", reading: "RRG relative-strength momentum" },
  { key: "breadth_50d", code: "FILT", label: "Trend filter", hue: "#61727f", reading: "market breadth and trend filter" },
  { key: "cycle_tilt", code: "CYC", label: "Cycle tilt", hue: "#8e6b4e", reading: "business-cycle adjustment" },
  { key: "cmf21", code: "FLOW", label: "Flow", hue: "#b34a6b", reading: "money-flow pressure" },
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

function classRank(assetClass: string): number {
  const index = CLASS_ORDER.indexOf(assetClass);
  return index >= 0 ? index : CLASS_ORDER.length;
}

function stateLabel(state: string): string {
  return state.replaceAll("_", " ");
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

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function PillarLegend() {
  return (
    <div className="pillar-legend" aria-label="Pillar legend">
      {PILLARS.map((pillar) => (
        <span key={pillar.key}>
          <i style={{ background: pillar.hue }} />
          {pillar.code}
        </span>
      ))}
    </div>
  );
}

function LightStatePill({ state }: { state: string }) {
  return <span className={`light-state-pill ${stateTone(state)}`}>{stateLabel(state)}</span>;
}

export function PillarStackBar({ row }: { row: SnapshotRow }) {
  const contributions = pillarContributions(row);
  const positiveTotal = contributions
    .filter((pillar) => pillar.contribution > 0)
    .reduce((total, pillar) => total + pillar.contribution, 0);
  const negativeTotal = contributions
    .filter((pillar) => pillar.contribution < 0)
    .reduce((total, pillar) => total + Math.abs(pillar.contribution), 0);
  const maxSide = Math.max(1, positiveTotal, negativeTotal);
  const midpoint = 50;
  let positiveOffset = 0;
  let negativeOffset = 0;
  return (
    <div className="pillar-stack" aria-label={`${row.ticker} pillar stack`}>
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
        return <span key={pillar.key} className="pillar-segment" style={style} title={`${pillar.label}: ${fmt(pillar.contribution)}`} />;
      })}
    </div>
  );
}

export function PillarHeatmap({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
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
  const sortedRows = rows.slice().sort((a, b) => b.s_score - a.s_score);
  return (
    <section className="chart-card light-card" aria-label="Composite pillar-stack heatmap">
      <div className="chart-heading">
        <div>
          <h3>The composite, dissected</h3>
          <p>Each row IS the composite. Seven segments to the right of the midline are bullish contributions; segments to the left are bearish. Length encodes magnitude. Read the row to see why the score is what it is.</p>
        </div>
        <div className="chart-heading-meta">
          <span>{rows.length} instruments | sorted by S</span>
          <PillarLegend />
          <span className="composition-axis-copy">bearish left | bullish right</span>
        </div>
      </div>
      <div className="composition-header">
        <span>Ticker</span>
        <span>Composition</span>
        <span>State</span>
        <span>S</span>
        <span>Mom</span>
      </div>
      {classes.map((assetClass) => (
        <div key={assetClass} className="composition-group">
          <div className="composition-class">
            {assetClass} | {grouped[assetClass].length} | {grouped[assetClass].filter((row) => row.s_score > 0).length} positive S
          </div>
          {grouped[assetClass]
            .slice()
            .sort((a, b) => b.s_score - a.s_score)
            .map((row) => (
              <button type="button" key={row.ticker} className="composition-row" onClick={() => onSelectTicker(row.ticker)}>
                <strong>{row.ticker}</strong>
                <PillarStackBar row={row} />
                <LightStatePill state={row.state} />
                <span>{fmt(row.s_score)}</span>
                <span>{fmt(row.momentum_pct, 2)}</span>
              </button>
            ))}
        </div>
      ))}
      {!sortedRows.length ? <p className="empty-chart-copy">No saved snapshot rows are available yet.</p> : null}
    </section>
  );
}

export function WaterfallChart({ row }: { row: SnapshotRow }) {
  const contributions = pillarContributions(row);
  const cumulatives = contributions.reduce<number[]>((acc, pillar) => {
    acc.push((acc.at(-1) ?? 0) + pillar.contribution);
    return acc;
  }, [0]);
  const minY = Math.min(-1, ...cumulatives, row.s_score);
  const maxY = Math.max(1, ...cumulatives, row.s_score);
  const width = 860;
  const height = 260;
  const left = 42;
  const top = 20;
  const plotW = width - 70;
  const plotH = height - 62;
  const y = (value: number) => top + (maxY - value) / (maxY - minY || 1) * plotH;
  const zeroY = y(0);
  const stepW = plotW / (contributions.length + 1);

  return (
    <div className="chart-card light-card" aria-label={`${row.ticker} composite waterfall`}>
      <div className="chart-heading">
        <div>
          <h3>The composite, built pillar by pillar</h3>
          <p>Start at zero, add each pillar contribution, and end at the current S-score.</p>
        </div>
        <strong>S {fmt(row.s_score)}</strong>
      </div>
      <svg className="waterfall-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${row.display_label} waterfall to S score ${fmt(row.s_score)}`}>
        <line x1={left} x2={width - 18} y1={zeroY} y2={zeroY} className="axis-line" />
        <text x={8} y={y(maxY) + 4}>{fmt(maxY)}</text>
        <text x={8} y={zeroY + 4}>0</text>
        <text x={8} y={y(minY) + 4}>{fmt(minY)}</text>
        {contributions.map((pillar, index) => {
          const previous = cumulatives[index];
          const next = cumulatives[index + 1];
          const x = left + index * stepW + 18;
          const barY = Math.min(y(previous), y(next));
          const barH = Math.max(3, Math.abs(y(previous) - y(next)));
          const connectorX = x + stepW * 0.72;
          return (
            <g key={pillar.key}>
              <rect x={x} y={barY} width={stepW * 0.55} height={barH} fill={pillar.hue} opacity={pillar.contribution >= 0 ? 0.9 : 0.68} />
              <line x1={connectorX} x2={connectorX + stepW * 0.28} y1={y(next)} y2={y(next)} className="connector-line" />
              <text x={x} y={barY - 5}>{fmt(pillar.contribution, 2)}</text>
              <text x={x} y={height - 20}>{pillar.code}</text>
            </g>
          );
        })}
        <rect x={left + contributions.length * stepW + 18} y={Math.min(zeroY, y(row.s_score))} width={stepW * 0.6} height={Math.max(3, Math.abs(zeroY - y(row.s_score)))} className="total-bar" />
        <text x={left + contributions.length * stepW + 18} y={Math.min(zeroY, y(row.s_score)) - 6}>S {fmt(row.s_score)}</text>
      </svg>
      <div className="pillar-card-grid">
        {contributions.map((pillar) => (
          <div key={pillar.key} className="pillar-card" style={{ borderColor: pillar.hue }}>
            <span>{pillar.code}</span>
            <strong>{fmt(pillar.contribution)}</strong>
            <p>{pillar.label}: {pillar.reading}; current input {fmt(pillar.raw, 2)}.</p>
          </div>
        ))}
      </div>
    </div>
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

export function RrgChart({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
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
          <h3>Relative Rotation Graph</h3>
          <p>Quadrants are split at 100 RS-ratio and 100 RS-momentum. Trails show recent direction from saved signal values.</p>
        </div>
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
          return (
            <g
              key={row.ticker}
              className="rrg-point"
              onClick={() => onSelectTicker(row.ticker)}
              aria-label={`${row.display_label} ${row.quadrant} rotation point`}
            >
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

export function MomentumBars({ rows, onSelectTicker }: { rows: SnapshotRow[]; onSelectTicker: (ticker: string) => void }) {
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
          <h3>12-1 Momentum Rank</h3>
          <p>Sorted by current saved momentum signal.</p>
        </div>
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
  const totalOut = outflows.reduce((total, row) => total + Math.max(0.05, Math.abs(row.f_score || row.cmf21 || row.s_score)), 0);
  const totalIn = inflows.reduce((total, row) => total + Math.max(0.05, Math.abs(row.f_score || row.cmf21 || row.s_score)), 0);
  const maxMagnitude = Math.max(
    0.1,
    ...outflows.map((row) => Math.abs(row.f_score || row.cmf21 || row.s_score)),
    ...inflows.map((row) => Math.abs(row.f_score || row.cmf21 || row.s_score)),
  );
  return (
    <div className="chart-card light-card" aria-label="Flow river">
      <div className="chart-heading">
        <div>
          <h3>The flow river</h3>
          <p>Data-derived map from current weakest flow/score rows into strongest flow/score rows. Strand width follows relative pressure magnitude.</p>
        </div>
        <strong>{pairCount} lanes</strong>
      </div>
      <svg className="flow-river" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Current flow river from weakening to strengthening instruments">
        <text x="22" y="20">NET OUTFLOWS</text>
        <text x={width - 22} y="20" textAnchor="end">NET INFLOWS</text>
        {outflows.flatMap((source, sourceIndex) => {
          const sourceMagnitude = Math.max(0.05, Math.abs(source.f_score || source.cmf21 || source.s_score));
          return inflows.map((target, targetIndex) => {
            const targetMagnitude = Math.max(0.05, Math.abs(target.f_score || target.cmf21 || target.s_score));
            const share = sourceMagnitude / Math.max(totalOut, 0.1) * targetMagnitude / Math.max(totalIn, 0.1);
            const y1 = top + sourceIndex * rowGap + (targetIndex - 2) * 2.4;
            const y2 = top + targetIndex * rowGap + (sourceIndex - 2) * 2.4;
            const strokeWidth = Math.max(1.5, share * 130);
            return (
              <path
                key={`${source.ticker}-${target.ticker}`}
                d={`M ${leftX} ${y1} C ${leftX + 190} ${y1}, ${rightX - 190} ${y2}, ${rightX} ${y2}`}
                fill="none"
                stroke="#b34a4a"
                strokeOpacity="0.16"
                strokeWidth={strokeWidth}
              />
            );
          });
        })}
        {Array.from({ length: pairCount }).map((_, index) => {
          const source = outflows[index];
          const target = inflows[index];
          const y1 = top + index * rowGap;
          const y2 = top + index * rowGap;
          const strokeWidth = 4 + Math.abs(source.f_score || source.cmf21 || source.s_score) / maxMagnitude * 8;
          return (
            <path
              key={`primary-${source.ticker}-${target.ticker}`}
              d={`M ${leftX} ${y1} C ${leftX + 190} ${y1}, ${rightX - 190} ${y2}, ${rightX} ${y2}`}
              fill="none"
              stroke="#b34a6b"
              strokeOpacity="0.34"
              strokeWidth={strokeWidth}
            />
          );
        })}
        {outflows.map((row, index) => {
          const y = top + index * rowGap;
          const h = 12 + Math.abs(row.f_score || row.cmf21 || row.s_score) / maxMagnitude * 24;
          return (
            <g key={`out-${row.ticker}`}>
              <rect x={leftX - 18} y={y - h / 2} width="12" height={h} fill="#b34a4a" />
              <text x={leftX - 26} y={y - 2} textAnchor="end">{row.ticker} | {row.identity}</text>
              <text x={leftX - 26} y={y + 13} textAnchor="end" className="flow-value">-{fmt(Math.max(0.05, Math.abs(row.f_score || row.cmf21 || row.s_score)), 2)}</text>
            </g>
          );
        })}
        {inflows.map((row, index) => {
          const y = top + index * rowGap;
          const h = 12 + Math.abs(row.f_score || row.cmf21 || row.s_score) / maxMagnitude * 24;
          return (
            <g key={`in-${row.ticker}`}>
              <rect x={rightX + 6} y={y - h / 2} width="12" height={h} fill="#1f7a4a" />
              <text x={rightX + 26} y={y - 2}>{row.ticker} | {row.identity}</text>
              <text x={rightX + 26} y={y + 13} className="flow-value">+{fmt(Math.max(0.05, Math.abs(row.f_score || row.cmf21 || row.s_score)), 2)}</text>
            </g>
          );
        })}
        {!pairCount ? <text x="22" y="70">No opposing flow lanes are available in the latest snapshot.</text> : null}
      </svg>
      {pairCount ? (
        <p className="flow-caption">
          Current saved snapshot shows pressure led by {outflows[0].display_label}; support is led by {inflows[0].display_label}. Use this as a rotation map, not a literal dollar-transfer ledger.
        </p>
      ) : null}
    </div>
  );
}
