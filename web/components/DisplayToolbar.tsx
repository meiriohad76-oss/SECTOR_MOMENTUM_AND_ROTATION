// web/components/DisplayToolbar.tsx
"use client";
import type { DisplayMode } from "./DisplayShell";
import RefreshButton from "./RefreshButton";

const DISPLAY_TABS: { mode: DisplayMode; label: string; title: string }[] = [
  { mode: "a", label: "A", title: "Terminal" },
  { mode: "b", label: "B", title: "Brief" },
  { mode: "c", label: "C", title: "Pillar Stack" },
];

export default function DisplayToolbar({
  activeDisplay,
  generatedAt,
  onSwitch,
}: {
  activeDisplay: DisplayMode;
  generatedAt: string;
  onSwitch: (mode: DisplayMode) => void;
}) {
  return (
    <header className="display-toolbar" aria-label="Display mode selector">
      <div className="display-toolbar-brand">
        <span className="c-logo" aria-hidden="true">
          <span /><span /><span /><span />
        </span>
        <strong>Momentum</strong>
      </div>
      <nav className="display-toolbar-tabs" aria-label="Choose display style">
        {DISPLAY_TABS.map(({ mode, label, title }) => (
          <button
            key={mode}
            type="button"
            className={`display-toolbar-tab${activeDisplay === mode ? " active" : ""}`}
            onClick={() => onSwitch(mode)}
            aria-pressed={activeDisplay === mode}
            title={title}
          >
            <span className="display-toolbar-tab-label">{label}</span>
            <span className="display-toolbar-tab-title">{title}</span>
          </button>
        ))}
      </nav>
      <div className="display-toolbar-right">
        {generatedAt ? (
          <span className="display-toolbar-timestamp mono">{generatedAt}</span>
        ) : null}
        <RefreshButton laneId="all" label="all data" />
        <a href="/admin" className="display-toolbar-admin">Admin</a>
      </div>
    </header>
  );
}
