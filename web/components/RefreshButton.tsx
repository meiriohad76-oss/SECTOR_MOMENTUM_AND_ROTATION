// web/components/RefreshButton.tsx
"use client";
import { useState, useCallback } from "react";

type BtnState = "idle" | "running" | "done" | "error";

const TERMINAL_STATUSES = new Set(["succeeded", "failed", "cancelled"]);
const POLL_INTERVAL_MS = 1500;
const RESET_DELAY_MS = 2500;

/** POST /api/v1/refresh via the same-origin Next.js proxy (Route Handler). */
async function callRefresh(laneId: string): Promise<{ job_id: string } | null> {
  try {
    const res = await fetch("/api/v1/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ lane_id: laneId, run_now: true, background: true }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.job_id ? data : null;
  } catch {
    return null;
  }
}

/** GET /api/v1/refresh/{job_id} via the same-origin Next.js proxy (Route Handler). */
async function pollJob(jobId: string): Promise<{ status: string } | null> {
  try {
    const res = await fetch(`/api/v1/refresh/${jobId}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

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

    const job = await callRefresh(laneId);
    if (!job) {
      setState("error");
      setTimeout(() => setState("idle"), RESET_DELAY_MS);
      return;
    }

    const poll = async (): Promise<void> => {
      const result = await pollJob(job.job_id);
      if (!result) {
        setState("error");
        setTimeout(() => setState("idle"), RESET_DELAY_MS);
        return;
      }
      const s = result.status;
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
