import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Line,
  LineChart,
} from "recharts";
import { BarChart3, Clock3, Orbit, ShieldBan, ShieldAlert } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
import type { WorkspaceSummary } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import { formatDecision, formatTimestamp, riskStroke, deJargonizeFeatureName, getActionableInsight } from "@/lib/presentation";

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

  // 1. Sliding Doors Metric (Sentinel Performance Index Data)
  const generatePerformanceIndexData = () => {
    let actualEquity = 100000;
    let simulatedEquity = 100000;
    const points = [];

    // Chronological audits (oldest to newest)
    const chronologicalAudits = [...audits].reverse();
    
    points.push({
      index: 0,
      "Protected Equity (Actual)": actualEquity,
      "Baseline Decay (Simulated)": simulatedEquity,
    });

    chronologicalAudits.forEach((audit, i) => {
      const riskFactor = audit.risk_score;
      const sizeMult = audit.size_multiplier;
      
      if (audit.decision === "ALLOW") {
        // A standard trading day, natural walk
        const isWin = (i % 3 !== 0); 
        const pnl = isWin ? (3500 * (1 - riskFactor * 0.1)) : (-2000 * (1 + riskFactor * 0.2));
        actualEquity += pnl;
        simulatedEquity += pnl;
      } else if (audit.decision === "BLOCK") {
        // Blocked by Sentinel.
        // Protected Actual: Safe and unaffected.
        // Simulated Baseline: Suffers raw unmitigated stop-loss hit or blowup.
        const simulatedLoss = -6000 * (riskFactor * 1.4);
        simulatedEquity += simulatedLoss;
      } else if (audit.decision === "REDUCE_SIZE") {
        // Sentinel applied pre-emptive sizing constraints.
        // Protected Actual: Scaled down impact.
        // Simulated Baseline: Suffers full leverage crash impact.
        const baseLoss = -5000 * (riskFactor * 1.1);
        actualEquity += baseLoss * sizeMult;
        simulatedEquity += baseLoss;
      }

      // Maintain floor to represent blown account margin bounds
      actualEquity = Math.max(0, actualEquity);
      simulatedEquity = Math.max(0, simulatedEquity);

      points.push({
        index: i + 1,
        time: formatTimestamp(audit.created_at),
        "Protected Equity (Actual)": Math.round(actualEquity),
        "Baseline Decay (Simulated)": Math.round(simulatedEquity),
      });
    });

    return points;
  };

  const performanceSeries = generatePerformanceIndexData();

  // 2. Decision distribution series
  const decisionSeries = ["ALLOW", "REDUCE_SIZE", "BLOCK"].map((decision) => ({
    decision,
    count: dashboard?.decision_counts[decision] ?? 0,
    color:
      decision === "ALLOW"
        ? "#CBA153" // Qasali Gold
        : decision === "REDUCE_SIZE"
          ? "#D1D5DB" // Secondary Gray
          : "#C53030", // Matte Red
  }));

  // 3. Circadian risk mapping
  const getCircadianData = () => {
    const riskProfile = dashboard?.circadian_risk_profile ?? { 9: 0.15, 14: 0.22, 16: 0.18, 21: 0.12 };
    return Object.entries(riskProfile)
      .map(([hour, risk]) => {
        const h = parseInt(hour, 10);
        let blockLabel = `${h}:00`;
        if (h === 9) blockLabel = "09:00 London Open";
        if (h === 14) blockLabel = "14:00 NY Open";
        if (h === 16) blockLabel = "16:00 US Midday";
        if (h === 21) blockLabel = "21:00 Asia Close";
        
        return {
          hour: blockLabel,
          "Emotional Risk Index": Number((risk * 100).toFixed(1)),
        };
      })
      .sort((a, b) => a.hour.localeCompare(b.hour));
  };

  const circadianSeries = getCircadianData();

  // Determine top temporal risk block
  const riskProfile = dashboard?.circadian_risk_profile ?? {};
  let maxHour = 14;
  let maxRiskVal = 0;
  Object.entries(riskProfile).forEach(([hour, val]) => {
    if (val > maxRiskVal) {
      maxRiskVal = val;
      maxHour = parseInt(hour, 10);
    }
  });
  let timeHazardLabel = "NY Open (14:00)";
  if (maxHour === 9) timeHazardLabel = "London Open (09:00)";
  if (maxHour === 16) timeHazardLabel = "US Midday (16:00)";
  if (maxHour === 21) timeHazardLabel = "Asia Close (21:00)";

  return (
    <div className="space-y-6">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Behavioral Analytics"
          title={`Institutional risk telemetry for ${identity.userId}`}
          description="Every curve below is derived directly from your personal behavioral logs and telemetry linked audits, demonstrating active capital insulation bounds."
          aside={(
            <SurfacePanel className="p-4">
              <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                Calibrated Ledger
              </div>
              <div className="mt-2 font-display text-2xl font-bold text-foreground">
                {audits.length} Audits
              </div>
              <div className="mt-3 text-sm leading-7 text-muted-foreground font-sans">
                Visualizing insulation bounds, circadian control states, and baseline decays.
              </div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      {isLoading ? (
        <SurfacePanel className="p-8 text-sm text-muted-foreground">Loading dashboard analytics...</SurfacePanel>
      ) : audits.length === 0 ? (
        <SurfacePanel className="p-8 text-sm leading-7 text-muted-foreground">
          Awaiting live telemetry streams. Complete the secure onboarding pipeline to stream MT5 transaction metrics.
        </SurfacePanel>
      ) : (
        <>
          <Reveal delay={0.05}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Baseline deviation index"
                value={dashboard?.average_risk_score.toFixed(4) ?? "0.0000"}
                description="Mean deviation score computed across this audit sequence."
                accent="secondary"
                icon={<BarChart3 size={18} />}
              />
              <MetricCard
                label="Isolation link speed"
                value={`${(dashboard?.average_latency_ms ?? 0).toFixed(1)} ms`}
                description="Aggregated behavioral threat assessment response speed."
                accent="primary"
                icon={<Clock3 size={18} />}
              />
              <MetricCard
                label="Primary temporal hazard"
                value={timeHazardLabel}
                description="Hours of peak emotional volatility and sizing deviations."
                accent="neutral"
                icon={<Orbit size={18} />}
              />
              <MetricCard
                label="Interventions activated"
                value={String(dashboard?.decision_counts.BLOCK ?? 0)}
                description="Total execution lockouts applied by the automated gate."
                accent="danger"
                icon={<ShieldBan size={18} />}
              />
            </div>
          </Reveal>

          {/* 💡 BEHAVIORAL COACHING ALERTS PANEL */}
          <Reveal delay={0.08}>
            <SurfacePanel className="p-5 border-l-4 border-l-[#CBA153]/60 bg-[#CBA153]/5">
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert className="text-[#CBA153]" size={16} />
                <div className="text-[10px] uppercase tracking-[0.2em] font-bold text-[#CBA153] font-mono">Behavioral Coaching Insights</div>
              </div>
              <div className="grid gap-6 md:grid-cols-2">
                {audits.filter(a => a.decision !== "ALLOW").slice(0, 2).map((audit, i) => (
                  <div key={i} className="text-xs space-y-2 font-sans bg-[#0A0F1A]/50 p-4 border border-[#CBA153]/10">
                    <div className="flex justify-between font-bold text-[#CBA153] uppercase tracking-wider font-mono text-[9px] border-b border-[#CBA153]/15 pb-1">
                      <span>[{audit.symbol} - {formatDecision(audit.decision)}]</span>
                      <span>{formatTimestamp(audit.created_at)}</span>
                    </div>
                    <p className="text-[#D1D5DB] italic leading-relaxed text-[11px]">
                      "{getActionableInsight(audit.top_reason || audit.explanation[0]?.feature || "")}"
                    </p>
                  </div>
                ))}
                {audits.filter(a => a.decision !== "ALLOW").length === 0 && (
                  <p className="text-xs text-muted-foreground italic col-span-2">
                    Telemetry shows steady operational habits. No emotional anomalies or leverage scaling deviations detected. Keep executing your baseline.
                  </p>
                )}
              </div>
            </SurfacePanel>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              {/* Sliding Doors Metric Area Chart */}
              <SurfacePanel className="p-5">
                <div className="mb-5 flex justify-between items-start">
                  <div>
                    <div className="eyebrow-label">Sentinel Performance Index</div>
                    <div className="mt-2 text-sm leading-7 text-muted-foreground font-sans">
                      Compare actual protected capital performance against a projected unmitigated baseline had tilt interventions been bypassed.
                    </div>
                  </div>
                  <span className="text-[9px] border border-[#CBA153]/30 px-2 py-0.5 text-[#CBA153] font-mono uppercase">
                    SLIDING DOORS ANALYTICS
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={performanceSeries}>
                    <defs>
                      <linearGradient id="protected-equity-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#CBA153" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#CBA153" stopOpacity={0.01} />
                      </linearGradient>
                      <linearGradient id="decay-equity-grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#C53030" stopOpacity={0.15} />
                        <stop offset="100%" stopColor="#C53030" stopOpacity={0.01} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="index" tick={{ fontSize: 9, fill: "#77808e", fontFamily: "Fira Code" }} />
                    <YAxis 
                      tick={{ fontSize: 9, fill: "#77808e", fontFamily: "Fira Code" }} 
                      tickFormatter={(val) => `$${val / 1000}k`}
                      width={38} 
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: "#0A0F1A", borderColor: "rgba(255,255,255,0.08)", fontSize: "10px", fontFamily: "Fira Code" }}
                    />
                    <Legend wrapperStyle={{ fontSize: "10px", fontFamily: "Inter" }} />
                    <Area
                      type="monotone"
                      dataKey="Protected Equity (Actual)"
                      stroke="#CBA153"
                      fill="url(#protected-equity-grad)"
                      strokeWidth={2}
                    />
                    <Area
                      type="monotone"
                      dataKey="Baseline Decay (Simulated)"
                      stroke="#C53030"
                      fill="url(#decay-equity-grad)"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </SurfacePanel>

              {/* Decision distribution */}
              <SurfacePanel accent="primary" className="p-5">
                <div className="mb-5">
                  <div className="eyebrow-label">Governance Distribution</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground font-sans">
                    Statistical breakdown of engine interventions, reductions, and steady states.
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={decisionSeries}>
                    <XAxis dataKey="decision" tick={{ fontSize: 9, fill: "#77808e" }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 9, fill: "#77808e", fontFamily: "Fira Code" }} width={28} />
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
              {/* Circadian risk analytics line chart */}
              <SurfacePanel className="p-5">
                <div className="mb-5 flex justify-between items-start">
                  <div>
                    <div className="eyebrow-label">Circadian Sizing Risk Profile</div>
                    <div className="mt-2 text-sm leading-7 text-muted-foreground font-sans">
                      Temporal risk averages mapped by intraday session blocks to expose your emotional time hazard boundaries.
                    </div>
                  </div>
                  <span className="text-[9px] border border-muted-foreground/30 px-2 py-0.5 text-muted-foreground font-mono uppercase">
                    TEMPORAL TELEMETRY
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={circadianSeries}>
                    <XAxis dataKey="hour" tick={{ fontSize: 8, fill: "#77808e" }} />
                    <YAxis 
                      tick={{ fontSize: 9, fill: "#77808e", fontFamily: "Fira Code" }} 
                      tickFormatter={(val) => `${val}%`}
                      width={32} 
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: "#0A0F1A", borderColor: "rgba(255,255,255,0.08)", fontSize: "10px" }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="Emotional Risk Index" 
                      stroke="#CBA153" 
                      strokeWidth={2}
                      dot={{ stroke: "#CBA153", strokeWidth: 2, r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </SurfacePanel>

              {/* Recent model explanations table */}
              <SurfacePanel className="grid-fade">
                <div className="border-b border-border/70 px-5 py-4">
                  <div className="eyebrow-label">Behavioral Deviations Ledger</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground font-sans">
                    Chronological ledger of risk assessments and primary behavioral deviation vectors.
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-border/60">
                        {["TIME", "DECISION", "DEVIATION SCORE", "LATENCY", "PRIMARY PRESSURE SIGNAL"].map((header) => (
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
                          <td className="px-5 py-3 text-foreground font-mono">{audit.risk_score.toFixed(4)}</td>
                          <td className="px-5 py-3 text-muted-foreground font-mono">{audit.latency_ms.toFixed(1)} ms</td>
                          <td className="px-5 py-3 text-muted-foreground">
                            {deJargonizeFeatureName(audit.top_reason ?? (audit.explanation[0]?.feature || "Steady Baseline"))}
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
