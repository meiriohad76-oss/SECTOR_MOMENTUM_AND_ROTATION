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
