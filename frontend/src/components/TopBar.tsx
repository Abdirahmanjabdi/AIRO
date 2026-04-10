import { useEffect, useState } from "react";
import { Server, ShieldCheck, ShieldOff } from "lucide-react";

import type {
  HealthResponse,
  ReadinessResponse,
  RiskAuditRecord,
} from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import { formatDecision, formatMode, riskTextTone } from "@/lib/presentation";

function LiveClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = window.setInterval(() => setTime(new Date()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <span className="tabular-nums text-[10px] tracking-[0.15em] text-muted-foreground">
      {time.toLocaleTimeString("en-GB", { hour12: false })}
      <span className="ml-0.5 text-muted-foreground/30">UTC</span>
    </span>
  );
}

interface TopBarProps {
  identity: SentinelIdentity | null;
  health?: HealthResponse;
  readiness?: ReadinessResponse;
  latestAssessment: RiskAuditRecord | null;
  onDisconnect: () => void;
}

export default function TopBar({
  identity,
  health,
  readiness,
  latestAssessment,
  onDisconnect,
}: TopBarProps) {
  const readinessLabel = readiness?.status === "ready" ? "API READY" : "API DEGRADED";

  return (
    <header
      className="fixed right-0 top-0 z-40 flex h-10 items-center justify-between border-b border-border/80 bg-card/75 px-3 backdrop-blur-xl sm:px-5"
      style={{ left: 52 }}
    >
      <div className="flex items-center gap-3 sm:gap-6">
        <LiveClock />
        <div className="hidden h-4 w-px bg-border sm:block" />
        <span className="hidden text-[10px] tracking-[0.12em] text-muted-foreground sm:inline">
          USER
          <span className="ml-2 font-mono text-foreground">
            {identity?.userId ?? "not connected"}
          </span>
        </span>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <span
          className={`hidden border px-2 py-0.5 text-[9px] tracking-[0.18em] sm:inline ${
            latestAssessment
              ? riskTextTone(latestAssessment.risk_score)
              : "text-muted-foreground"
          }`}
        >
          {latestAssessment
            ? `${formatDecision(latestAssessment.decision)} | ${formatMode(latestAssessment.mode)}`
            : "NO DECISIONS"}
        </span>

        <span
          className={`flex items-center gap-1.5 border px-2 py-0.5 text-[9px] tracking-[0.18em] ${
            readiness?.status === "ready"
              ? "border-secondary/30 text-secondary"
              : "border-primary/30 text-primary"
          }`}
        >
          {readiness?.status === "ready" ? <ShieldCheck size={12} /> : <ShieldOff size={12} />}
          {readinessLabel}
        </span>

        <span className="hidden items-center gap-1.5 text-[9px] tracking-[0.18em] text-muted-foreground md:flex">
          <Server size={12} />
          {health?.version ?? "v1.0.0"}
        </span>

        {identity ? (
          <button
            type="button"
            onClick={onDisconnect}
            className="border border-border px-2 py-0.5 text-[9px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
          >
            DISCONNECT
          </button>
        ) : null}
      </div>
    </header>
  );
}
