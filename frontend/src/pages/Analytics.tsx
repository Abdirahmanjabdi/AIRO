import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import type { WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import { formatDecision, formatTimestamp, riskStroke } from "@/lib/presentation";

interface AnalyticsProps {
  identity: SentinelIdentity | null;
  dashboard: WorkspaceSummary | null;
  isLoading: boolean;
}

export default function Analytics({ identity, dashboard, isLoading }: AnalyticsProps) {
  if (!identity) {
    return (
      <div className="border border-border/80 bg-card/75 p-8 backdrop-blur-xl">
        <h1 className="font-display text-2xl font-bold text-foreground">ANALYTICS</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Connect a user identity first so the charts can read from persisted risk audits.
        </p>
      </div>
    );
  }

  const audits = dashboard?.recent_audits ?? [];

  const riskSeries = audits
    .slice()
    .reverse()
    .map((audit, index) => ({
      index: index + 1,
      risk: Number(audit.risk_score.toFixed(4)),
      latency: Number(audit.latency_ms.toFixed(1)),
    }));

  const decisionSeries = ["ALLOW", "REDUCE_SIZE", "BLOCK"].map((decision) => ({
    decision,
    count: dashboard?.decision_counts[decision] ?? 0,
    color:
      decision === "ALLOW"
        ? "#4ECDC4"
        : decision === "REDUCE_SIZE"
          ? "#F5A623"
          : "#E63946",
  }));

  const symbolCounts = Object.entries(
    audits.reduce<Record<string, number>>((accumulator, audit) => {
      accumulator[audit.symbol] = (accumulator[audit.symbol] ?? 0) + 1;
      return accumulator;
    }, {}),
  )
    .map(([symbol, count]) => ({ symbol, count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 6);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
          ANALYTICS
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Persisted risk audits for <span className="text-foreground">{identity.userId}</span>.
          These charts are derived from the same decision records stored by the FastAPI brain.
        </p>
      </div>

      {isLoading ? (
        <div className="border border-border/80 bg-card/75 p-8 text-sm text-muted-foreground backdrop-blur-xl">
          Loading analytics...
        </div>
      ) : audits.length === 0 ? (
        <div className="border border-border/80 bg-card/75 p-8 text-sm leading-relaxed text-muted-foreground backdrop-blur-xl">
          No risk audits are stored yet. Finish onboarding or use the Trading probe to generate
          real model decisions.
        </div>
      ) : (
        <>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl">
              <div className="mb-4 text-[10px] tracking-[0.18em] text-muted-foreground">
                RISK SCORE OVER TIME
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={riskSeries}>
                  <defs>
                    <linearGradient id="sentinel-risk-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4ECDC4" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#4ECDC4" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="index" tick={{ fontSize: 10, fill: "#77808e" }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: "#77808e" }} width={32} />
                  <Area
                    type="monotone"
                    dataKey="risk"
                    stroke={riskStroke(dashboard?.latest_assessment?.risk_score ?? 0.4)}
                    fill="url(#sentinel-risk-fill)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl">
              <div className="mb-4 text-[10px] tracking-[0.18em] text-muted-foreground">
                DECISION DISTRIBUTION
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={decisionSeries}>
                  <XAxis dataKey="decision" tick={{ fontSize: 10, fill: "#77808e" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#77808e" }} width={28} />
                  <Bar dataKey="count" radius={0}>
                    {decisionSeries.map((entry) => (
                      <Cell key={entry.decision} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <div className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl">
              <div className="mb-4 text-[10px] tracking-[0.18em] text-muted-foreground">
                SYMBOL FREQUENCY
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={symbolCounts}>
                  <XAxis dataKey="symbol" tick={{ fontSize: 10, fill: "#77808e" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#77808e" }} width={28} />
                  <Bar dataKey="count" fill="#F5A623" radius={0} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="border border-border/80 bg-card/75 backdrop-blur-xl">
              <div className="border-b border-border/80 px-5 py-3 text-[10px] tracking-[0.18em] text-muted-foreground">
                RECENT MODEL EXPLANATIONS
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="border-b border-border/60">
                      {["TIME", "DECISION", "RISK", "LATENCY", "TOP FEATURE"].map((header) => (
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
                    {audits.slice(0, 8).map((audit, index) => (
                      <tr
                        key={`${audit.audit_id ?? audit.created_at}-${index}`}
                        className={index % 2 === 0 ? "bg-card/80" : "bg-background/35"}
                      >
                        <td className="px-5 py-2 text-muted-foreground">{formatTimestamp(audit.created_at)}</td>
                        <td className="px-5 py-2 text-foreground">{formatDecision(audit.decision)}</td>
                        <td className="px-5 py-2 text-foreground">{audit.risk_score.toFixed(4)}</td>
                        <td className="px-5 py-2 text-muted-foreground">{audit.latency_ms.toFixed(1)} ms</td>
                        <td className="px-5 py-2 text-muted-foreground">
                          {audit.top_reason ?? (audit.explanation[0]?.feature || "No explanation")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
