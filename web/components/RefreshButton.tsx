// web/components/RefreshButton.tsx
"use client";
import { useState, useCallback } from "react";
import { triggerRefresh, pollRefreshJob } from "../lib/api";

type BtnState = "idle" | "running" | "done" | "error";

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "cancelled"]);
const POLL_INTERVAL_MS = 1500;
const RESET_DELAY_MS = 2500;

export default function RefreshButton({
  laneId = "all",
  label,
  afterSuccess = () => window.location.reload(),
}: {
  laneId?: string;
  label?: string;
  afterSuccess?: () => void;
}) {
  const [state, setState] = useState<BtnState>("idle");

  const handleClick = useCallback(async () => {
    if (state === "running") return;
    setState("running");

    const result = await triggerRefresh(laneId);
    if (!result.ok || !result.data) {
      setState("error");
      setTimeout(() => setState("idle"), RESET_DELAY_MS);
      return;
    }

    const { job_id } = result.data;

    const poll = async (): Promise<void> => {
      const status = await pollRefreshJob(job_id);
      if (!status.ok || !status.data) {
        setState("error");
        setTimeout(() => setState("idle"), RESET_DELAY_MS);
        return;
      }
      const s = status.data.status;
      if (TERMINAL_STATUSES.has(s)) {
        if (s === "succeeded") {
          setState("done");
          setTimeout(afterSuccess, RESET_DELAY_MS);
        } else {
          setState("error");
          setTimeout(() => setState("idle"), RESET_DELAY_MS);
        }
      } else {
        setTimeout(poll, POLL_INTERVAL_MS);
      }
    };

    setTimeout(poll, POLL_INTERVAL_MS);
  }, [laneId, state, afterSuccess]);

  const icon =
    state === "running" ? "⟳" :
    state === "done"    ? "✓" :
    state === "error"   ? "✗" : "↺";

  const title = `Refresh ${label ?? laneId}`;

  return (
    <button
      type="button"
      className={`refresh-btn refresh-btn--${state}`}
      onClick={handleClick}
      disabled={state === "running"}
      title={title}
      aria-label={title}
    >
      <span className="refresh-btn-icon" aria-hidden="true">{icon}</span>
    </button>
  );
}
