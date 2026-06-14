// web/components/RefreshButton.tsx
"use client";
import { useTransition, useState } from "react";
import { runRefreshAction } from "../app/actions";

export default function RefreshButton({
  laneId = "all",
  label,
}: {
  laneId?: string;
  label?: string;
}) {
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
        // Page data is already fresh (revalidatePath was called server-side).
        // Give the user a moment to see the ✓ before the page auto-refreshes.
        setTimeout(() => window.location.reload(), 1500);
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
