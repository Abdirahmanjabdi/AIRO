import { describe, expect, it } from "vitest";

import {
  decisionBadgeTone,
  formatDecision,
  formatMode,
  latestTopReason,
  riskStroke,
  riskTextTone,
} from "@/lib/presentation";
import type { RiskAuditRecord } from "@/lib/api";

const sampleAudit: RiskAuditRecord = {
  audit_id: 1,
  user_id: "user-1",
  symbol: "EURUSD",
  decision: "BLOCK",
  risk_score: 0.81,
  size_multiplier: 0.4,
  mode: "risk_off",
  is_anomaly: true,
  top_reason: null,
  explanation: [{ feature: "losing_streak", impact: 0.72 }],
  latency_ms: 182,
  cached: false,
  created_at: "2026-04-10T10:00:00Z",
};

describe("presentation helpers", () => {
  it("formats mode and decision labels for the dashboard", () => {
    expect(formatMode("baseline_pending")).toBe("BASELINE PENDING");
    expect(formatDecision("REDUCE_SIZE")).toBe("REDUCE SIZE");
  });

  it("returns stable tones for the major risk thresholds", () => {
    expect(riskTextTone(0.2)).toBe("text-secondary");
    expect(riskTextTone(0.5)).toBe("text-primary");
    expect(riskTextTone(0.9)).toBe("text-destructive");
    expect(riskStroke(0.2)).toBe("#4ECDC4");
    expect(riskStroke(0.5)).toBe("#F5A623");
    expect(riskStroke(0.9)).toBe("#E63946");
  });

  it("surfaces the best available explanation for the latest decision", () => {
    expect(latestTopReason(null)).toBe("No telemetry has been evaluated yet.");
    expect(latestTopReason(sampleAudit)).toBe("losing_streak");
  });

  it("maps decisions to the intended badge styles", () => {
    expect(decisionBadgeTone("ALLOW")).toContain("text-secondary");
    expect(decisionBadgeTone("REDUCE_SIZE")).toContain("text-primary");
    expect(decisionBadgeTone("BLOCK")).toContain("text-destructive");
  });
});
