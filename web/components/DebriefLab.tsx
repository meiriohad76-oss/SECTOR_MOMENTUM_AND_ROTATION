// web/components/DebriefLab.tsx
import type { DebriefPayload, DebriefDecision } from "../lib/api";
import { stateColor, stateShortLabel } from "../lib/state-colors";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toISOString().slice(0, 10);
}

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2);
}

function ActionBadge({ action }: { action: string | null }) {
  if (!action) return <span className="dl-action dl-action-neutral">—</span>;
  const normalized = action.toUpperCase();
  const cls =
    normalized === "BUY" || normalized === "ADD"
      ? "dl-action-buy"
      : normalized === "EXIT" || normalized === "SELL"
      ? "dl-action-exit"
      : normalized === "HOLD"
      ? "dl-action-hold"
      : "dl-action-neutral";
  return <span className={`dl-action ${cls}`}>{normalized}</span>;
}

export default function DebriefLab({
  debrief,
}: {
  debrief: DebriefPayload | null | undefined;
}) {
  if (!debrief || debrief.runs.length === 0) {
    return (
      <details className="debrief-lab-panel">
        <summary className="debrief-lab-summary">Debrief Lab</summary>
        <p className="dl-empty">No run journal data available.</p>
      </details>
    );
  }

  const decisions = debrief.decisions;

  return (
    <details className="debrief-lab-panel">
      <summary className="debrief-lab-summary">
        Debrief Lab — {debrief.runs.length} runs, {decisions.length} decisions
      </summary>

      <section className="dl-section">
        <h4 className="dl-heading">Recent runs</h4>
        <table className="dl-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Provider</th>
              <th>Universe</th>
            </tr>
          </thead>
          <tbody>
            {debrief.runs.map((run) => (
              <tr key={run.run_id}>
                <td>{fmtDate(run.started_at_utc)}</td>
                <td>{run.provider ?? "—"}</td>
                <td>{run.universe_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {decisions.length > 0 && (
        <section className="dl-section">
          <h4 className="dl-heading">Decisions</h4>
          <table className="dl-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Ticker</th>
                <th>Action</th>
                <th>State</th>
                <th>S</th>
                <th>F</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((d: DebriefDecision, i: number) => (
                <tr key={`${d.run_id}-${d.ticker}-${i}`}>
                  <td>{fmtDate(d.started_at_utc)}</td>
                  <td className="dl-ticker">{d.ticker}</td>
                  <td><ActionBadge action={d.action} /></td>
                  <td>
                    {d.state ? (
                      <span
                        className="state-pill mono"
                        style={{
                          background: stateColor(d.state),
                          color: "#fff",
                          padding: "1px 6px",
                          borderRadius: "8px",
                          fontSize: "0.67rem",
                          fontWeight: 600,
                        }}
                      >
                        {stateShortLabel(d.state)}
                      </span>
                    ) : "—"}
                  </td>
                  <td className={d.s_score !== null ? (d.s_score >= 0 ? "dl-pos" : "dl-neg") : ""}>
                    {fmtScore(d.s_score)}
                  </td>
                  <td className={d.f_score !== null ? (d.f_score >= 0 ? "dl-pos" : "dl-neg") : ""}>
                    {fmtScore(d.f_score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </details>
  );
}
