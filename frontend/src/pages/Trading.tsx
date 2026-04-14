import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  Clock3,
  Radar,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import MetricCard from "@/components/MetricCard";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
import { toast } from "@/components/ui/sonner";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import {
  sentinelApi,
  type AnalyzeTradeRequest,
  type RiskAssessment,
  type WorkspaceSummary,
} from "@/lib/api";
import {
  decisionBadgeTone,
  formatDecision,
  formatMode,
  formatTimestamp,
  riskTextTone,
} from "@/lib/presentation";

type TradeDraft = Omit<AnalyzeTradeRequest, "user_id">;

const DEFAULT_TRADE: TradeDraft = {
  symbol: "XAUUSD",
  hour_decimal: 14.2,
  losing_streak: 2,
  drawdown_state: 12,
  lot_deviation: 0.35,
  revenge_timer: 44,
  lots: 0.5,
  rr_ratio: 1.8,
  realized_vol_20: 0.018,
  trend_momentum: 0.11,
};

const PRESETS: Array<{
  label: string;
  description: string;
  accent: "secondary" | "primary" | "danger";
  values: TradeDraft;
}> = [
  {
    label: "Controlled Swing",
    description: "Disciplined sizing with healthier risk-reward and low drawdown pressure.",
    accent: "secondary",
    values: {
      symbol: "EURUSD",
      hour_decimal: 9.4,
      losing_streak: 0,
      drawdown_state: 3,
      lot_deviation: 0.08,
      revenge_timer: 180,
      lots: 0.2,
      rr_ratio: 2.4,
      realized_vol_20: 0.009,
      trend_momentum: 0.16,
    },
  },
  {
    label: "Revenge Burst",
    description: "Escalating size after losses with a compressed timer between entries.",
    accent: "danger",
    values: {
      symbol: "XAUUSD",
      hour_decimal: 14.2,
      losing_streak: 4,
      drawdown_state: 19,
      lot_deviation: 0.62,
      revenge_timer: 18,
      lots: 1.4,
      rr_ratio: 1.1,
      realized_vol_20: 0.021,
      trend_momentum: -0.09,
    },
  },
  {
    label: "Volatility Spike",
    description: "Market regime turns hostile while the trader keeps pushing size.",
    accent: "primary",
    values: {
      symbol: "GBPJPY",
      hour_decimal: 16.7,
      losing_streak: 2,
      drawdown_state: 11,
      lot_deviation: 0.41,
      revenge_timer: 36,
      lots: 0.75,
      rr_ratio: 1.4,
      realized_vol_20: 0.031,
      trend_momentum: 0.28,
    },
  },
];

const FIELD_GROUPS: Array<{
  title: string;
  description: string;
  accent?: "neutral" | "primary" | "secondary" | "danger";
  fields: Array<{
    key: keyof TradeDraft;
    label: string;
    type: "text" | "number";
    step?: string;
  }>;
}> = [
  {
    title: "Instrument context",
    description: "Define the symbol, session timing, and current regime variables that shape the trade.",
    accent: "secondary",
    fields: [
      { key: "symbol", label: "SYMBOL", type: "text" },
      { key: "hour_decimal", label: "HOUR DECIMAL", type: "number", step: "0.1" },
      { key: "realized_vol_20", label: "REALIZED VOL", type: "number", step: "0.001" },
      { key: "trend_momentum", label: "TREND MOMENTUM", type: "number", step: "0.01" },
    ],
  },
  {
    title: "Behavioral pressure",
    description: "Capture losing streak, drawdown pressure, and the trader's time since the last impulse.",
    accent: "primary",
    fields: [
      { key: "losing_streak", label: "LOSING STREAK", type: "number", step: "1" },
      { key: "drawdown_state", label: "DRAWDOWN STATE", type: "number", step: "0.1" },
      { key: "revenge_timer", label: "REVENGE TIMER", type: "number", step: "0.1" },
    ],
  },
  {
    title: "Position sizing",
    description: "Send the sizing inputs the backend uses to decide whether to allow, scale down, or block.",
    accent: "danger",
    fields: [
      { key: "lots", label: "LOTS", type: "number", step: "0.01" },
      { key: "lot_deviation", label: "LOT DEVIATION", type: "number", step: "0.01" },
      { key: "rr_ratio", label: "RR RATIO", type: "number", step: "0.01" },
    ],
  },
];

