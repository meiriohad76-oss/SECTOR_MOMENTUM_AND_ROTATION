// web/components/RefreshButton.tsx
"use client";
import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { runRefreshAction } from "../app/actions";

export default function RefreshButton({
  laneId = "all",
  label,
}: {
  laneId?: string;
  label?: string;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [done, setDone] = useState(false);
  const [errored, setErrored] = useState(false);

  const handleClick = () => {
    if (isPending) return;
    setDone(false);
    setErrored(false);
    startTransition(async () => {
      const result = await runRefreshAction(laneId);
      if (result.ok) {
        setDone(true);
        // Use router.refresh() instead of window.location.reload().
        // router.refresh() is a Next.js soft refresh: it re-fetches server
        // components without a full browser reload, so the JS context is
        // preserved. window.location.reload() was crashing with
        // ERR_NETWORK_IO_SUSPENDED / "Application error" because the browser
        // attempted a cold full-page load immediately after a heavy sector-api
        // refresh job — before sector-api had settled — causing SSR fetches to
        // hang and the shared JS chunk to fail mid-load.
        setTimeout(() => router.refresh(), 1500);
        // Reset button back to idle once data has settled.
        setTimeout(() => setDone(false), 5000);
      } else {
        setErrored(true);
        setTimeout(() => setErrored(false), 4000);
      }
    });
  };

  const icon = isPending ? "⟳" : done ? "✓" : errored ? "✗" : "↺";
  const stateClass = isPending ? "running" : done ? "done" : errored ? "error" : "idle";
  const title = label ? `Refresh ${label}` : "Refresh data";

  return (
    <button
      type="button"
      className={`refresh-btn refresh-btn--${stateClass}`}
      onClick={handleClick}
      disabled={isPending}
      title={title}
      aria-label={title}
    >
      <span className="refresh-btn-icon" aria-hidden="true">{icon}</span>
      {isPending && <span className="refresh-btn-label">Refreshing…</span>}
    </button>
  );
}
