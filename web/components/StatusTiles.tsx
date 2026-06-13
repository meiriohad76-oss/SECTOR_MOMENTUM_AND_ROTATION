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
