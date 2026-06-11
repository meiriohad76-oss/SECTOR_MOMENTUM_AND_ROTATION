// web/components/DisplayShell.tsx
"use client";

import { useEffect, useState } from "react";
import type { DashboardSnapshotPayload } from "../lib/api";
import DashboardScreensClient from "../app/dashboard-screens-client";
import DisplayToolbar from "./DisplayToolbar";

export type DisplayMode = "a" | "b" | "c";
const STORAGE_KEY = "momentum.display";

export default function DisplayShell({
  snapshot,
}: {
  snapshot: DashboardSnapshotPayload | null;
}) {
  const [display, setDisplay] = useState<DisplayMode>("c");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "a" || stored === "b" || stored === "c") {
      setDisplay(stored);
    }
    setHydrated(true);
  }, []);

  function switchDisplay(mode: DisplayMode) {
    setDisplay(mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }

  const generatedAt = snapshot?.generated_at ?? "";

  const presentation =
    display === "a" ? "handoff-a" : display === "b" ? "handoff-b" : "handoff-c";

  // Suppress flash of wrong display before hydration
  if (!hydrated) {
    return (
      <div style={{ minHeight: "100vh", background: "#fbfaf8" }} aria-hidden="true" />
    );
  }

  return (
    <>
      <DisplayToolbar
        activeDisplay={display}
        generatedAt={generatedAt}
        onSwitch={switchDisplay}
      />
      <DashboardScreensClient snapshot={snapshot} presentation={presentation} />
    </>
  );
}
