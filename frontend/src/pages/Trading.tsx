import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { toast } from "@/components/ui/sonner";
import { sentinelApi, type AnalyzeTradeRequest, type WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import {
  decisionBadgeTone,
  formatDecision,
  formatMode,
  formatTimestamp,
  riskTextTone,
} from "@/lib/presentation";

interface TradingProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
}

const DEFAULT_TRADE: Omit<AnalyzeTradeRequest, "user_id"> = {
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
  values: Omit<AnalyzeTradeRequest, "user_id">;
}> = [
  {
    label: "Controlled Swing",
    description: "Disciplined sizing with healthier risk-reward and low drawdown pressure.",
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

export default function Trading({ identity, dashboard }: TradingProps) {
  const queryClient = useQueryClient();
  const [trade, setTrade] = useState(DEFAULT_TRADE);

  useEffect(() => {
    setTrade(DEFAULT_TRADE);
  }, [identity?.userId]);

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
      <div className="border border-border/80 bg-card/75 p-8 backdrop-blur-xl">
        <h1 className="font-display text-2xl font-bold text-foreground">TRADING</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Connect a trader first. The live decision probe submits telemetry into the real
          `/v1/analyze` path and writes the result into the audit table.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
          LIVE DECISION PROBE
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Send a sample trade context for <span className="text-foreground">{identity.userId}</span>.
          This hits the same FastAPI inference route the bridge uses and persists the response
          into the user audit feed.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl sm:p-6">
          <div className="mb-5 grid gap-3 lg:grid-cols-3">
            {PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => setTrade(preset.values)}
                className="border border-border/80 bg-background/35 p-4 text-left transition-colors hover:border-primary/30 hover:bg-background/55"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">
                  {preset.label}
                </div>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">
                  {preset.description}
                </div>
              </button>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[
              { key: "symbol", label: "SYMBOL", type: "text" },
              { key: "hour_decimal", label: "HOUR DECIMAL", type: "number", step: "0.1" },
              { key: "losing_streak", label: "LOSING STREAK", type: "number", step: "1" },
              { key: "drawdown_state", label: "DRAWDOWN STATE", type: "number", step: "0.1" },
              { key: "lot_deviation", label: "LOT DEVIATION", type: "number", step: "0.01" },
              { key: "revenge_timer", label: "REVENGE TIMER", type: "number", step: "0.1" },
              { key: "lots", label: "LOTS", type: "number", step: "0.01" },
              { key: "rr_ratio", label: "RR RATIO", type: "number", step: "0.01" },
              { key: "realized_vol_20", label: "REALIZED VOL", type: "number", step: "0.001" },
              { key: "trend_momentum", label: "TREND MOMENTUM", type: "number", step: "0.01" },
            ].map((field) => (
              <div key={field.key}>
                <label className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground">
                  {field.label}
                </label>
                <input
                  type={field.type}
                  step={field.step}
                  value={String(trade[field.key as keyof typeof trade])}
                  onChange={(event) => {
                    const nextValue =
                      field.type === "number" && field.key !== "symbol"
                        ? Number(event.target.value)
                        : event.target.value;
                    setTrade((current) => ({
                      ...current,
                      [field.key]: nextValue,
                    }));
                  }}
                  spellCheck={false}
                  className="h-10 w-full border border-border bg-background/70 px-3 text-sm text-foreground outline-none transition-colors focus:border-primary"
                />
              </div>
            ))}
          </div>

          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="border border-primary/50 bg-primary/10 px-4 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {mutation.isPending ? "SCORING TRADE" : "RUN DECISION PROBE"}
            </button>
            <button
              type="button"
              onClick={() => setTrade(DEFAULT_TRADE)}
              className="border border-border px-4 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-secondary/40 hover:text-secondary"
            >
              RESET DEFAULTS
            </button>
          </div>

          {mutation.error ? (
            <div className="mt-4 border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {mutation.error instanceof Error ? mutation.error.message : "Request failed."}
            </div>
          ) : null}
        </section>

        <aside className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl sm:p-5">
          <div className="mb-4">
            <h2 className="font-display text-lg font-bold text-foreground">Latest Probe</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              The result below is the direct response from the inference service.
            </p>
          </div>

          {mutation.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 border border-border/80 bg-background/40 p-4">
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    DECISION
                  </span>
                  <span
                    className={`mt-1 inline-block border px-2 py-0.5 text-[10px] tracking-[0.12em] ${decisionBadgeTone(mutation.data.decision)}`}
                  >
                    {formatDecision(mutation.data.decision)}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    RISK SCORE
                  </span>
                  <span className={`text-2xl font-bold ${riskTextTone(mutation.data.risk_score)}`}>
                    {mutation.data.risk_score.toFixed(4)}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    MODE
                  </span>
                  <span className="text-sm font-bold text-primary">
                    {formatMode(mutation.data.mode)}
                  </span>
                </div>
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    LATENCY
                  </span>
                  <span className="text-sm font-bold text-foreground">
                    {mutation.data.latency_ms.toFixed(1)} ms
                  </span>
                </div>
              </div>

              <div className="border border-border/80 bg-background/40 p-4">
                <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                  TOP FEATURES
                </span>
                <div className="mt-3 space-y-2 text-sm">
                  {mutation.data.explanation.length ? (
                    mutation.data.explanation.map((feature) => (
                      <div
                        key={`${feature.feature}-${feature.impact}`}
                        className="flex items-center justify-between border-b border-border/50 pb-2 last:border-b-0 last:pb-0"
                      >
                        <span className="text-foreground">{feature.feature}</span>
                        <span className="font-mono text-muted-foreground">
                          {feature.impact.toFixed(4)}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-muted-foreground">
                      The model returned no ranked explanation for this sample.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm leading-relaxed text-muted-foreground">
              Run a probe to inspect a live decision. The dashboard audit feed will refresh once
              the result is written.
            </div>
          )}
        </aside>
      </div>

      <div className="border border-border/80 bg-card/75 backdrop-blur-xl">
        <div className="border-b border-border/80 px-5 py-3 text-[10px] tracking-[0.18em] text-muted-foreground">
          RECENT AUDITS
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
                    className={index % 2 === 0 ? "bg-card/80" : "bg-background/35"}
                  >
                    <td className="px-5 py-2 text-muted-foreground">{formatTimestamp(audit.created_at)}</td>
                    <td className="px-5 py-2 text-foreground">{audit.symbol}</td>
                    <td className="px-5 py-2 text-foreground">{formatDecision(audit.decision)}</td>
                    <td className={`px-5 py-2 ${riskTextTone(audit.risk_score)}`}>
                      {audit.risk_score.toFixed(4)}
                    </td>
                    <td className="px-5 py-2 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                    <td className="px-5 py-2 text-muted-foreground">{formatMode(audit.mode)}</td>
                    <td className="px-5 py-2 text-muted-foreground">{audit.cached ? "YES" : "NO"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-5 py-6 text-sm text-muted-foreground">
            No audits recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}
