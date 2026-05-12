import { Link } from "react-router-dom";
import { Activity, ArrowRight, BrainCircuit, ShieldAlert, ShieldCheck, TimerReset } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import MiniSparkline from "@/components/MiniSparkline";
import Reveal from "@/components/Reveal";
import RiskGauge from "@/components/RiskGauge";
import KillSwitchModal from "@/components/KillSwitchModal";
import { useState, useEffect } from "react";
import SHAPHoverCard from "@/components/SHAPHoverCard";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
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

function generateInsightText(audit: any, identity: string): string {
  if (!audit) return "Awaiting live telemetry to generate behavioral insights.";
  if (audit.decision === "BLOCK") {
    return `Critical intervention: ${identity} exhibited '${audit.top_reason || 'Anomaly'}' signature on ${audit.symbol}. Immediate execution block applied.`;
  }
  if (audit.decision === "REDUCE_SIZE") {
    return `Risk elevated: ${identity} showing '${audit.top_reason || 'Volatility'}' patterns on ${audit.symbol}. Scaling position down by ${((1 - audit.size_multiplier) * 100).toFixed(0)}%.`;
  }
  return `Normal operation: ${identity} is trading ${audit.symbol} within expected behavioral bounds.`;
}

export default function CommandCenter({
  identity,
  dashboard,
  readiness,
  isLoading,
  onRefresh,
}: CommandCenterProps) {
  const [isKillSwitchOpen, setIsKillSwitchOpen] = useState(false);

  useEffect(() => {
    const latest = dashboard?.latest_assessment;
    if (latest?.decision === "BLOCK" && latest?.top_reason?.toLowerCase().includes("revenge")) {
      setIsKillSwitchOpen(true);
    }
  }, [dashboard?.latest_assessment]);
  if (!identity) {
    return (
      <div className="mx-auto max-w-5xl py-6">
        <SurfacePanel accent="secondary" className="p-8 sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
            <div>
              <div className="eyebrow-label">Workspace / Waiting for identity</div>
              <h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Connect a trader and turn the workspace live.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-8 text-muted-foreground">
                The command center is wired to the FastAPI brain, Vault-backed onboarding flow,
                Redis cache, and per-user model persistence. Once a trader is connected, the
                dashboard switches from product shell to real operator telemetry.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  to="/workspace/onboarding"
                  className="inline-flex items-center justify-center gap-2 border border-primary/40 bg-primary/10 px-5 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20"
                >
                  START ONBOARDING
                  <ArrowRight size={14} />
                </Link>
                {frontendEnv.adminEnabled ? (
                  <Link
                    to="/workspace/admin"
                    className="inline-flex items-center justify-center gap-2 border border-border px-5 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-secondary/40 hover:text-secondary"
                  >
                    VIEW CONTROL PLANE
                  </Link>
                ) : null}
              </div>
            </div>

            <div className="grid gap-4">
              <MetricCard
                label="What comes next"
                value="Vault"
                description="Seal the MT5 read-only password and queue the bridge onboarding job."
                accent="secondary"
              />
              <MetricCard
                label="Outcome"
                value="Baseline"
                description="Persist the personalized model and begin writing live decision audits."
                accent="primary"
              />
            </div>
          </div>
        </SurfacePanel>
      </div>
    );
  }

  const latest = dashboard?.latest_assessment ?? null;
  const riskScore = latest?.risk_score ?? 0;
  const sizeMultiplier = latest?.size_multiplier ?? 1;
  const riskSeries =
    dashboard?.recent_audits
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
    <div className="space-y-6">
      <KillSwitchModal isOpen={isKillSwitchOpen} onAcknowledge={() => setIsKillSwitchOpen(false)} />
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Command Center"
          title={`${identity.userId} protection overview`}
          description={
            <>
              Monitoring identity-bound inference for <span className="text-foreground">{identity.userId}</span>.
              The system below is driven by persisted audits, readiness state, and the user’s
              own baseline metadata rather than client-side demo timers.
            </>
          }
          aside={(
            <SurfacePanel className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    Control plane
                  </div>
                  <div className="mt-2 font-display text-2xl font-bold text-foreground">
                    {readiness?.status === "ready" ? "Ready" : "Degraded"}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onRefresh}
                  className="inline-flex items-center gap-2 border border-border px-3 py-2 text-[10px] tracking-[0.16em] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  <TimerReset size={13} />
                  REFRESH
                </button>
              </div>
              <div className="mt-4 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span
                  className={`inline-flex items-center gap-2 border px-2 py-1 tracking-[0.16em] ${
                    readiness?.status === "ready"
                      ? "border-secondary/30 text-secondary"
                      : "border-primary/30 text-primary"
                  }`}
                >
                  <Activity size={12} />
                  {readiness?.status === "ready" ? "BRAIN READY" : "READINESS WATCH"}
                </span>
                <span>{dashboard?.recent_audits.length ?? 0} audits loaded</span>
              </div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      <Reveal delay={0.02}>
        <SurfacePanel accent={latest?.decision === "BLOCK" ? "danger" : latest?.decision === "REDUCE_SIZE" ? "primary" : "secondary"} className="p-5 border-l-4 border-l-primary/60">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <BrainCircuit className={latest?.decision === "BLOCK" ? "text-danger" : "text-primary"} size={20} />
              <div>
                <div className="eyebrow-label mb-1">Sentinel Predictive Insight</div>
                <div className="font-display text-sm font-medium text-foreground/90">
                  {generateInsightText(latest, identity.userId)}
                </div>
              </div>
            </div>
            {latest?.decision !== "ALLOW" && latest && (
              <div className="flex gap-2 mt-3 sm:mt-0">
                <button className="px-3 py-1.5 text-[10px] font-bold tracking-widest border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 transition-colors">
                  APPROVE
                </button>
                <button className="px-3 py-1.5 text-[10px] font-bold tracking-widest border border-border text-muted-foreground hover:text-foreground transition-colors">
                  OVERRIDE & MONITOR
                </button>
              </div>
            )}
          </div>
        </SurfacePanel>
      </Reveal>

      <Reveal delay={0.05}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Live risk",
              value: riskScore.toFixed(4),
              description: latest ? latest.symbol : "No symbol scored yet",
              accent: riskScore > (dashboard?.profile.risk_threshold ?? 0.6537) ? "danger" : riskScore > 0.4 ? "primary" : "secondary",
              valueClassName: riskTextTone(riskScore),
              icon: riskSeries.length > 1 ? <MiniSparkline data={riskSeries} color={riskStroke(riskScore)} width={86} height={24} /> : null,
            },
            {
              label: "Position gate",
              value: `${sizeMultiplier.toFixed(2)}x`,
              description: "Dynamic sizing multiplier returned by the live risk engine.",
              accent: sizeMultiplier < 1.0 ? "danger" : "primary",
              icon: <ShieldCheck size={18} />,
            },
            {
              label: "Brain mode",
              value: modeLabel,
              description: latestTopReason(latest),
              accent: latest?.is_anomaly ? "danger" : "neutral",
              icon: <BrainCircuit size={18} />,
              valueClassName: "text-xl text-primary",
            },
            {
              label: "Baseline",
              value: baselineLabel,
              description: `${dashboard?.profile.trade_count ?? 0} trades indexed into the current baseline.`,
              accent: "secondary",
              icon: <ShieldAlert size={18} />,
              valueClassName: "text-xl text-secondary",
            }
          ].sort((a, b) => {
            const score = (accent: string) => accent === "danger" ? 3 : accent === "primary" ? 2 : accent === "secondary" ? 1 : 0;
            return score(b.accent) - score(a.accent);
          }).map((card, i) => (
            <MetricCard key={i} {...card} />
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_420px]">
          <SurfacePanel accent="secondary" className="p-6">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <div className="eyebrow-label">Risk gauge</div>
                <div className="mt-2 text-sm leading-7 text-muted-foreground">
                  The gauge below reflects the latest persisted assessment and the current
                  per-user threshold.
                </div>
              </div>
              <div className="hidden border border-border/70 bg-background/35 px-3 py-2 text-[10px] tracking-[0.16em] text-muted-foreground sm:block">
                THRESHOLD {(dashboard?.profile.risk_threshold ?? 0.6537).toFixed(4)}
              </div>
            </div>
            <RiskGauge score={riskScore} threshold={dashboard?.profile.risk_threshold ?? 0.6537} />
          </SurfacePanel>

          <div className="grid gap-4">
            <MetricCard
              label="Protection events"
              value={String(dashboard?.protection_events ?? 0)}
              description="Count of stored decisions that actively intervened in risk."
              accent="secondary"
            />
            <MetricCard
              label="Average latency"
              value={`${(dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`}
              description="Observed decision latency across the visible audit window."
              accent="primary"
            />
            <MetricCard
              label="Blocked decisions"
              value={String(dashboard?.decision_counts.BLOCK ?? 0)}
              description="Number of full block decisions stored for this identity."
              accent="danger"
            />
            <MetricCard
              label="Model artifact"
              value={dashboard?.profile.model_s3_key ?? "Awaiting persistence"}
              description="S3 or MinIO key for the active saved model."
              accent="neutral"
              valueClassName="text-base break-all leading-7 text-foreground"
            />
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.15}>
        <SurfacePanel className="grid-fade">
          <div className="flex flex-col gap-3 border-b border-border/70 px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="eyebrow-label">Decision audit log</div>
              <div className="mt-2 text-sm leading-7 text-muted-foreground">
                Stored trade decisions, explanations, and execution posture for the active identity.
              </div>
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {dashboard?.recent_audits.length ?? 0} entries
            </div>
          </div>

          {isLoading ? (
            <div className="px-5 py-8 text-sm text-muted-foreground">Loading dashboard state...</div>
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
                      className={index % 2 === 0 ? "bg-card/30" : "bg-background/20"}
                    >
                      <td className="px-5 py-3 text-muted-foreground">{formatTimestamp(audit.created_at)}</td>
                      <td className="px-5 py-3 text-foreground">{audit.symbol}</td>
                      <td className="px-5 py-3">
                        <span
                          className={`inline-block border px-2 py-0.5 text-[9px] tracking-[0.1em] ${decisionBadgeTone(audit.decision)}`}
                        >
                          {formatDecision(audit.decision)}
                        </span>
                      </td>
                      <td className={`px-5 py-3 ${riskTextTone(audit.risk_score)}`}>
                        <SHAPHoverCard explanation={audit.explanation as any[]}>
                          {audit.risk_score.toFixed(4)}
                        </SHAPHoverCard>
                      </td>
                      <td className="px-5 py-3 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                      <td className="px-5 py-3 text-muted-foreground">{formatMode(audit.mode)}</td>
                      <td className="px-5 py-3 text-muted-foreground">
                        <SHAPHoverCard explanation={audit.explanation as any[]}>
                          {audit.top_reason ?? (audit.explanation[0]?.feature || "No explanation")}
                        </SHAPHoverCard>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="px-5 py-8 text-sm leading-7 text-muted-foreground">
              No audits are stored for this identity yet. Open the Trading page to send a live
              decision probe or finish onboarding to let the bridge begin streaming telemetry.
            </div>
          )}
        </SurfacePanel>
      </Reveal>
    </div>
  );
}
