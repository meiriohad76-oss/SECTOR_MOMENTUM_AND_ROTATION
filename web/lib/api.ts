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

export type ApiResult<T> = {
  ok: boolean;
  data: T | null;
  error: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  "http://127.0.0.1:8000";

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

export async function fetchHealth() {
  return fetchDashboardApi<DashboardHealthPayload>("/api/v1/health");
}

export async function fetchDataHealth() {
  return fetchDashboardApi<DashboardHealthPayload>("/api/v1/data-health");
}
