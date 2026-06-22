export type HealthStatus = "healthy" | "info" | "warning" | "stale" | string;

export type HealthLane = {
  lane_id: string;
  source: string;
  role: string;
  status: HealthStatus;
  severity_symbol: string;
  latest: string;
  freshness: string;
  coverage: string;
  detail: string;
  sla: string;
  refresh_label: string;
  refresh_key: string;
  providers?: ProviderHealthRow[];
};

export type ProviderHealthRow = {
  id: string;
  label: string;
  provider: string;
  status: HealthStatus;
  mode: string;
  signal: string;
  detail: string;
};

export type DashboardHealthPayload = {
  api_version: string;
  generated_at: string;
  app: {
    name: string;
    version: string;
    git_sha: string;
    active_frontend: string;
    migration_stage: string;
  };
  health: {
    status: HealthStatus;
    label: string;
    detail: string;
    lane_count: number;
    critical_statuses: string[];
  };
  lanes: HealthLane[];
  provider_flow?: {
    provider_count: number;
    enabled_provider_count: number;
    stubbed: boolean;
  };
};

export type SnapshotRow = {
  ticker: string;
  identity: string;
  display_label: string;
  asset_class: string;
  state: string;
  s_score: number;
  f_score: number;
  quadrant: string;
  momentum_pct: number | null;
  rs_ratio: number | null;
  rs_momentum: number | null;
  cmf21: number | null;
  adv_20d: number | null;
  net_flow_21d: number | null;
  pillar_scores: Record<string, number | string | boolean | null>;
  payload: Record<string, number | string | boolean | null>;
};

export type SnapshotDecision = {
  decision_type: string;
  ticker: string;
  identity: string;
  action: string;
  rationale: string;
  payload: Record<string, number | string | boolean | null>;
};

export type SnapshotTransition = {
  ticker: string;
  identity: string;
  from: string;
  to: string;
  date: string;
};

export type SnapshotPosition = {
  ticker: string;
  identity: string;
  shares: number | null;
  cost_basis: number | null;
  market_value: number | null;
  cost: number | null;
  unrealized_pct: number | null;
  account: string;
  notes: string;
  source_name: string;
  updated_at: string;
};

export type DashboardSnapshotPayload = {
  api_version: string;
  generated_at: string;
  status: "ready" | "empty" | string;
  message: string;
  run: {
    run_id: string;
    started_at_utc: string;
    provider: string;
    universe_count: number;
    metadata: Record<string, unknown>;
  } | null;
  summary: {
    universe_count: number;
    state_counts: Record<string, number>;
    quadrant_counts: Record<string, number>;
    decision_counts: Record<string, number>;
  };
  rows: SnapshotRow[];
  decisions: SnapshotDecision[];
  focus: SnapshotRow | null;
  screens: {
    overview?: {
      leaders?: SnapshotRow[];
      risks?: SnapshotRow[];
      actions?: SnapshotDecision[];
      transitions?: SnapshotTransition[];
      positions?: SnapshotPosition[];
    };
    deepdive?: {
      focus?: SnapshotRow | null;
      peer_rows?: SnapshotRow[];
    };
    rotation?: {
      sectors?: SnapshotRow[];
      leaders?: SnapshotRow[];
      laggards?: SnapshotRow[];
    };
  };
};

export type PortfolioAnalysisRow = {
  ticker: string;
  analysis_weight: number | null;
  input_weight: number | null;
  market_value: number | null;
  state: string;
  asset_class: string;
  s_score: number | null;
  f_score: number | null;
  rank_in_class: number | null;
  selected: boolean | null;
  veto: boolean | null;
  missing: boolean;
  missing_reason: string;
};

export type PortfolioAnalysisPayload = {
  api_version: string;
  status: "ready" | "invalid" | string;
  message: string;
  input: {
    holding_count: number;
    errors: { message: string; row_number: number | null; column: string | null }[];
  };
  summary: {
    row_count: number;
    missing_tickers: string[];
    state_exposure: Record<string, number>;
    class_exposure: Record<string, number>;
    action_tickers: Record<string, string[]>;
  };
  rows: PortfolioAnalysisRow[];
};

