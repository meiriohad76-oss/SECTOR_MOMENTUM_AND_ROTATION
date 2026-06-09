import {
  fetchDashboardSnapshot,
  fetchDataHealth,
  fetchHealth,
  type DashboardHealthPayload,
  type DashboardSnapshotPayload,
  type HealthLane,
  type SnapshotDecision,
  type SnapshotRow
} from "../lib/api";

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "healthy" || normalized === "info") return "good";
  if (normalized === "stale") return "bad";
  return "warn";
}

function laneRows(payload: DashboardHealthPayload | null): HealthLane[] {
  return payload?.lanes ?? [];
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${statusClass(status)}`}>{status || "unknown"}</span>;
}

function HeroBand({ payload }: { payload: DashboardHealthPayload | null }) {
  const health = payload?.health;
  return (
    <section className="hero-band" aria-label="Dashboard health overview">
      <div>
        <p className="eyebrow">API migration shell</p>
        <h1>Sector Momentum Dashboard</h1>
        <p className="subtle">
          {health?.detail || "Waiting for the FastAPI backend health payload."}
        </p>
      </div>
      <div className="summary-strip">
        <div>
          <span>Health</span>
          <strong>{health?.label || "Unavailable"}</strong>
        </div>
        <div>
          <span>Lanes</span>
          <strong>{health?.lane_count ?? 0}</strong>
        </div>
        <div>
          <span>Generated</span>
          <strong>{payload?.generated_at || "-"}</strong>
        </div>
        <div>
          <span>Frontend</span>
          <strong>{payload?.app?.active_frontend || "next"}</strong>
        </div>
      </div>
    </section>
  );
}

function HealthTable({ title, lanes }: { title: string; lanes: HealthLane[] }) {
  return (
    <section className="table-section" aria-label={title}>
      <div className="section-heading">
        <h2>{title}</h2>
        <span>{lanes.length} lanes</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Lane</th>
              <th>Status</th>
              <th>Latest</th>
              <th>Freshness</th>
              <th>Coverage</th>
              <th>Operational Detail</th>
            </tr>
          </thead>
          <tbody>
            {lanes.map((lane) => (
              <tr key={lane.lane_id}>
                <td>
                  <strong>{lane.source || lane.lane_id}</strong>
                  <small>{lane.role}</small>
                </td>
                <td>
                  <StatusPill status={lane.status} />
                </td>
                <td>{lane.latest || "-"}</td>
                <td>{lane.freshness || "-"}</td>
                <td>{lane.coverage || "-"}</td>
                <td>{lane.detail || lane.sla || "-"}</td>
              </tr>
            ))}
            {!lanes.length ? (
              <tr>
                <td colSpan={6}>No API health lanes returned yet.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProviderRail({ payload }: { payload: DashboardHealthPayload | null }) {
  const providerLane = laneRows(payload).find((lane) => lane.lane_id === "provider_flow_readiness");
  const providers = providerLane?.providers ?? [];
  return (
    <aside className="provider-rail" aria-label="Provider health">
      <div className="section-heading compact">
        <h2>Provider Flow</h2>
        <span>{payload?.provider_flow?.enabled_provider_count ?? 0} enabled</span>
      </div>
      <div className="provider-list">
        {providers.map((provider) => (
          <div className="provider-row" key={provider.id}>
            <div>
              <strong>{provider.label}</strong>
              <span>{provider.provider} | {provider.signal}</span>
            </div>
            <StatusPill status={provider.status} />
            <p>{provider.mode}. {provider.detail}</p>
          </div>
        ))}
        {!providers.length ? <p className="subtle">Provider readiness is unavailable until the API responds.</p> : null}
      </div>
    </aside>
  );
}

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function SnapshotCard({ row }: { row: SnapshotRow }) {
  return (
    <article className="snapshot-card">
      <div>
        <strong>{row.display_label}</strong>
        <span>{row.asset_class} | {row.quadrant}</span>
      </div>
      <StatusPill status={row.state} />
      <dl>
        <div><dt>S</dt><dd>{fmt(row.s_score)}</dd></div>
        <div><dt>F</dt><dd>{fmt(row.f_score)}</dd></div>
        <div><dt>RS-R</dt><dd>{fmt(row.rs_ratio, 1)}</dd></div>
        <div><dt>RS-M</dt><dd>{fmt(row.rs_momentum, 1)}</dd></div>
      </dl>
    </article>
  );
}

function ActionRow({ decision }: { decision: SnapshotDecision }) {
  return (
    <div className="action-row">
      <StatusPill status={decision.action} />
      <strong>{decision.ticker} | {decision.identity}</strong>
      <span>{decision.rationale || "No rationale recorded."}</span>
    </div>
  );
}

function OverviewScreen({ snapshot }: { snapshot: DashboardSnapshotPayload | null }) {
  const leaders = snapshot?.screens.overview?.leaders ?? [];
  const risks = snapshot?.screens.overview?.risks ?? [];
  const actions = snapshot?.screens.overview?.actions ?? [];
  return (
    <section className="screen-section" aria-label="Display A overview">
      <div className="section-heading">
        <h2>A | Overview</h2>
        <span>{snapshot?.summary.universe_count ?? 0} instruments</span>
      </div>
      <div className="snapshot-columns">
        <div>
          <h3>Leaders</h3>
          {leaders.slice(0, 5).map((row) => <SnapshotCard key={row.ticker} row={row} />)}
        </div>
        <div>
          <h3>Risk Queue</h3>
          {risks.slice(0, 5).map((row) => <SnapshotCard key={row.ticker} row={row} />)}
        </div>
        <div>
          <h3>Actions</h3>
          {actions.slice(0, 6).map((decision) => (
            <ActionRow key={`${decision.action}-${decision.ticker}`} decision={decision} />
          ))}
          {!actions.length ? <p className="subtle">No BLUF decisions in the latest journal snapshot.</p> : null}
        </div>
      </div>
    </section>
  );
}

function DeepDiveScreen({ snapshot }: { snapshot: DashboardSnapshotPayload | null }) {
  const focus = snapshot?.focus;
  const pillars = Object.entries(focus?.pillar_scores ?? {}).slice(0, 10);
  return (
    <section className="screen-section" aria-label="Display B deep dive">
      <div className="section-heading">
        <h2>B | Deep Dive</h2>
        <span>{focus?.display_label || "No focus ticker"}</span>
      </div>
      {focus ? (
        <div className="deep-grid">
          <SnapshotCard row={focus} />
          <div className="pillar-list">
            {pillars.map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <strong>{typeof value === "number" ? fmt(value, 3) : String(value)}</strong>
              </div>
            ))}
          </div>
          <p>
            {focus.display_label} is currently labeled {focus.state.replaceAll("_", " ")} with
            S {fmt(focus.s_score)} and F {fmt(focus.f_score)}. The React shell is reading this
            directly from the latest persisted run journal.
          </p>
        </div>
      ) : (
        <p className="subtle">Run a dashboard refresh to persist a focus row.</p>
      )}
    </section>
  );
}

function RotationScreen({ snapshot }: { snapshot: DashboardSnapshotPayload | null }) {
  const sectors = snapshot?.screens.rotation?.sectors ?? [];
  const counts = snapshot?.summary.quadrant_counts ?? {};
  return (
    <section className="screen-section" aria-label="Display C rotation">
      <div className="section-heading">
        <h2>C | Rotation</h2>
        <span>{sectors.length} sector rows</span>
      </div>
      <div className="rotation-grid">
        {["Leading", "Weakening", "Lagging", "Improving", "Unknown"].map((quadrant) => (
          <div className="quadrant-box" key={quadrant}>
            <strong>{quadrant}</strong>
            <span>{counts[quadrant] ?? 0}</span>
            <ul>
              {sectors
                .filter((row) => row.quadrant === quadrant)
                .slice(0, 5)
                .map((row) => (
                  <li key={row.ticker}>{row.ticker} | {row.identity}</li>
                ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function SnapshotScreens({ snapshot }: { snapshot: DashboardSnapshotPayload | null }) {
  return (
    <div className="screen-stack">
      <OverviewScreen snapshot={snapshot} />
      <DeepDiveScreen snapshot={snapshot} />
      <RotationScreen snapshot={snapshot} />
    </div>
  );
}

function ApiWarning({
  healthError,
  dataHealthError,
  snapshotError
}: {
  healthError: string;
  dataHealthError: string;
  snapshotError: string;
}) {
  if (!healthError && !dataHealthError && !snapshotError) return null;
  return (
    <section className="api-warning" role="status">
      <strong>API connection pending</strong>
      <span>
        Health: {healthError || "ok"} | Data health: {dataHealthError || "ok"} | Snapshot: {snapshotError || "ok"}
      </span>
    </section>
  );
}

export default async function DashboardShell() {
  const [healthResult, dataHealthResult, snapshotResult] = await Promise.all([
    fetchHealth(),
    fetchDataHealth(),
    fetchDashboardSnapshot()
  ]);
  const primary = dataHealthResult.data || healthResult.data;
  const snapshot = snapshotResult.data;
  const persistedLanes = laneRows(primary).filter((lane) => !lane.lane_id.startsWith("provider_"));
  const providerLanes = laneRows(primary).filter((lane) => lane.lane_id.startsWith("provider_"));

  return (
    <main>
      <HeroBand payload={primary} />
      <ApiWarning
        healthError={healthResult.error}
        dataHealthError={dataHealthResult.error}
        snapshotError={snapshotResult.error}
      />
      <div className="dashboard-grid">
        <div className="main-stack">
          <SnapshotScreens snapshot={snapshot} />
          <HealthTable title="Persisted Data Health" lanes={persistedLanes} />
          <HealthTable title="Provider Data Health" lanes={providerLanes} />
        </div>
        <ProviderRail payload={primary} />
      </div>
    </main>
  );
}
