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
    return audit.top_reason;
  }
  if (audit.explanation.length > 0) {
    return audit.explanation[0].feature;
  }
  return "Model completed a decision without a ranked explanation.";
}
