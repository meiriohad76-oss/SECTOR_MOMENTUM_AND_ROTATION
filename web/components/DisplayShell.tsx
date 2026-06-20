// web/components/DisplayShell.tsx
"use client";

import { useEffect, useState } from "react";
import type { BacktestArtifactsPayload, DebriefPayload, DashboardSnapshotPayload } from "../lib/api";
import DashboardScreensClient from "../app/dashboard-screens-client";
import DisplayToolbar from "./DisplayToolbar";

export type DisplayMode = "a" | "b" | "c";
const STORAGE_KEY = "momentum.display";

export default function DisplayShell({
  snapshot,
  backtestArtifacts = null,
  backtestError,
  debriefData = null,
}: {
  snapshot: DashboardSnapshotPayload | null;
  backtestArtifacts?: BacktestArtifactsPayload | null;
  backtestError?: string | null;
  debriefData?: DebriefPayload | null;
}) {
  const [presentation, setPresentation] = useState<DisplayMode>("c");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // URL param takes priority (enables QA/deeplink) over persisted preference
    const params = new URLSearchParams(window.location.search);
    const urlParam = params.get("presentation");
    if (urlParam === "a" || urlParam === "b" || urlParam === "c") {
      setPresentation(urlParam);
    } else {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "a" || stored === "b" || stored === "c") {
        setPresentation(stored);
      }
    }
    setHydrated(true);
  }, []);

  function switchPresentation(mode: DisplayMode) {
    setPresentation(mode);
    localStorage.setItem(STORAGE_KEY, mode);
  }

  const generatedAt = snapshot?.generated_at ?? "";

  const presentationMode =
    presentation === "a" ? "handoff-a"
    : presentation === "b" ? "handoff-b"
    : presentation === "c" ? "handoff-c"
    : "handoff-c";

  // Suppress flash of wrong display before hydration
  if (!hydrated) {
    return (
      <div style={{ minHeight: "100vh", background: "#fbfaf8" }} aria-hidden="true" />
    );
  }

  return (
    <>
      <DisplayToolbar
        activeDisplay={presentation}
        generatedAt={generatedAt}
        onSwitch={switchPresentation}
      />
      <DashboardScreensClient
        snapshot={snapshot}
        presentation={presentationMode}
        backtestArtifacts={backtestArtifacts}
        debriefData={debriefData}
      />
    </>
  );
}
