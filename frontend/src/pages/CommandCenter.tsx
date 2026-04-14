import { Link } from "react-router-dom";

import RiskGauge from "@/components/RiskGauge";
import MiniSparkline from "@/components/MiniSparkline";
import { frontendEnv } from "@/lib/env";
import type { ReadinessResponse, WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import {
  decisionBadgeTone,
  formatDecision,
  formatMode,
  formatTimestamp,
  latestTopReason,
  riskStroke,
  riskTextTone,
} from "@/lib/presentation";

interface CommandCenterProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
  readiness: ReadinessResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
}

export default function CommandCenter({
  identity,
  dashboard,
  readiness,
  isLoading,
  onRefresh,
}: CommandCenterProps) {
  if (!identity) {
    return (
      <div className="mx-auto max-w-4xl py-8">
        <div className="border border-border/80 bg-card/75 p-8 backdrop-blur-xl">
          <h1 className="font-display text-3xl font-bold tracking-wide text-foreground">
            Sentinel Command Center
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            This dashboard is now wired to the FastAPI brain, Vault-backed onboarding flow,
            Redis cache, and per-user model persistence. Connect a trader identity to start
            streaming real baseline and audit data.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/workspace/onboarding"
              className="border border-primary/50 bg-primary/10 px-4 py-3 text-center text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20"
            >
              START ONBOARDING
            </Link>
            {frontendEnv.adminEnabled ? (
              <Link
                to="/workspace/admin"
                className="border border-border px-4 py-3 text-center text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-secondary/40 hover:text-secondary"
              >
                VIEW CONTROL PLANE
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const latest = dashboard?.latest_assessment ?? null;
  const riskScore = latest?.risk_score ?? 0;
  const sizeMultiplier = latest?.size_multiplier ?? 1;
  const riskSeries = dashboard?.recent_audits
    .slice(0, 20)
    .map((audit) => audit.risk_score)
    .reverse() ?? [];
  const modeLabel = latest
    ? formatMode(latest.mode)
    : dashboard?.blank_baseline
      ? "BASELINE PENDING"
      : "AWAITING TELEMETRY";
  const baselineLabel = dashboard?.profile.is_baseline_ready
    ? "PERSONALIZED MODEL READY"
    : dashboard?.blank_baseline
      ? "BLANK BASELINE"
      : "HISTORY PENDING";

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
            COMMAND CENTER
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Monitoring identity-bound inference for <span className="text-foreground">{identity.userId}</span>.
            The feed below is generated from persisted risk audits, not client-side mock timers.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`border px-2 py-1 text-[10px] tracking-[0.16em] ${
              readiness?.status === "ready"
                ? "border-secondary/40 text-secondary"
                : "border-primary/40 text-primary"
            }`}
          >
            {readiness?.status === "ready" ? "BRAIN READY" : "DEGRADED"}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="border border-border px-3 py-2 text-[10px] tracking-[0.16em] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
          >
            REFRESH
          </button>
        </div>
      </div>

      <div className="grid gap-px bg-border md:grid-cols-2 xl:grid-cols-4">
        <div className="bg-card/80 px-5 py-4 backdrop-blur-xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
              Live Risk
            </span>
            {riskSeries.length > 1 ? (
              <MiniSparkline data={riskSeries} color={riskStroke(riskScore)} width={70} height={22} />
            ) : null}
          </div>
          <div className={`text-4xl font-bold leading-none ${riskTextTone(riskScore)}`}>
            {riskScore.toFixed(4)}
          </div>
          <div className="mt-3 text-[10px] tracking-[0.16em] text-muted-foreground">
            {latest ? latest.symbol : "No symbol scored yet"}
          </div>
        </div>

        <div className="bg-card/80 px-5 py-4 backdrop-blur-xl">
          <div className="mb-3 text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
            Position Gate
          </div>
          <div className="text-4xl font-bold leading-none text-foreground">
            {sizeMultiplier.toFixed(2)}
            <span className="ml-1 text-2xl text-muted-foreground">x</span>
          </div>
          <div className="mt-3 h-[3px] bg-muted/60">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${Math.max(6, sizeMultiplier * 100)}%` }}
            />
          </div>
        </div>

        <div className="bg-card/80 px-5 py-4 backdrop-blur-xl">
          <div className="mb-3 text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
            Brain Mode
          </div>
          <div className="text-lg font-bold tracking-[0.14em] text-primary">{modeLabel}</div>
          <div className="mt-3 text-[10px] leading-relaxed text-muted-foreground">
            {latestTopReason(latest)}
          </div>
        </div>

        <div className="bg-card/80 px-5 py-4 backdrop-blur-xl">
          <div className="mb-3 text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
            Baseline
          </div>
          <div className="text-lg font-bold tracking-[0.14em] text-secondary">{baselineLabel}</div>
          <div className="mt-3 text-[10px] text-muted-foreground">
            {dashboard?.profile.trade_count ?? 0} trades indexed
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_420px]">
        <div className="border border-border/80 bg-card/75 py-6 backdrop-blur-xl">
          <RiskGauge score={riskScore} threshold={dashboard?.profile.risk_threshold ?? 0.6537} />
        </div>

        <div className="grid gap-px bg-border">
          {[
            {
              label: "PROTECTION EVENTS",
              value: String(dashboard?.protection_events ?? 0),
              accent: "text-secondary",
            },
            {
              label: "AVG LATENCY",
              value: `${(dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`,
              accent: "text-primary",
            },
            {
              label: "BLOCKED DECISIONS",
              value: String(dashboard?.decision_counts.BLOCK ?? 0),
              accent: "text-destructive",
            },
            {
              label: "MODEL ARTIFACT",
              value: dashboard?.profile.model_s3_key ?? "Awaiting S3 persistence",
              accent: "text-foreground",
            },
          ].map((item) => (
            <div key={item.label} className="bg-card/80 px-5 py-4 backdrop-blur-xl">
              <div className="mb-2 text-[9px] tracking-[0.2em] text-muted-foreground uppercase">
                {item.label}
              </div>
              <div className={`text-sm font-bold leading-relaxed ${item.accent}`}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="border border-border/80 bg-card/75 backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-border/80 px-5 py-3">
          <span className="text-[9px] tracking-[0.2em] text-muted-foreground">
            DECISION AUDIT LOG
          </span>
          <span className="text-[9px] text-muted-foreground">
            {dashboard?.recent_audits.length ?? 0} ENTRIES
          </span>
        </div>

        {isLoading ? (
          <div className="px-5 py-6 text-sm text-muted-foreground">Loading dashboard state...</div>
        ) : dashboard?.recent_audits.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-border/60">
                  {["TIME", "SYMBOL", "DECISION", "RISK", "SIZE", "MODE", "TOP SIGNAL"].map((header) => (
                    <th
                      key={header}
                      className="px-5 py-2 text-left text-[9px] font-normal tracking-[0.15em] text-muted-foreground"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dashboard.recent_audits.map((audit, index) => (
                  <tr
                    key={`${audit.audit_id ?? audit.created_at}-${index}`}
                    className={index % 2 === 0 ? "bg-card/80" : "bg-background/35"}
                  >
                    <td className="px-5 py-2 text-muted-foreground">{formatTimestamp(audit.created_at)}</td>
                    <td className="px-5 py-2 text-foreground">{audit.symbol}</td>
                    <td className="px-5 py-2">
                      <span
                        className={`inline-block border px-2 py-0.5 text-[9px] tracking-[0.1em] ${decisionBadgeTone(audit.decision)}`}
                      >
                        {formatDecision(audit.decision)}
                      </span>
                    </td>
                    <td className={`px-5 py-2 ${riskTextTone(audit.risk_score)}`}>
                      {audit.risk_score.toFixed(4)}
                    </td>
                    <td className="px-5 py-2 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                    <td className="px-5 py-2 text-muted-foreground">{formatMode(audit.mode)}</td>
                    <td className="px-5 py-2 text-muted-foreground">
                      {audit.top_reason ?? (audit.explanation[0]?.feature || "No explanation")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-6 text-sm leading-relaxed text-muted-foreground">
            No audits are stored for this identity yet. Open the Trading page to send a live
            decision probe or finish onboarding to let the bridge start streaming telemetry.
          </div>
        )}
      </div>
    </div>
  );
}
