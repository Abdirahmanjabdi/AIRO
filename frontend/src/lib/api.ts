export type Decision = "ALLOW" | "BLOCK" | "REDUCE_SIZE";
export type OnboardingState =
  | "pending"
  | "pulling_history"
  | "training"
  | "blank_baseline"
  | "ready"
  | "failed";
export type RiskMode = "normal" | "risk_off" | "baseline_pending";

export interface FeatureContribution {
  feature: string;
  impact: number;
}

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  model_loaded: boolean;
  redis_connected: boolean;
  db_connected: boolean;
  details: Record<string, string>;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  version: string;
  timestamp: string;
}

export interface UserBaseline {
  user_id: string;
  broker_server: string | null;
  account_id: string | null;
  trade_count: number;
  model_s3_key: string | null;
  trained_at: string | null;
  is_baseline_ready: boolean;
  risk_threshold: number;
  contamination: number;
}

export interface CredentialResponse {
  user_id: string;
  stored: boolean;
  vault_path: string;
}

export interface OnboardingStatus {
  job_id: string;
  user_id: string;
  state: OnboardingState;
  trade_count: number;
  message: string;
  model_s3_key: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RiskAuditRecord {
  audit_id: number | null;
  user_id: string;
  symbol: string;
  decision: Decision;
  risk_score: number;
  size_multiplier: number;
  mode: RiskMode;
  is_anomaly: boolean;
  top_reason: string | null;
  explanation: FeatureContribution[];
  latency_ms: number;
  cached: boolean;
  created_at: string;
}

export interface WorkspaceSummary {
  user_id: string;
  profile: UserBaseline;
  recent_audits: RiskAuditRecord[];
  latest_assessment: RiskAuditRecord | null;
  decision_counts: Record<string, number>;
  average_risk_score: number;
  average_latency_ms: number;
  protection_events: number;
  blank_baseline: boolean;
}

export interface AdminUserRecord {
  user_id: string;
  broker_server: string | null;
  account_id: string | null;
  email: string | null;
  plan: string | null;
  provisioning_state: string | null;
  helm_release: string | null;
  trade_count: number;
  is_baseline_ready: boolean;
  model_s3_key: string | null;
  trained_at: string | null;
  latest_risk_score: number | null;
  latest_decision: Decision | null;
  latest_mode: RiskMode | null;
  last_audit_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AdminOverview {
  total_users: number;
  baseline_ready_users: number;
  active_api_credentials: number;
  total_audits: number;
  blocked_decisions: number;
  reduced_decisions: number;
  average_risk_score: number;
  users: AdminUserRecord[];
  recent_jobs: OnboardingStatus[];
}

export interface RiskAssessment {
  decision: Decision;
  risk_score: number;
  is_anomaly: boolean;
  size_multiplier: number;
  explanation: FeatureContribution[];
  latency_ms: number;
  mode: RiskMode;
}

export interface AnalyzeTradeRequest {
  user_id: string;
  symbol: string;
  hour_decimal: number;
  losing_streak: number;
  drawdown_state: number;
  lot_deviation: number;
  revenge_timer: number;
  lots: number;
  rr_ratio: number;
  realized_vol_20: number;
  trend_momentum: number;
}

export interface CredentialRequest {
  user_id: string;
  broker_server: string;
  account_id: string;
  read_only_password: string;
}

export interface OnboardingRequest {
  user_id: string;
  broker_server: string;
  account_id: string;
  min_trades?: number;
}

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_BRAIN_API_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }

  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

const API_BASE_URL = resolveApiBaseUrl();

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

async function parseError(response: Response): Promise<never> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : JSON.stringify(payload);
    throw new ApiError(detail || `Request failed with ${response.status}`, response.status, payload);
  }

  const text = await response.text();
  throw new ApiError(text || `Request failed with ${response.status}`, response.status, text);
}

interface ApiRequestOptions extends RequestInit {
  timeoutMs?: number;
}

function withTimeout(signal: AbortSignal | undefined, timeoutMs: number) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  return {
    signal: controller.signal,
    clear() {
      window.clearTimeout(timeout);
    },
  };
}

async function apiRequest<T>(path: string, init?: ApiRequestOptions): Promise<T> {
  const { timeoutMs = 15000, headers, signal, ...rest } = init || {};
  const timeout = withTimeout(signal, timeoutMs);

  const finalHeaders =
    rest.body instanceof FormData
      ? headers
      : {
          ...(rest.body ? { "Content-Type": "application/json" } : {}),
          ...(headers || {}),
        };

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      signal: timeout.signal,
    });
  } catch (error) {
    timeout.clear();

    if (timeout.signal.aborted) {
      throw new ApiError("Request timed out. Please try again.", 408);
    }

    const message = error instanceof Error ? error.message : "Network request failed.";
    throw new ApiError(message, 0);
  }

  timeout.clear();

  if (!response.ok) {
    return parseError(response);
  }

  return (await response.json()) as T;
}

export const sentinelApi = {
  getHealth(): Promise<HealthResponse> {
    return apiRequest("/healthz");
  },
  getReadiness(): Promise<ReadinessResponse> {
    return apiRequest("/readyz");
  },
  storeCredentials(payload: CredentialRequest): Promise<CredentialResponse> {
    return apiRequest("/v1/credentials", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  startOnboarding(payload: OnboardingRequest): Promise<OnboardingStatus> {
    return apiRequest("/v1/onboard", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getOnboardingStatus(jobId: string): Promise<OnboardingStatus> {
    return apiRequest(`/v1/onboard/${jobId}`);
  },
  getProfile(userId: string): Promise<UserBaseline> {
    return apiRequest(`/v1/user/${encodeURIComponent(userId)}/profile`);
  },
  getAudits(userId: string, limit = 50): Promise<RiskAuditRecord[]> {
    return apiRequest(`/v1/user/${encodeURIComponent(userId)}/audits?limit=${limit}`);
  },
  getDashboard(userId: string, limit = 50): Promise<WorkspaceSummary> {
    return apiRequest(`/v1/user/${encodeURIComponent(userId)}/dashboard?limit=${limit}`);
  },
  analyzeTrade(payload: AnalyzeTradeRequest): Promise<RiskAssessment> {
    return apiRequest("/v1/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getAdminOverview(): Promise<AdminOverview> {
    return apiRequest("/v1/admin/overview");
  },
};