export type BacktestArtifactRow = {
  id: string;
  label: string;
  path: string;
  exists: boolean;
  status: string;
  bytes: number;
  modified_at: string;
  sha256: string;
  expected_sha256: string;
};

export type BacktestArtifactsPayload = {
  api_version: string;
  generated_at: string;
  status: "ready" | "missing" | "unverified" | string;
  message: string;
  artifacts: BacktestArtifactRow[];
  report: {
    text: string;
    methodology_text: string;
  };
  equity: {
    row_count: number;
    columns: string[];
    rows: Record<string, number | string | boolean | null>[];
  };
  metadata: Record<string, unknown>;
};

export type TickerChartPoint = {
  date: string;
  close: number | null;
  ma30w: number | null;
};

export type TickerFlowPoint = {
  date: string;
  cmf21: number | null;
  obv: number | null;
};

export type TickerRelativeStrengthPoint = {
  date: string;
  rs_ratio: number | null;
  momentum_12w: number | null;
  momentum_52w: number | null;
};

export type TickerChartPayload = {
  api_version: string;
  generated_at: string;
  status: "ready" | "empty" | string;
  message: string;
  ticker: string;
  identity: string;
  period: string;
  source: {
    mode: string;
    provider: string;
    updated_at: string;
    row_count: number;
    weekly_row_count: number;
    benchmark: string;
    benchmark_available: boolean;
  };
  latest: {
    date: string;
    close: number | null;
    ma30w: number | null;
    above_30wma: boolean | null;
    ma30w_slope: number | null;
    cmf21: number | null;
    obv: number | null;
    obv_slope: number | null;
    rs_ratio: number | null;
    rs_slope: number | null;
    momentum_12w: number | null;
    momentum_52w: number | null;
  };
  series: TickerChartPoint[];
  flow_series: TickerFlowPoint[];
  relative_strength_series: TickerRelativeStrengthPoint[];
};

export type PortfolioAnalysisRequest = {
  ticker?: string;
  csv?: string;
  file_name?: string;
  content_base64?: string;
  holdings?: Record<string, unknown>[];
};

export type SavedPortfolioHolding = {
  ticker: string;
  shares: number | null;
  cost_basis: number | null;
  market_value: number | null;
  weight: number | null;
  sector: string | null;
  account: string | null;
  notes: string | null;
};

export type SavedPortfolio = {
  name: string;
  updated_at: string;
  holding_count: number;
  holdings: SavedPortfolioHolding[];
};

export type SavedPortfoliosPayload = {
  api_version: string;
  status: "ready" | string;
  portfolio_count: number;
  portfolios: SavedPortfolio[];
};

export type SavePortfolioPayload = {
  api_version: string;
  status: "ready" | "invalid" | string;
  message: string;
  errors: { message: string; row_number: number | null; column: string | null }[];
  portfolio: SavedPortfolio | null;
};

export type DeletePortfolioPayload = {
  api_version: string;
  status: "deleted" | "missing" | string;
  message: string;
  deleted: boolean;
};

export type ApiResult<T> = {
  ok: boolean;
  data: T | null;
  error: string;
};

export type RefreshJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | string;

export type RefreshJobPayload = {
  job_id: string;
  lane_id: string;
  status: RefreshJobStatus;
  progress_pct: number;
  message: string;
  status_url: string;
  events_url: string;
};

export async function triggerRefresh(laneId = "all") {
  return postDashboardApi<RefreshJobPayload>("/api/v1/refresh", {
    lane_id: laneId,
    run_now: true,
    background: true,
  });
}

export async function pollRefreshJob(jobId: string) {
  return fetchDashboardApi<RefreshJobPayload>(`/api/v1/refresh/${jobId}`);
}

