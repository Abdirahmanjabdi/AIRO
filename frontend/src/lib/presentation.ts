import type { Decision, RiskAuditRecord, RiskMode } from "@/lib/api";

export function formatMode(mode: RiskMode | null | undefined): string {
  if (!mode) {
    return "UNKNOWN";
  }
  return mode.replace(/_/g, " ").toUpperCase();
}

export function formatDecision(decision: Decision | null | undefined): string {
  if (!decision) {
    return "NO SIGNAL";
  }
  return decision.replace(/_/g, " ");
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Pending";
  }

  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatClock(value: string | null | undefined): string {
  if (!value) {
    return "--:--:--";
  }

  return new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function riskTextTone(score: number): string {
  if (score < 0.4) {
    return "text-secondary";
  }
  if (score < 0.6537) {
    return "text-primary";
  }
  return "text-destructive";
}

export function riskStroke(score: number): string {
  if (score < 0.4) {
    return "#4ECDC4";
  }
  if (score < 0.6537) {
    return "#F5A623";
  }
  return "#E63946";
}

export function decisionBadgeTone(decision: Decision | null | undefined): string {
  switch (decision) {
    case "ALLOW":
      return "text-secondary border-secondary/30 bg-secondary/5";
    case "REDUCE_SIZE":
      return "text-primary border-primary/30 bg-primary/5";
    case "BLOCK":
      return "text-destructive border-destructive/30 bg-destructive/5";
    default:
      return "text-muted-foreground border-border bg-background";
  }
}

export function latestTopReason(audit: RiskAuditRecord | null | undefined): string {
  if (!audit) {
    return "No telemetry has been evaluated yet.";
  }
  if (audit.top_reason) {
    return deJargonizeFeatureName(audit.top_reason);
  }
  if (audit.explanation.length > 0) {
    return deJargonizeFeatureName(audit.explanation[0].feature);
  }
  return "Model completed a decision without a ranked explanation.";
}

export function deJargonizeFeatureName(feature: string): string {
  const f = feature.toLowerCase();
  if (f.includes("revenge") || f.includes("timer")) return "Re-entry Urgency";
  if (f.includes("lot_deviation")) return "Leverage Scaling Deviation";
  if (f.includes("drawdown")) return "Session Drawdown Rate";
  if (f.includes("streak") || f.includes("loss")) return "Consecutive Loss Streak";
  if (f.includes("vol") || f.includes("volatility")) return "Local Market Volatility";
  if (f.includes("trend") || f.includes("momentum")) return "Counter-trend Risk Index";
  if (f.includes("rr_ratio") || f.includes("reward")) return "Risk-to-Reward Efficiency";
  if (f.includes("lots")) return "Position Sizing Magnitude";
  if (f.includes("hour") || f.includes("time")) return "Intraday Session Block Hazard";
  return feature.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function getActionableInsight(feature: string): string {
  const f = feature.toLowerCase();
  if (f.includes("revenge") || f.includes("timer")) {
    return "You are executing orders too quickly following a losing trade. Step away for 15 minutes to allow session volatility to normalize.";
  }
  if (f.includes("lot_deviation") || f.includes("lot") || f.includes("size")) {
    return "Outsized leverage anomaly detected relative to your 30-day baseline distribution.";
  }
  if (f.includes("drawdown") || f.includes("state")) {
    return "Intraday loss velocity is reaching historical hazard limits. Consider scaling down size temporarily.";
  }
  if (f.includes("streak") || f.includes("loss")) {
    return "Loss streak momentum detected. Behavioral baseline suggests taking a 30-minute break.";
  }
  if (f.includes("vol") || f.includes("volatility")) {
    return "Trading during elevated local market volatility. Sizing adjustments are recommended to preserve margin.";
  }
  return "Execution aligned with standard historical baseline bounds. Maintain steady disciplined execution.";
}
