import type { ReadinessResponse, WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";

interface SystemConfigProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
  readiness: ReadinessResponse | null;
  apiBaseUrl: string;
}

export default function SystemConfig({
  identity,
  dashboard,
  readiness,
  apiBaseUrl,
}: SystemConfigProps) {
  const rows = [
    {
      key: "API_BASE_URL",
      value: apiBaseUrl,
      description: "Frontend runtime target for the FastAPI brain service.",
    },
    {
      key: "USER_ID",
      value: identity?.userId ?? "not connected",
      description: "Local browser identity persisted for the current Sentinel session.",
    },
    {
      key: "RISK_THRESHOLD",
      value: dashboard?.profile.risk_threshold?.toFixed(4) ?? "0.6537",
      description: "Threshold returned from the per-user baseline metadata.",
    },
    {
      key: "CONTAMINATION",
      value: dashboard?.profile.contamination?.toFixed(4) ?? "0.0399",
      description: "Isolation Forest contamination value surfaced from the saved profile.",
    },
    {
      key: "MODEL_KEY",
      value: dashboard?.profile.model_s3_key ?? "not persisted yet",
      description: "Artifact key for the persisted model in S3 or MinIO.",
    },
    {
      key: "READINESS",
      value: readiness?.status ?? "unknown",
      description: "Combined Redis, Postgres, and default model readiness state.",
    },
  ];

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
          SYSTEM CONFIGURATION
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Runtime configuration exposed from the real control plane. This page is read-only on
          purpose so the browser cannot drift from backend truth.
        </p>
      </div>

      <div className="divide-y divide-border border border-border/80 bg-card/75 backdrop-blur-xl">
        {rows.map((row) => (
          <div
            key={row.key}
            className="flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-background/35 sm:flex-row sm:items-start sm:justify-between"
          >
            <div className="sm:max-w-[60%]">
              <div className="text-[12px] font-bold tracking-[0.12em] text-foreground">
                {row.key}
              </div>
              <div className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {row.description}
              </div>
            </div>
            <div className="border border-border/80 bg-background/40 px-3 py-2 font-mono text-sm text-primary">
              {row.value}
            </div>
          </div>
        ))}
      </div>

      <div className="border border-border/80 bg-card/75 p-4 text-sm leading-relaxed text-muted-foreground backdrop-blur-xl">
        The active baseline currently references{" "}
        <span className="text-foreground">{dashboard?.profile.trade_count ?? 0}</span> indexed
        trades and reports Redis{" "}
        <span className={readiness?.redis_connected ? "text-secondary" : "text-destructive"}>
          {readiness?.redis_connected ? "connected" : "disconnected"}
        </span>
        , Postgres{" "}
        <span className={readiness?.db_connected ? "text-secondary" : "text-destructive"}>
          {readiness?.db_connected ? "connected" : "disconnected"}
        </span>
        , and model readiness{" "}
        <span className={readiness?.model_loaded ? "text-secondary" : "text-destructive"}>
          {readiness?.model_loaded ? "loaded" : "not loaded"}
        </span>
        .
      </div>
    </div>
  );
}
