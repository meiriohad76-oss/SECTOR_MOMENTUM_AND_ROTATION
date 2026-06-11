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
        <span className={(row.s_score ?? 0) >= 0 ? "good" : "bad"}>S {fmtSigned(row.s_score)}</span>
        <span className={(row.f_score ?? 0) >= 0 ? "good" : "bad"}>F {fmtSigned(row.f_score)}</span>
      </div>
      <div className="pick-card-footer mono">
        <span className={(row.momentum_pct ?? 0) >= 0 ? "good" : "bad"}>MOM {momPct}</span>
        <span>{row.quadrant}</span>
      </div>
    </button>
  );
}
