// web/components/DisplayToolbar.tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import type { DisplayMode, ScreenId } from "./DisplayShell";
import RefreshButton from "./RefreshButton";

const DISPLAY_TABS: { mode: DisplayMode; label: string; title: string }[] = [
  { mode: "a", label: "A", title: "Terminal" },
  { mode: "b", label: "B", title: "Brief" },
  { mode: "c", label: "C", title: "Pillar Stack" },
];

/** Screen tab labels adapt per display mode */
const SCREEN_TABS: Record<DisplayMode, Array<{ id: ScreenId; label: string }>> = {
  a: [
    { id: "overview",  label: "Overview"  },
    { id: "deepdive",  label: "Deep Dive" },
    { id: "rotation",  label: "Rotation"  },
  ],
  b: [
    { id: "overview",  label: "Brief"     },
    { id: "deepdive",  label: "Deep Dive" },
    { id: "rotation",  label: "Rotation"  },
  ],
  c: [
    { id: "overview",  label: "Heatmap"   },
    { id: "deepdive",  label: "Deep Dive" },
    { id: "rotation",  label: "Rotation"  },
  ],
};

export default function DisplayToolbar({
  activeDisplay,
  activeScreen,
  generatedAt,
  onSwitch,
  onSwitchScreen,
}: {
  activeDisplay: DisplayMode;
  activeScreen: ScreenId;
  generatedAt: string;
  onSwitch: (mode: DisplayMode) => void;
  onSwitchScreen: (screen: ScreenId) => void;
}) {
  const screenTabs = SCREEN_TABS[activeDisplay];
  const [copied, setCopied] = useState(false);
  const handleCopyLink = useCallback(() => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }).catch(() => {/* clipboard unavailable — no-op */});
  }, []);
  return (
    <header className="display-toolbar" aria-label="Display mode selector">
      <div className="display-toolbar-brand">
        <span className="c-logo" aria-hidden="true">
          <span /><span /><span /><span />
        </span>
        <strong>Momentum</strong>
      </div>

      {/* Display-style switcher: A / B / C */}
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

      {/* Vertical rule separating display tabs from screen tabs */}
      <div className="display-toolbar-divider" aria-hidden="true" />

      {/* Screen switcher — labels depend on active display */}
      <nav className="display-toolbar-screens" aria-label="Choose screen">
        {screenTabs.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`display-toolbar-screen-tab${activeScreen === id ? " active" : ""}`}
            onClick={() => onSwitchScreen(id)}
            aria-pressed={activeScreen === id}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="display-toolbar-right">
        {generatedAt ? (
          <span className="display-toolbar-timestamp mono">{generatedAt}</span>
        ) : null}
        <button
          type="button"
          className="display-toolbar-copy-link"
          onClick={handleCopyLink}
          title="Copy deep-link URL (?display=…&screen=…&t=…)"
          aria-label="Copy link to this view"
        >
          {copied ? "✓ Copied" : "⧉ Link"}
        </button>
        <RefreshButton laneId="all" label="all data" />
        <ThemeToggle />
        <a href="/admin" className="display-toolbar-admin">Admin</a>
      </div>
    </header>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    try {
      setDark(window.localStorage.getItem("sector-theme") === "dark");
    } catch {
      /* storage unavailable: keep the default theme */
    }
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    try {
      window.localStorage.setItem("sector-theme", next ? "dark" : "light");
    } catch {
      /* ignore: the toggle still works for this page view */
    }
  };
  const label = dark ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button type="button" className="c-icon-btn" onClick={toggle} aria-pressed={dark} title={label} aria-label={label}>
      {dark ? "☀" : "☾"}
    </button>
  );
}
