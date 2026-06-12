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
  title = "State changes",
}: {
  transitions: SnapshotTransition[];
  onSelect: (ticker: string) => void;
  light?: boolean;
  title?: string;
}) {
  if (!transitions.length) return null;
  const visible = transitions.slice(0, 8);

  return (
    <section className="transitions-banner" aria-label="Recent state transitions">
      <div className="transitions-banner-head">
        <span className="mono">{title}</span>
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
