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
import { BarChart3, Clock3, Orbit, ShieldBan } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
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
      <SurfacePanel className="p-8">
        <h1 className="font-display text-2xl font-bold text-foreground">ANALYTICS</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Connect a user identity first so the charts can read from persisted risk audits.
        </p>
      </SurfacePanel>
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
    <div className="space-y-6">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Analytics"
          title={`Behavioral audit analytics for ${identity.userId}`}
          description="Every chart here is derived from persisted risk audits written by the FastAPI brain. This is product telemetry, not browser-side mock data."
          aside={(
            <SurfacePanel className="p-4">
              <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                Audit window
              </div>
              <div className="mt-2 font-display text-2xl font-bold text-foreground">
                {audits.length} records
              </div>
              <div className="mt-3 text-sm leading-7 text-muted-foreground">
                Visualizing risk, latency, symbol concentration, and recent explanations.
              </div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      {isLoading ? (
        <SurfacePanel className="p-8 text-sm text-muted-foreground">Loading analytics...</SurfacePanel>
      ) : audits.length === 0 ? (
        <SurfacePanel className="p-8 text-sm leading-7 text-muted-foreground">
          No risk audits are stored yet. Finish onboarding or use the Trading probe to generate
          real model decisions.
        </SurfacePanel>
      ) : (
        <>
          <Reveal delay={0.05}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Average risk"
                value={dashboard?.average_risk_score.toFixed(4) ?? "0.0000"}
                description="Mean score across the current audit window."
                accent="secondary"
                icon={<BarChart3 size={18} />}
              />
              <MetricCard
                label="Average latency"
                value={`${(dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`}
                description="Mean decision latency for this user."
                accent="primary"
                icon={<Clock3 size={18} />}
              />
              <MetricCard
                label="Top symbol"
                value={symbolCounts[0]?.symbol ?? "--"}
                description={`${symbolCounts[0]?.count ?? 0} audit events in the visible window.`}
                accent="neutral"
                icon={<Orbit size={18} />}
              />
              <MetricCard
                label="Blocked count"
                value={String(dashboard?.decision_counts.BLOCK ?? 0)}
                description="Number of fully blocked decisions stored for the user."
                accent="danger"
                icon={<ShieldBan size={18} />}
              />
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              <SurfacePanel className="p-5">
                <div className="mb-5">
                  <div className="eyebrow-label">Risk score over time</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Track how the latest assessments have drifted toward or away from the user’s
                    intervention threshold.
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={280}>
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
              </SurfacePanel>

              <SurfacePanel accent="primary" className="p-5">
                <div className="mb-5">
                  <div className="eyebrow-label">Decision distribution</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    See how often the engine allowed, reduced, or blocked recent activity.
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={280}>
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
              </SurfacePanel>
            </div>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
              <SurfacePanel className="p-5">
                <div className="mb-5">
                  <div className="eyebrow-label">Symbol frequency</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Concentration of recent decision volume by instrument.
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={symbolCounts}>
                    <XAxis dataKey="symbol" tick={{ fontSize: 10, fill: "#77808e" }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#77808e" }} width={28} />
                    <Bar dataKey="count" fill="#F5A623" radius={0} />
                  </BarChart>
                </ResponsiveContainer>
              </SurfacePanel>

              <SurfacePanel className="grid-fade">
                <div className="border-b border-border/70 px-5 py-4">
                  <div className="eyebrow-label">Recent model explanations</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Latest decisions with top-ranked features and inference latency.
                  </div>
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
                          className={index % 2 === 0 ? "bg-card/30" : "bg-background/20"}
                        >
                          <td className="px-5 py-3 text-muted-foreground">{formatTimestamp(audit.created_at)}</td>
                          <td className="px-5 py-3 text-foreground">{formatDecision(audit.decision)}</td>
                          <td className="px-5 py-3 text-foreground">{audit.risk_score.toFixed(4)}</td>
                          <td className="px-5 py-3 text-muted-foreground">{audit.latency_ms.toFixed(1)} ms</td>
                          <td className="px-5 py-3 text-muted-foreground">
                            {audit.top_reason ?? (audit.explanation[0]?.feature || "No explanation")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SurfacePanel>
            </div>
          </Reveal>
        </>
      )}
    </div>
  );
}
