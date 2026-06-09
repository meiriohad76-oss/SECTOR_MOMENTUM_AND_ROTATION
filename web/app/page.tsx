import {
  fetchBacktestArtifacts,
  fetchDashboardSnapshot,
  fetchDataHealth,
  fetchHealth,
  type BacktestArtifactsPayload,
  type DashboardHealthPayload,
  type HealthLane,
} from "../lib/api";
import DashboardScreensClient from "./dashboard-screens-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

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

function ApiWarning({
  healthError,
  dataHealthError,
  snapshotError,
  backtestError
}: {
  healthError: string;
  dataHealthError: string;
  snapshotError: string;
  backtestError: string;
}) {
  if (!healthError && !dataHealthError && !snapshotError && !backtestError) return null;
  return (
    <section className="api-warning" role="status">
      <strong>API connection pending</strong>
      <span>
        Health: {healthError || "ok"} | Data health: {dataHealthError || "ok"} | Snapshot: {snapshotError || "ok"} | Backtest: {backtestError || "ok"}
      </span>
    </section>
  );
}

type SearchParamsValue = string | string[] | undefined;

function firstParam(value: SearchParamsValue): string {
  return Array.isArray(value) ? value[0] || "" : value || "";
}

export default async function DashboardShell({
  searchParams,
}: {
  searchParams?: Promise<Record<string, SearchParamsValue>>;
}) {
  const params = searchParams ? await searchParams : {};
  const presentation = firstParam(params.presentation);
  const [healthResult, dataHealthResult, snapshotResult, backtestResult] = await Promise.all([
    fetchHealth(),
    fetchDataHealth(),
    fetchDashboardSnapshot(),
    fetchBacktestArtifacts()
  ]);
  const primary = dataHealthResult.data || healthResult.data;
  const snapshot = snapshotResult.data;
  const backtestArtifacts: BacktestArtifactsPayload | null = backtestResult.data;
  const persistedLanes = laneRows(primary).filter((lane) => !lane.lane_id.startsWith("provider_"));
  const providerLanes = laneRows(primary).filter((lane) => lane.lane_id.startsWith("provider_"));

  if (presentation === "c") {
    return (
      <main className="handoff-main">
        <DashboardScreensClient snapshot={snapshot} presentation="handoff-c" />
      </main>
    );
  }

  return (
    <main>
      <HeroBand payload={primary} />
      <ApiWarning
        healthError={healthResult.error}
        dataHealthError={dataHealthResult.error}
        snapshotError={snapshotResult.error}
        backtestError={backtestResult.error}
      />
      <div className="dashboard-grid">
        <div className="main-stack">
          <DashboardScreensClient snapshot={snapshot} backtestArtifacts={backtestArtifacts} />
          <HealthTable title="Persisted Data Health" lanes={persistedLanes} />
          <HealthTable title="Provider Data Health" lanes={providerLanes} />
        </div>
        <ProviderRail payload={primary} />
      </div>
    </main>
  );
}
