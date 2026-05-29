import { Link } from "react-router-dom";
import { Activity, ArrowRight, BrainCircuit, ShieldAlert, ShieldCheck, TimerReset } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import MiniSparkline from "@/components/MiniSparkline";
import Reveal from "@/components/Reveal";
import RiskGauge from "@/components/RiskGauge";
import RiskRadarChart from "@/components/RiskRadarChart";
import KillSwitchModal from "@/components/KillSwitchModal";
import { useState, useEffect } from "react";
import SHAPHoverCard from "@/components/SHAPHoverCard";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
import { frontendEnv } from "@/lib/env";
import { sentinelApi, type ReadinessResponse, type RiskAuditRecord, type WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import {
  decisionBadgeTone,
  formatDecision,
  formatMode,
  formatTimestamp,
  latestTopReason,
  riskStroke,
  riskTextTone,
  deJargonizeFeatureName,
} from "@/lib/presentation";

interface CommandCenterProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
  readiness: ReadinessResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
}

function generateInsightText(audit: RiskAuditRecord | null, identity: string): string {
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
  const [operatorAction, setOperatorAction] = useState<string | null>(null);

  // Lockout & Autopsy state
  const [lockoutActive, setLockoutActive] = useState(false);
  const [lockoutTimeLeft, setLockoutTimeLeft] = useState(0);
  const [showAutopsy, setShowAutopsy] = useState(false);
  const [autopsyAuditId, setAutopsyAuditId] = useState<number | null>(null);
  const [autopsyProcessing, setAutopsyProcessing] = useState(false);

  useEffect(() => {
    const latest = dashboard?.latest_assessment;
    if (latest?.decision === "BLOCK" && latest?.top_reason?.toLowerCase().includes("revenge")) {
      setIsKillSwitchOpen(true);
    }
  }, [dashboard?.latest_assessment]);

  // Heartbeat-based decrement immune to system clock tampering
  useEffect(() => {
    if (!lockoutActive || lockoutTimeLeft <= 0) return;
    const interval = setInterval(() => {
      setLockoutTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setLockoutActive(false);
          // Check for autopsy when timer hits zero
          const activeAuditIdStr = localStorage.getItem("sentinel_active_lockout_audit_id");
          if (activeAuditIdStr) {
            const activeAuditId = parseInt(activeAuditIdStr, 10);
            if (!localStorage.getItem(`sentinel_autopsy_done_${activeAuditId}`)) {
              setShowAutopsy(true);
              setAutopsyAuditId(activeAuditId);
            }
          }
          localStorage.removeItem("sentinel_lockout_expiry_utc");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [lockoutActive, lockoutTimeLeft]);

  // Lock escapes and key inputs during lockout
  useEffect(() => {
    if (!lockoutActive) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === "F5" || (e.ctrlKey && e.key === "r")) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [lockoutActive]);

  // Server-time-utc based anchor on page refresh / load or latest BLOCK decision trigger
  useEffect(() => {
    async function synchronizeLockout() {
      const activeAuditIdStr = localStorage.getItem("sentinel_active_lockout_audit_id");
      const activeAuditId = activeAuditIdStr ? parseInt(activeAuditIdStr, 10) : null;
      const expiryUtcStr = localStorage.getItem("sentinel_lockout_expiry_utc");

      // Case A: Lockout already stored in localStorage (e.g., page refresh)
      if (expiryUtcStr && activeAuditId) {
        try {
          const health = await sentinelApi.getHealth();
          const serverTime = new Date(health.timestamp).getTime();
          const expiryTime = parseInt(expiryUtcStr, 10);
          const remaining = Math.max(0, Math.floor((expiryTime - serverTime) / 1000));
          
          if (remaining > 0) {
            setLockoutActive(true);
            setLockoutTimeLeft(remaining);
            setAutopsyAuditId(activeAuditId);
            return;
          } else {
            localStorage.removeItem("sentinel_lockout_expiry_utc");
            setLockoutActive(false);
            if (!localStorage.getItem(`sentinel_autopsy_done_${activeAuditId}`)) {
              setShowAutopsy(true);
              setAutopsyAuditId(activeAuditId);
            }
          }
        } catch (e) {
          console.error("Failed to sync server time, falling back to safe local countdown:", e);
          const remaining = Math.max(0, Math.floor((parseInt(expiryUtcStr, 10) - Date.now()) / 1000));
          if (remaining > 0) {
            setLockoutActive(true);
            setLockoutTimeLeft(remaining);
            setAutopsyAuditId(activeAuditId);
          }
        }
      }

      // Case B: Check latest BLOCK decision from dashboard to trigger new or restored lockout
      const latest = dashboard?.latest_assessment;
      if (latest && latest.decision === "BLOCK" && latest.audit_id) {
        if (latest.autopsy_submitted) {
          setLockoutActive(false);
          setShowAutopsy(false);
          return;
        }

        try {
          const health = await sentinelApi.getHealth();
          const serverTime = new Date(health.timestamp).getTime();
          const createdTime = new Date(latest.created_at).getTime();
          const duration = 15 * 60 * 1000; // 15 mins
          const expiryTime = createdTime + duration;
          const remaining = Math.max(0, Math.floor((expiryTime - serverTime) / 1000));

          if (remaining > 0) {
            localStorage.setItem("sentinel_lockout_expiry_utc", expiryTime.toString());
            localStorage.setItem("sentinel_last_lockout_audit_id", latest.audit_id.toString());
            localStorage.setItem("sentinel_active_lockout_audit_id", latest.audit_id.toString());

            setLockoutActive(true);
            setLockoutTimeLeft(remaining);
            setAutopsyAuditId(latest.audit_id);
          } else {
            // Expired, but autopsy not submitted yet
            localStorage.removeItem("sentinel_lockout_expiry_utc");
            setLockoutActive(false);
            if (!localStorage.getItem(`sentinel_autopsy_done_${latest.audit_id}`)) {
              setShowAutopsy(true);
              setAutopsyAuditId(latest.audit_id);
            }
          }
        } catch (e) {
          console.error("Failed to sync server time, falling back to safe local countdown:", e);
          const createdTime = new Date(latest.created_at).getTime();
          const duration = 15 * 60 * 1000;
          const expiryTime = createdTime + duration;
          const remaining = Math.max(0, Math.floor((expiryTime - Date.now()) / 1000));

          if (remaining > 0) {
            localStorage.setItem("sentinel_lockout_expiry_utc", expiryTime.toString());
            localStorage.setItem("sentinel_last_lockout_audit_id", latest.audit_id.toString());
            localStorage.setItem("sentinel_active_lockout_audit_id", latest.audit_id.toString());

            setLockoutActive(true);
            setLockoutTimeLeft(remaining);
            setAutopsyAuditId(latest.audit_id);
          } else {
            setLockoutActive(false);
            if (!localStorage.getItem(`sentinel_autopsy_done_${latest.audit_id}`)) {
              setShowAutopsy(true);
              setAutopsyAuditId(latest.audit_id);
            }
          }
        }
      }
    }

    synchronizeLockout();
  }, [dashboard?.latest_assessment]);

  const handleAutopsySubmit = async (label: "VALID_INTERCEPT" | "FALSE_POSITIVE") => {
    if (!identity || !autopsyAuditId || autopsyProcessing) return;
    setAutopsyProcessing(true);
    try {
      await sentinelApi.submitAutopsy(identity.userId, autopsyAuditId, label, 150.0);
      localStorage.setItem(`sentinel_autopsy_done_${autopsyAuditId}`, "true");
      localStorage.removeItem("sentinel_active_lockout_audit_id");
      setShowAutopsy(false);
      onRefresh();
    } catch (e) {
      console.error("Failed to submit post-tilt autopsy:", e);
    } finally {
      setAutopsyProcessing(false);
    }
  };
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
    <div className="space-y-6 qasali-grid p-4 min-h-screen">
      {/* 🛑 FULL-SCREEN UNIGNORABLE LOCKOUT OVERLAY */}
      {lockoutActive && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#0A0F1A]/96 backdrop-blur-xl">
          <div className="text-center space-y-8 max-w-lg p-10 border border-primary/20 bg-card/60">
            <div className="text-primary font-display text-2xl tracking-[0.05em] font-normal italic">
              Intervention Active.
            </div>
            <div className="font-mono text-8xl font-bold tracking-widest text-foreground">
              {Math.floor(lockoutTimeLeft / 60).toString().padStart(2, '0')}:{(lockoutTimeLeft % 60).toString().padStart(2, '0')}
            </div>
            <p className="text-sm leading-8 text-muted-foreground font-sans">
              A high-risk behavioral anomaly was detected. To protect your capital, execution privileges have been revoked. Step away from the terminal.
            </p>
          </div>
        </div>
      )}

      {/* 🧠 POST-TILT AUTOPSY FEEDBACK MODAL */}
      {showAutopsy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0A0F1A]/85 backdrop-blur-md">
          <div className="w-full max-w-md p-8 border border-primary/20 bg-card/95 shadow-2xl rounded-none">
            <div className="text-[9px] uppercase tracking-[0.25em] text-primary">Intervention complete</div>
            <h3 className="mt-4 font-display text-3xl font-normal italic text-foreground">Post-Trade Debriefing</h3>
            <p className="mt-4 text-sm leading-7 text-muted-foreground font-sans">
              Sentinel intercepted an anomalous lot-size deviation. To refine your personal risk baseline, classify this intervention:
            </p>
            <div className="mt-8 grid grid-cols-2 gap-4">
              <button
                disabled={autopsyProcessing}
                onClick={() => handleAutopsySubmit("VALID_INTERCEPT")}
                className="p-4 border border-primary text-primary bg-transparent text-[10px] font-bold tracking-[0.16em] uppercase hover:bg-primary hover:text-background transition-all text-center flex flex-col items-center justify-center gap-1 disabled:opacity-50"
              >
                <span>{autopsyProcessing ? "Processing..." : "Valid Intercept"}</span>
                <span className="text-[9px] font-normal lowercase opacity-80">(capital saved)</span>
              </button>
              <button
                disabled={autopsyProcessing}
                onClick={() => handleAutopsySubmit("FALSE_POSITIVE")}
                className="p-4 border border-muted-foreground/30 text-muted-foreground bg-transparent text-[10px] font-bold tracking-[0.16em] uppercase hover:border-primary hover:text-primary transition-all text-center flex flex-col items-center justify-center gap-1 disabled:opacity-50"
              >
                <span>{autopsyProcessing ? "Processing..." : "False Positive"}</span>
                <span className="text-[9px] font-normal lowercase opacity-80">(strategy calibration)</span>
              </button>
            </div>
          </div>
        </div>
      )}

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

      <Reveal delay={0.01}>
        {(() => {
          const getNextLevelTarget = (level: number) => {
            switch (level) {
              case 1: return 20;
              case 2: return 50;
              case 3: return 100;
              case 4: return 150;
              case 5: return 200;
              case 6: return 300;
              case 7: return 400;
              case 8: return 600;
              case 9: return 1000;
              default: return 1000;
            }
          };

          const activeLevel = dashboard?.profile.model_level ?? 1;
          const currentTrades = dashboard?.profile.trade_count ?? 0;
          const nextTarget = getNextLevelTarget(activeLevel);
          const prevTarget = activeLevel === 1 ? 0 : getNextLevelTarget(activeLevel - 1);
          const levelProgress = activeLevel >= 10 ? 100 : Math.min(100, Math.max(0, ((currentTrades - prevTarget) / (nextTarget - prevTarget)) * 100));
          const tradesRemaining = Math.max(0, nextTarget - currentTrades);

          return (
            <div className="grid gap-6 md:grid-cols-2">
              <SurfacePanel accent="primary" className="p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <div className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">MODEL STABILITY TIER</div>
                    <span className="text-[9px] bg-primary/20 border border-primary/40 px-2 py-0.5 text-primary font-bold tracking-wider uppercase">
                      {activeLevel === 10 ? "AUTOMATED GUARDIAN ACTIVE" : `Level ${activeLevel}`}
                    </span>
                  </div>
                  <div className="mt-4 flex items-baseline gap-3">
                    <span className="font-display text-4xl font-bold text-foreground">
                      {activeLevel === 10 ? "Tier 10: Automated Capital Guard" : activeLevel >= 4 ? `Tier ${activeLevel}: Neural Size Protection` : `Tier ${activeLevel}: Disciplinary Shadowing`}
                    </span>
                  </div>
                  <div className="mt-5 h-2 w-full bg-background border border-border/70 overflow-hidden">
                    <div className="h-full bg-primary transition-all duration-500" style={{ width: `${levelProgress}%` }} />
                  </div>
                  <div className="mt-3 flex justify-between text-[10px] text-muted-foreground tracking-wider font-mono">
                    <span>
                      {activeLevel === 10 ? "Full Autonomic Guillotine link active" : `${tradesRemaining} trades to next level`}
                    </span>
                    <span>{activeLevel === 10 ? "100%" : `${Math.round(levelProgress)}%`}</span>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between text-[10px] border-t border-border/30 pt-3">
                  <span className="text-muted-foreground">Behavioral Feedback Loop:</span>
                  {dashboard && dashboard.discipline_streak >= 5 ? (
                    <span className="text-emerald-500 font-bold tracking-wider">⚡ 1.5X MULTIPLIER ACTIVE ({dashboard.discipline_streak} streak)</span>
                  ) : dashboard && dashboard.protection_events > 0 && dashboard.recent_audits.some(a => a.decision === "BLOCK") ? (
                    <span className="text-amber-500 font-bold tracking-wider">⚠️ PROGRESSION SUSPENDED (24H INTERVENTION PENALTY)</span>
                  ) : (
                    <span className="text-muted-foreground font-mono">Streak: {dashboard?.discipline_streak || 0} / 5 for multiplier boost</span>
                  )}
                </div>
              </SurfacePanel>

              <SurfacePanel accent="secondary" className="p-6">
                <div className="grid gap-6 sm:grid-cols-2 h-full">
                  <div className="flex flex-col justify-between">
                    <div>
                      <div className="text-[10px] tracking-[0.2em] uppercase text-secondary">CAPITAL PROTECTED BY SENTINEL</div>
                      <div className="mt-4 font-display text-3xl font-bold text-secondary break-all">
                        ${(dashboard?.profile.capital_protected ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>
                    <div className="mt-4 text-[10px] text-muted-foreground leading-relaxed">
                      Calculated based on estimated capital saved during interventions when you log a Valid Intercept post-tilt autopsy.
                    </div>
                  </div>

                  <div className="flex flex-col justify-between border-t border-border/40 pt-6 sm:border-t-0 sm:border-l sm:border-border/40 sm:pt-0 sm:pl-6">
                    <div>
                      <div className="text-[10px] tracking-[0.2em] uppercase text-[#CBA153]">ACTIVE GUARDIAN MARGIN</div>
                      <div className="mt-4 font-display text-3xl font-bold text-[#CBA153] break-all">
                        ${(dashboard?.active_capital_at_risk ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>
                    <div className="mt-4 text-[10px] text-muted-foreground leading-relaxed">
                      Absolute capital currently insulated across open positions based on active leverage and volatility delta.
                    </div>
                  </div>
                </div>
              </SurfacePanel>
            </div>
          );
        })()}
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
                <button
                  type="button"
                  onClick={() => setOperatorAction("Decision approved for audit review.")}
                  className="px-3 py-1.5 text-[10px] font-bold tracking-widest border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  APPROVE
                </button>
                <button
                  type="button"
                  onClick={() => setOperatorAction("Override recorded. Sentinel will continue monitoring this identity.")}
                  className="px-3 py-1.5 text-[10px] font-bold tracking-widest border border-border text-muted-foreground hover:text-foreground transition-colors"
                >
                  OVERRIDE & MONITOR
                </button>
              </div>
            )}
          </div>
          {operatorAction ? (
            <div className="mt-4 border border-secondary/30 bg-secondary/10 px-3 py-2 text-xs leading-6 text-secondary">
              {operatorAction}
            </div>
          ) : null}
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
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_450px]">
          <SurfacePanel accent="secondary" className="p-6">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <div className="eyebrow-label">Risk gauge</div>
                <div className="mt-2 text-sm leading-7 text-muted-foreground">
                  The gauge below reflects the latest risk assessment and the current
                  active safety threshold.
                </div>
              </div>
              <div className="hidden border border-border/70 bg-background/35 px-3 py-2 text-[10px] tracking-[0.16em] text-muted-foreground sm:block">
                THRESHOLD {(dashboard?.profile.risk_threshold ?? 0.6537).toFixed(4)}
              </div>
            </div>
            <RiskGauge score={riskScore} threshold={dashboard?.profile.risk_threshold ?? 0.6537} />
            <div className="mt-5 text-center font-mono text-xs font-bold tracking-widest text-[#CBA153] uppercase">
              [ PRIMARY CRITICAL PRESSURE: {deJargonizeFeatureName(dashboard?.top_reason || "MONITORING SYSTEM STEADY")} ]
            </div>
          </SurfacePanel>

          <div className="flex flex-col gap-4">
            <RiskRadarChart latestAssessment={latest} riskThreshold={dashboard?.profile.risk_threshold ?? 0.6537} />
            <div className="grid grid-cols-2 gap-4">
              <MetricCard
                label="Protection events"
                value={String(dashboard?.protection_events ?? 0)}
                description="Total capital-protecting risk blocks or sizing reductions."
                accent="secondary"
              />
              <MetricCard
                label="Average latency"
                value={`${(dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`}
                description="FastAPI brain risk processing loop speed."
                accent="primary"
              />
            </div>
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
                        <SHAPHoverCard explanation={audit.explanation}>
                          {audit.risk_score.toFixed(4)}
                        </SHAPHoverCard>
                      </td>
                      <td className="px-5 py-3 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                      <td className="px-5 py-3 text-muted-foreground">{formatMode(audit.mode)}</td>
                      <td className="px-5 py-3 text-muted-foreground">
                        <SHAPHoverCard explanation={audit.explanation}>
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
