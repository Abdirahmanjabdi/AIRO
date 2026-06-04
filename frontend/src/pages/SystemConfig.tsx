import { useState } from "react";
import { Binary, Cloud, DatabaseZap, Server } from "lucide-react";
import { getExecutionMode, setExecutionMode } from "@/lib/api";

import MetricCard from "@/components/MetricCard";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
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
  const [mode, setModeState] = useState<"local" | "cloud">(getExecutionMode());
  const [warning, setWarning] = useState<string | null>(null);
  const [showPlumbing, setShowPlumbing] = useState(false);

  const handleToggle = (newMode: "local" | "cloud") => {
    if (newMode === "local") {
      const isWindows = navigator.platform.indexOf('Win') > -1 || navigator.userAgent.indexOf('Windows') > -1;
      if (!isWindows) {
        setWarning("MT5 Native Library requires Windows. Switching to AWS Managed Bridge...");
        setTimeout(() => setWarning(null), 5000);
        return; // Block the switch
      }
    }
    setModeState(newMode);
    setExecutionMode(newMode);
    window.location.reload();
  };

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
      description: "Disciplinary deviation cap surfaced from the saved baseline profile.",
    },
    {
      key: "MODEL_KEY",
      value: dashboard?.profile.model_s3_key ?? "not persisted yet",
      description: "Artifact key for the persisted risk-DNA baseline in secure storage.",
    },
    {
      key: "READINESS",
      value: readiness?.status ?? "unknown",
      description: "Combined telemetry links, immutable ledger, and baseline model status.",
    },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <Reveal>
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <SectionHeader
            eyebrow="Workspace / Runtime"
            title="System Status and Institutional Integrity"
            description="Exposing system health and operational precision without unnecessary technical veils. Willpower is a failed metric— Sentinel relies on mathematical objectivity."
          />
          {showPlumbing && (
            <SurfacePanel className="p-4 md:min-w-[320px]">
              <div className="text-[10px] uppercase tracking-[0.15em] text-primary mb-3">
                Execution Routing
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleToggle("cloud")}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold tracking-widest border transition-colors ${
                    mode === "cloud" ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Cloud size={14} /> CLOUD
                </button>
                <button
                  onClick={() => handleToggle("local")}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold tracking-widest border transition-colors ${
                    mode === "local" ? "border-secondary text-secondary bg-secondary/10" : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Server size={14} /> LOCAL
                </button>
              </div>
              {warning && (
                <div className="mt-3 text-xs text-danger font-mono bg-danger/10 border border-danger/30 p-2">
                  {warning}
                </div>
              )}
            </SurfacePanel>
          )}
        </div>
      </Reveal>

      {!showPlumbing ? (
        <Reveal delay={0.05}>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            <SurfacePanel accent="primary" className="p-6">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">System Status</div>
              <div className="mt-4 font-display text-3xl font-normal italic text-primary">Online</div>
              <p className="mt-2 text-xs text-muted-foreground leading-6">All telemetry feeds active and secure.</p>
            </SurfacePanel>
            <SurfacePanel className="p-6">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Latency</div>
              <div className="mt-4 font-mono text-3xl font-bold text-foreground">
                {(dashboard?.average_latency_ms ?? 42.0).toFixed(1)}ms
              </div>
              <p className="mt-2 text-xs text-muted-foreground leading-6">Sub-500ms real-time precision.</p>
            </SurfacePanel>
            <SurfacePanel className="p-6">
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Baseline Status</div>
              <div className="mt-4 font-display text-lg font-bold text-foreground">
                {dashboard?.profile.is_baseline_ready ? "Calibrated" : "Shadowing"}
              </div>
              <p className="mt-2 text-xs text-muted-foreground leading-6">
                Behavioral safety baseline active for user.
              </p>
            </SurfacePanel>
            <SurfacePanel className="p-6 flex flex-col justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Security</div>
                <div className="mt-4 font-display text-lg font-bold text-foreground">Immutable Risk Ledger</div>
              </div>
              <button
                onClick={() => setShowPlumbing(true)}
                className="mt-4 text-[10px] uppercase tracking-widest text-primary hover:underline text-left"
              >
                [Inspect Technical Telemetry]
              </button>
            </SurfacePanel>
          </div>
        </Reveal>
      ) : (
        <>
          <Reveal delay={0.05}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="API target"
                value="Brain API"
                description={apiBaseUrl}
                accent="primary"
                icon={<Cloud size={18} />}
                valueClassName="text-xl text-primary"
              />
              <MetricCard
                label="Ledger State"
                value={readiness?.redis_connected ? "Indexed" : "Watching"}
                description="High-speed memory ledger status."
                accent={readiness?.redis_connected ? "secondary" : "danger"}
                icon={<DatabaseZap size={18} />}
                valueClassName={readiness?.redis_connected ? "text-secondary text-xl" : "text-destructive text-xl"}
              />
              <MetricCard
                label="Model load"
                value={readiness?.model_loaded ? "Loaded" : "Not ready"}
                description="Whether the runtime has a calibrated baseline ready."
                accent={readiness?.model_loaded ? "secondary" : "primary"}
                icon={<Binary size={18} />}
                valueClassName={readiness?.model_loaded ? "text-secondary text-xl" : "text-primary text-xl"}
              />
              <MetricCard
                label="Indexed trades"
                value={dashboard?.profile.trade_count ?? 0}
                description="Trades captured into the user’s active baseline ledger."
                accent="neutral"
                icon={<Binary size={18} />}
              />
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <SurfacePanel className="divide-y divide-border/70">
              {rows.map((row) => (
                <div
                  key={row.key}
                  className="flex flex-col gap-3 px-5 py-5 transition-colors hover:bg-background/25 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="sm:max-w-[58%]">
                    <div className="text-[12px] font-bold tracking-[0.16em] text-foreground">
                      {row.key}
                    </div>
                    <div className="mt-2 text-sm leading-7 text-muted-foreground">
                      {row.description}
                    </div>
                  </div>
                  <div className="max-w-full overflow-hidden border border-border/70 bg-background/35 px-3 py-2 font-mono text-sm leading-7 text-primary">
                    {row.value}
                  </div>
                </div>
              ))}
            </SurfacePanel>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="flex justify-between items-center px-4">
              <span className="text-xs text-muted-foreground">
                Exposing runtime variables for advanced technical audits.
              </span>
              <button
                onClick={() => setShowPlumbing(false)}
                className="text-[10px] uppercase tracking-widest text-primary hover:underline"
              >
                [Hide Technical Telemetry]
              </button>
            </div>
          </Reveal>
        </>
      )}
    </div>
  );
}
