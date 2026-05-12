import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\CommandCenter.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add SHAPHoverCard import
import_target = """import RiskGauge from "@/components/RiskGauge";"""
import_replacement = """import RiskGauge from "@/components/RiskGauge";
import SHAPHoverCard from "@/components/SHAPHoverCard";"""
content = content.replace(import_target, import_replacement)

# 2. Add generateInsightText helper before the component
helper_target = """export default function CommandCenter({"""
helper_replacement = """function generateInsightText(audit: any, identity: string): string {
  if (!audit) return "Awaiting live telemetry to generate behavioral insights.";
  if (audit.decision === "BLOCK") {
    return `Critical intervention: ${identity} exhibited '${audit.top_reason || 'Anomaly'}' signature on ${audit.symbol}. Immediate execution block applied.`;
  }
  if (audit.decision === "REDUCE_SIZE") {
    return `Risk elevated: ${identity} showing '${audit.top_reason || 'Volatility'}' patterns on ${audit.symbol}. Scaling position down by ${((1 - audit.size_multiplier) * 100).toFixed(0)}%.`;
  }
  return `Normal operation: ${identity} is trading ${audit.symbol} within expected behavioral bounds.`;
}

export default function CommandCenter({"""
content = content.replace(helper_target, helper_replacement)

# 3. Add Insight Drawer inside the component
insight_target = """      <Reveal delay={0.05}>"""
insight_replacement = """      <Reveal delay={0.02}>
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

      <Reveal delay={0.05}>"""
content = content.replace(insight_target, insight_replacement)

# 4. Implement Adaptive Context Cards
cards_target = """        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Live risk"
            value={riskScore.toFixed(4)}
            description={latest ? latest.symbol : "No symbol scored yet"}
            accent={riskScore > (dashboard?.profile.risk_threshold ?? 0.6537) ? "danger" : riskScore > 0.4 ? "primary" : "secondary"}
            valueClassName={riskTextTone(riskScore)}
            icon={
              riskSeries.length > 1 ? (
                <MiniSparkline data={riskSeries} color={riskStroke(riskScore)} width={86} height={24} />
              ) : null
            }
          />
          <MetricCard
            label="Position gate"
            value={`${sizeMultiplier.toFixed(2)}x`}
            description="Dynamic sizing multiplier returned by the live risk engine."
            accent="primary"
            icon={<ShieldCheck size={18} />}
          />
          <MetricCard
            label="Brain mode"
            value={modeLabel}
            description={latestTopReason(latest)}
            accent="neutral"
            icon={<BrainCircuit size={18} />}
            valueClassName="text-xl text-primary"
          />
          <MetricCard
            label="Baseline"
            value={baselineLabel}
            description={`${dashboard?.profile.trade_count ?? 0} trades indexed into the current baseline.`}
            accent="secondary"
            icon={<ShieldAlert size={18} />}
            valueClassName="text-xl text-secondary"
          />
        </div>"""

cards_replacement = """        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
        </div>"""
content = content.replace(cards_target, cards_replacement)

# 5. Add SHAPHoverCard to table
table_target = """                      <td className={`px-5 py-3 ${riskTextTone(audit.risk_score)}`}>
                        {audit.risk_score.toFixed(4)}
                      </td>
                      <td className="px-5 py-3 text-foreground">{audit.size_multiplier.toFixed(2)}x</td>
                      <td className="px-5 py-3 text-muted-foreground">{formatMode(audit.mode)}</td>
                      <td className="px-5 py-3 text-muted-foreground">
                        {audit.top_reason ?? (audit.explanation[0]?.feature || "No explanation")}
                      </td>"""

table_replacement = """                      <td className={`px-5 py-3 ${riskTextTone(audit.risk_score)}`}>
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
                      </td>"""
content = content.replace(table_target, table_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("CommandCenter.tsx patched successfully!")