// Server-side: use direct FastAPI URL. Client-side: use relative URLs so
// requests go to the Next.js server on the same origin and are proxied to
// FastAPI via the rewrites in next.config.mjs. This handles deployments where
// the browser cannot reach 127.0.0.1:8000 directly (e.g. port-forwarded).
const API_BASE_URL =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://127.0.0.1:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL || "";

function endpoint(path: string): string {
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

export async function fetchDashboardApi<T>(path: string): Promise<ApiResult<T>> {
  try {
    const response = await fetch(endpoint(path), {
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      return { ok: false, data: null, error: `HTTP ${response.status}` };
    }
    return { ok: true, data: (await response.json()) as T, error: "" };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: error instanceof Error ? error.name : "FetchError"
    };
  }
}

export async function postDashboardApi<T>(path: string, payload: unknown): Promise<ApiResult<T>> {
  try {
    const response = await fetch(endpoint(path), {
      method: "POST",
      cache: "no-store",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      return { ok: false, data: null, error: `HTTP ${response.status}` };
    }
    return { ok: true, data: (await response.json()) as T, error: "" };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: error instanceof Error ? error.name : "FetchError"
    };
  }
}

export async function deleteDashboardApi<T>(path: string): Promise<ApiResult<T>> {
  try {
    const response = await fetch(endpoint(path), {
      method: "DELETE",
      cache: "no-store",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      return { ok: false, data: null, error: `HTTP ${response.status}` };
    }
    return { ok: true, data: (await response.json()) as T, error: "" };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: error instanceof Error ? error.name : "FetchError"
    };
  }
}

export async function fetchHealth() {
  return fetchDashboardApi<DashboardHealthPayload>("/api/v1/health");
}

export async function fetchDataHealth() {
  return fetchDashboardApi<DashboardHealthPayload>("/api/v1/data-health");
}

export async function fetchDashboardSnapshot(ticker?: string) {
  const query = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
  return fetchDashboardApi<DashboardSnapshotPayload>(`/api/v1/dashboard-snapshot${query}`);
}

export async function fetchBacktestArtifacts() {
  return fetchDashboardApi<BacktestArtifactsPayload>("/api/v1/backtest-artifacts");
}

export async function fetchTickerChart(ticker: string, period = "3y", benchmark?: string) {
  const query =
    `?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}` +
    (benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : "");
  return fetchDashboardApi<TickerChartPayload>(`/api/v1/ticker-chart${query}`);
}

export async function analyzePortfolio(payload: PortfolioAnalysisRequest) {
  return postDashboardApi<PortfolioAnalysisPayload>("/api/v1/portfolio/analyze", payload);
}

export async function fetchSavedPortfolios() {
  return fetchDashboardApi<SavedPortfoliosPayload>("/api/v1/portfolios");
}

export async function savePortfolio(name: string, payload: PortfolioAnalysisRequest) {
  return postDashboardApi<SavePortfolioPayload>("/api/v1/portfolios", { ...payload, name });
}

export async function deleteSavedPortfolio(name: string) {
  return deleteDashboardApi<DeletePortfolioPayload>(`/api/v1/portfolios?name=${encodeURIComponent(name)}`);
}

export type DebriefRun = {
  run_id: string;
  started_at_utc: string;
  provider: string | null;
  universe_count: number;
};

export type DebriefDecision = {
  run_id: string;
  started_at_utc: string;
  ticker: string;
  action: string | null;
  decision_type: string | null;
  rationale: string | null;
  state: string | null;
  s_score: number | null;
  f_score: number | null;
};

export type DebriefPayload = {
  api_version: string;
  generated_at: string;
  runs: DebriefRun[];
  decisions: DebriefDecision[];
};

export async function fetchDebrief(): Promise<{
  data: DebriefPayload | null;
  error: string | null;
}> {
  const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${base}/api/v1/debrief`, { cache: "no-store" });
    if (!res.ok) return { data: null, error: `HTTP ${res.status}` };
    const data = (await res.json()) as DebriefPayload;
    return { data, error: null };
  } catch (err) {
    return { data: null, error: String(err) };
  }
}