interface TradingProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
}

function latestResult(result: RiskAssessment | undefined, dashboard: WorkspaceSummary | null) {
  if (result) {
    return {
      decision: result.decision,
      risk_score: result.risk_score,
      mode: result.mode,
      latency_ms: result.latency_ms,
      explanation: result.explanation,
    };
  }

  return dashboard?.latest_assessment ?? null;
}

export default function Trading({ identity, dashboard }: TradingProps) {
  const queryClient = useQueryClient();
  const [trade, setTrade] = useState<TradeDraft>(DEFAULT_TRADE);

  useEffect(() => {
    setTrade(DEFAULT_TRADE);
  }, [identity?.userId]);

  function updateTradeField<Key extends keyof TradeDraft>(key: Key, value: TradeDraft[Key]) {
    setTrade((current) => ({
      ...current,
      [key]: value,
    }));
  }

  const mutation = useMutation({
    mutationFn: async () => {
      if (!identity) {
        throw new Error("Connect a user before sending a decision probe.");
      }

      return sentinelApi.analyzeTrade({
        user_id: identity.userId,
        ...trade,
      });
    },
    onSuccess: async () => {
      if (!identity) {
        return;
      }
      toast.success("Decision probe completed and audit feed refreshed.");
      await queryClient.invalidateQueries({ queryKey: ["sentinel", "dashboard", identity.userId] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Request failed.");
    },
  });

  if (!identity) {
    return (
      <div className="mx-auto max-w-5xl py-6">
        <SurfacePanel accent="secondary" className="p-8 sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_260px] lg:items-center">
            <div>
              <div className="eyebrow-label">Workspace / Decision probe</div>
              <h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
                Connect a trader before you send live telemetry to the brain.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-8 text-muted-foreground">
                The trading surface sends a real payload into `/v1/analyze`, then refreshes the
                user's persisted audit feed. It is a product control surface, not a demo widget.
              </p>
              <div className="mt-8">
                <Link
                  to="/workspace/onboarding"
                  className="inline-flex items-center gap-2 border border-primary/40 bg-primary/10 px-5 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20"
                >
                  START ONBOARDING
                  <ArrowRight size={14} />
                </Link>
              </div>
            </div>

            <MetricCard
              label="Live path"
              value="FastAPI"
              description="Probe calls the same backend inference route used by the MT5 relay."
              accent="primary"
            />
          </div>
        </SurfacePanel>
      </div>
    );
  }

  const latest = latestResult(mutation.data, dashboard);
  const latestDecision = latest ? formatDecision(latest.decision) : "Awaiting run";
  const latestRisk = latest?.risk_score ?? 0;
  const explanation = latest?.explanation ?? [];
  const threshold = dashboard?.profile.risk_threshold ?? 0.6537;

  return (
    <div className="space-y-6">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Trading"
          title={`Live decision probe for ${identity.userId}`}
          description="Send a fully structured trade context into the same FastAPI inference path used by the bridge. Every successful probe refreshes the stored audit history for this identity."
          aside={(
            <SurfacePanel accent={mutation.data ? "secondary" : "primary"} className="p-5">
              <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                Active threshold
              </div>
              <div className="mt-2 font-display text-3xl font-bold text-foreground">
                {threshold.toFixed(4)}
              </div>
              <div className="mt-4 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span className="inline-flex items-center gap-2 border border-border/70 bg-background/35 px-2 py-1 tracking-[0.16em]">
                  <Activity size={12} />
                  {dashboard?.profile.is_baseline_ready ? "MODEL READY" : "BASELINE PENDING"}
                </span>
                <span>{dashboard?.recent_audits.length ?? 0} audits loaded</span>
              </div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      <Reveal delay={0.05}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Latest decision"
            value={latestDecision}
            description="Most recent live or persisted decision returned for this trader."
            accent={latestRisk > threshold ? "danger" : latestRisk > 0.4 ? "primary" : "secondary"}
            icon={<ShieldCheck size={18} />}
            valueClassName={latestRisk > threshold ? "text-xl text-destructive" : latestRisk > 0.4 ? "text-xl text-primary" : "text-xl text-secondary"}
          />
          <MetricCard
            label="Latest risk"
            value={latest ? latest.risk_score.toFixed(4) : "0.0000"}
            description="Current risk score surfaced from the decision engine."
            accent={latestRisk > threshold ? "danger" : "primary"}
            icon={<Radar size={18} />}
            valueClassName={riskTextTone(latestRisk)}
          />
          <MetricCard
            label="Latency"
            value={`${(latest?.latency_ms ?? dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`}
            description="Observed response time for the latest probe or the visible audit window."
            accent="secondary"
            icon={<Clock3 size={18} />}
          />
          <MetricCard
            label="Brain mode"
            value={latest ? formatMode(latest.mode) : "Awaiting telemetry"}
            description="Execution posture returned from the backend risk engine."
            accent="neutral"
            icon={<BrainCircuit size={18} />}
            valueClassName="text-xl text-foreground"
          />
        </div>
      </Reveal>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_390px]">
        <Reveal delay={0.1}>
          <SurfacePanel className="p-6 sm:p-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="eyebrow-label">Decision payload builder</div>
                <h2 className="mt-3 font-display text-3xl font-bold text-foreground">
                  Shape the trade context before it ever touches inference.
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-8 text-muted-foreground">
                  Presets below let you jump between healthy, unstable, and hostile trade
                  contexts, then fine-tune every field before you send the probe to the live
                  backend.
                </p>
              </div>

              <span className="inline-flex items-center gap-2 border border-border/70 bg-background/35 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                <Sparkles size={13} />
                AUDIT WRITES ENABLED
              </span>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-3">
              {PRESETS.map((preset) => (
                <SurfacePanel
                  key={preset.label}
                  accent={preset.accent}
                  className="cursor-pointer p-5 transition-transform duration-200 hover:-translate-y-1"
                  onClick={() => setTrade(preset.values)}
                >
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    Preset
                  </div>
                  <div className="mt-3 font-display text-2xl font-bold text-foreground">
                    {preset.label}
                  </div>
                  <div className="mt-3 text-sm leading-7 text-muted-foreground">
                    {preset.description}
                  </div>
                  <div className="mt-5 flex items-center justify-between border border-border/70 bg-background/35 px-3 py-2 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                    <span>{preset.values.symbol}</span>
                    <span>{preset.values.lots.toFixed(2)} lots</span>
                  </div>
                </SurfacePanel>
              ))}
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-3">
              {FIELD_GROUPS.map((group) => (
                <SurfacePanel
                  key={group.title}
                  accent={group.accent ?? "neutral"}
                  className="p-5"
                >
                  <div className="eyebrow-label">{group.title}</div>
                  <div className="mt-3 text-sm leading-7 text-muted-foreground">
                    {group.description}
                  </div>

                  <div className="mt-5 space-y-4">
                    {group.fields.map((field) => {
                      const inputId = `trade-${String(field.key)}`;
                      const rawValue = trade[field.key];
                      return (
                        <div key={String(field.key)}>
                          <label
                            htmlFor={inputId}
                            className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                          >
                            {field.label}
                          </label>
                          <input
                            id={inputId}
                            type={field.type}
                            step={field.step}
                            value={String(rawValue)}
                            onChange={(event) => {
                              const nextValue =
                                field.type === "number"
                                  ? Number(event.target.value)
                                  : event.target.value;
                              updateTradeField(
                                field.key,
                                nextValue as TradeDraft[typeof field.key],
                              );
                            }}
                            spellCheck={false}
                            className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                          />
                        </div>
                      );
                    })}
                  </div>
                </SurfacePanel>
              ))}
            </div>

            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
                className="inline-flex items-center justify-center gap-2 border border-primary/40 bg-primary/10 px-5 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {mutation.isPending ? "SCORING TRADE" : "RUN DECISION PROBE"}
                <ArrowRight size={14} />
              </button>
              <button
                type="button"
                onClick={() => setTrade(DEFAULT_TRADE)}
                className="border border-border px-5 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-secondary/40 hover:text-secondary"
              >
                RESET DEFAULTS
              </button>
            </div>

            {mutation.error ? (
              <SurfacePanel accent="danger" className="mt-5 p-4 text-sm leading-7 text-destructive">
                {mutation.error instanceof Error ? mutation.error.message : "Request failed."}
              </SurfacePanel>
            ) : null}
          </SurfacePanel>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="space-y-4">
            <SurfacePanel accent={mutation.data ? "secondary" : "primary"} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="eyebrow-label">Latest probe</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    The response below comes directly from the inference service.
                  </div>
                </div>
                <span className="border border-border/70 bg-background/35 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  {mutation.isPending ? "RUNNING" : mutation.data ? "LIVE" : "READY"}
                </span>
              </div>

              {latest ? (
                <div className="mt-5 space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <MetricCard
                      label="Decision"
                      value={formatDecision(latest.decision)}
                      description="Recommended action for the submitted trade context."
                      accent={latest.risk_score > threshold ? "danger" : latest.risk_score > 0.4 ? "primary" : "secondary"}
                      valueClassName={latest.risk_score > threshold ? "text-xl text-destructive" : latest.risk_score > 0.4 ? "text-xl text-primary" : "text-xl text-secondary"}
                    />
                    <MetricCard
                      label="Mode"
                      value={formatMode(latest.mode)}
                      description="Execution posture returned by the backend."
                      accent="neutral"
                      valueClassName="text-xl text-foreground"
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="border border-border/70 bg-background/35 p-4">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        Risk score
                      </div>
                      <div className={`mt-3 font-display text-4xl font-bold ${riskTextTone(latest.risk_score)}`}>
                        {latest.risk_score.toFixed(4)}
                      </div>
                    </div>
                    <div className="border border-border/70 bg-background/35 p-4">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                        Latency
                      </div>
                      <div className="mt-3 font-display text-4xl font-bold text-foreground">
                        {latest.latency_ms.toFixed(1)} ms
                      </div>
                    </div>
                  </div>

                  <div className="border border-border/70 bg-background/35 p-4">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                      Top features
                    </div>
                    <div className="mt-4 space-y-3">
                      {explanation.length ? (
                        explanation.map((feature) => (
                          <div key={`${feature.feature}-${feature.impact}`} className="space-y-2">
                            <div className="flex items-center justify-between gap-3 text-sm">
                              <span className="text-foreground">{feature.feature}</span>
                              <span className="font-mono text-muted-foreground">
                                {feature.impact.toFixed(4)}
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden border border-border/70 bg-background/50">
                              <div
                                className="h-full bg-[linear-gradient(90deg,rgba(78,205,196,0.9),rgba(245,166,35,0.9))]"
                                style={{ width: `${Math.min(100, Math.max(8, Math.abs(feature.impact) * 100))}%` }}
                              />
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm leading-7 text-muted-foreground">
                          The model returned no ranked explanation for this sample.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-5 text-sm leading-8 text-muted-foreground">
                  Run a probe to inspect a live decision. The dashboard audit feed will refresh
                  once the result is written.
                </div>
              )}
            </SurfacePanel>

            <SurfacePanel className="p-5">
              <div className="eyebrow-label">Inference path</div>
              <div className="mt-4 space-y-4">
                {[
                  "Frontend assembles a typed trade context for the active user identity.",
                  "FastAPI scores the trade with the user's personalized model and policy logic.",
                  "The response is returned immediately and the audit feed is refreshed from persistence.",
                ].map((row) => (
                  <div key={row} className="border border-border/70 bg-background/35 p-4 text-sm leading-7 text-muted-foreground">
                    {row}
                  </div>
                ))}
              </div>
            </SurfacePanel>
          </div>
        </Reveal>
      </div>

      <Reveal delay={0.2}>
        <SurfacePanel className="grid-fade">
          <div className="flex flex-col gap-3 border-b border-border/70 px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="eyebrow-label">Recent audits</div>
              <div className="mt-2 text-sm leading-7 text-muted-foreground">
                Stored decisions for the active identity. These rows come back from persistence,
                not from browser-only state.
              </div>
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {dashboard?.recent_audits.length ?? 0} entries
            </div>
          </div>

          {dashboard?.recent_audits.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border/60">
                    {["TIME", "SYMBOL", "DECISION", "RISK", "SIZE", "MODE", "CACHED"].map((header) => (
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
                        {audit.risk_score.toFixed(4)}
                      </td>
                      <td className="px-5 py-3 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                      <td className="px-5 py-3 text-muted-foreground">{formatMode(audit.mode)}</td>
                      <td className="px-5 py-3 text-muted-foreground">{audit.cached ? "YES" : "NO"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="px-5 py-8 text-sm leading-7 text-muted-foreground">
              No audits recorded yet. Run a decision probe or finish onboarding to begin building
              this trader's persisted audit history.
            </div>
          )}
        </SurfacePanel>
      </Reveal>
    </div>
  );
}
