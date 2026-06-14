"use server";

import { revalidatePath } from "next/cache";

const API_BASE = process.env.API_BASE_URL || "http://127.0.0.1:8000";
const POLL_INTERVAL_MS = 4000;
const MAX_WAIT_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Server Action: trigger a dashboard refresh and wait for it to complete.
 *
 * Runs entirely on the Pi's Node.js server. The browser never calls FastAPI
 * directly — it calls this action via Next.js's built-in Server Action
 * transport (a POST to a Next.js internal endpoint). When the job finishes,
 * Next.js automatically re-renders all server components with fresh data.
 */
export async function runRefreshAction(laneId: string = "all"): Promise<{
  ok: boolean;
  message: string;
}> {
  console.log(`[runRefreshAction] START laneId=${laneId} API_BASE=${API_BASE}`);
  // 1. Start the background job
  let jobId: string;
  try {
    console.log(`[runRefreshAction] POST ${API_BASE}/api/v1/refresh`);
    const res = await fetch(`${API_BASE}/api/v1/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ lane_id: laneId, run_now: true, background: true }),
    });
    console.log(`[runRefreshAction] POST status=${res.status}`);
    if (!res.ok) {
      return { ok: false, message: `Failed to start refresh (HTTP ${res.status})` };
    }
    const data = await res.json();
    jobId = data.job_id;
    console.log(`[runRefreshAction] job_id=${jobId}`);
    if (!jobId) return { ok: false, message: "No job_id in response" };
  } catch (err) {
    console.error(`[runRefreshAction] fetch error:`, err);
    return { ok: false, message: `Could not reach API: ${err}` };
  }

  // 2. Poll server-side until the job reaches a terminal state
  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    try {
      const statusRes = await fetch(`${API_BASE}/api/v1/refresh/${jobId}`, {
        headers: { Accept: "application/json" },
      });
      if (!statusRes.ok) continue;
      const status = await statusRes.json();
      const s: string = status.status ?? "";
      if (s === "succeeded") {
        // Invalidate all server-component data so pages re-fetch on next render
        revalidatePath("/", "layout");
        return { ok: true, message: "Refresh complete" };
      }
      if (s === "failed" || s === "cancelled") {
        return { ok: false, message: `Refresh ${s}: ${status.error || ""}` };
      }
      // still running — loop
    } catch {
      // transient poll error — keep trying
    }
  }

  return { ok: false, message: "Refresh timed out after 5 minutes" };
}
