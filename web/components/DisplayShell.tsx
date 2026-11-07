// web/components/DisplayShell.tsx
"use client";

import { useEffect, useState } from "react";
import type { BacktestArtifactsPayload, DebriefPayload, DashboardSnapshotPayload } from "../lib/api";
import DashboardScreensClient from "../app/dashboard-screens-client";
import DisplayToolbar from "./DisplayToolbar";
import Bluf from "./Bluf";

export type DisplayMode = "a" | "b" | "c";
export type ScreenId = "overview" | "deepdive" | "rotation";

const DISPLAY_STORAGE_KEY = "momentum.display";
const SCREEN_STORAGE_KEY  = "mv2_screen";

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
  const [activeScreen,  setActiveScreen]  = useState<ScreenId>("overview");
  const [focusTicker,   setFocusTicker]   = useState<string>("");
  const [hydrated,      setHydrated]      = useState(false);
  const [blufOn,        setBlufOn]        = useState(process.env.NEXT_PUBLIC_BLUF_LAYOUT !== "0");

  // Hydrate from URL params then localStorage (runs once, client-only)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("bluf") === "1") setBlufOn(true);

    // Display mode: ?display= takes priority, legacy ?presentation= as fallback
    const urlDisplay = params.get("display") ?? params.get("presentation");
    if (urlDisplay === "a" || urlDisplay === "b" || urlDisplay === "c") {
      setPresentation(urlDisplay);
    } else {
      const stored = localStorage.getItem(DISPLAY_STORAGE_KEY);
      if (stored === "a" || stored === "b" || stored === "c") {
        setPresentation(stored);
      }
    }

    // Screen: ?screen= then localStorage
    const urlScreen = params.get("screen");
    if (urlScreen === "overview" || urlScreen === "deepdive" || urlScreen === "rotation") {
      setActiveScreen(urlScreen);
    } else {
      const storedScreen = localStorage.getItem(SCREEN_STORAGE_KEY);
      if (storedScreen === "overview" || storedScreen === "deepdive" || storedScreen === "rotation") {
        setActiveScreen(storedScreen as ScreenId);
      }
    }

    // Focus ticker: ?t= then snapshot
    const urlTicker    = params.get("t");
    const snapTicker   = snapshot?.focus?.ticker || snapshot?.rows?.[0]?.ticker || "";
    setFocusTicker(urlTicker ? urlTicker.toUpperCase() : snapTicker);

    setHydrated(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep URL in sync whenever display/screen/ticker changes (after initial hydration)
  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    url.searchParams.set("display", presentation);
    url.searchParams.set("screen",  activeScreen);
    if (focusTicker) url.searchParams.set("t", focusTicker);
    else             url.searchParams.delete("t");
    url.searchParams.delete("presentation"); // retire legacy param
    window.history.replaceState(null, "", url.toString());
  }, [presentation, activeScreen, focusTicker, hydrated]);

  function switchPresentation(mode: DisplayMode) {
    setPresentation(mode);
    localStorage.setItem(DISPLAY_STORAGE_KEY, mode);
  }

  function switchScreen(screen: ScreenId) {
    setActiveScreen(screen);
    localStorage.setItem(SCREEN_STORAGE_KEY, screen);
  }

  const generatedAt = snapshot?.generated_at ?? "";

  const presentationMode =
    presentation === "a" ? "handoff-a"
    : presentation === "b" ? "handoff-b"
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
        activeScreen={activeScreen}
        generatedAt={generatedAt}
        onSwitch={switchPresentation}
        onSwitchScreen={switchScreen}
      />
      {blufOn && snapshot?.bluf ? <Bluf bluf={snapshot.bluf} /> : null}
      <DashboardScreensClient
        snapshot={snapshot}
        presentation={presentationMode}
        backtestArtifacts={backtestArtifacts}
        debriefData={debriefData}
        activeScreen={activeScreen}
        setActiveScreen={switchScreen}
        focusTicker={focusTicker}
        setFocusTicker={setFocusTicker}
      />
    </>
  );
}
