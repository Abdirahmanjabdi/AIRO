import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip
} from "recharts";
import type { RiskAuditRecord } from "@/lib/api";

interface RiskRadarChartProps {
  latestAssessment: RiskAuditRecord | null;
  riskThreshold: number;
  losingStreakBreached12h?: boolean;
}

export default function RiskRadarChart({
  latestAssessment,
  riskThreshold,
  losingStreakBreached12h = false,
}: RiskRadarChartProps) {
  const metricValue = (key: keyof RiskAuditRecord): number => {
    const value = latestAssessment?.[key];
    return typeof value === "number" && Number.isFinite(value) ? value : 0;
  };

  // Map current telemetry metrics to normalized radar dimensions (0 to 100 scale)
  const normalizedData = [
    {
      metric: "Drawdown",
      "Current Risk": Math.min(100, metricValue("drawdown_state") * 300),
      "Safe Limit": 30, // 10% drawdown threshold
    },
    {
      metric: "Losing Streak",
      "Current Risk": Math.min(100, metricValue("losing_streak") * 20),
      "Safe Limit": 60, // 3 consecutive losses
    },
    {
      metric: "Time Pressure",
      // Revenge timer: less time elapsed = higher pressure
      "Current Risk": Math.max(0, 100 - metricValue("revenge_timer") / 10),
      "Safe Limit": 50, // 500 seconds cooldown
    },
    {
      metric: "Lot Deviation",
      "Current Risk": Math.min(100, metricValue("lot_deviation") * 25),
      "Safe Limit": 50, // 2 standard deviations
    },
    {
      metric: "Vol Deviation",
      "Current Risk": Math.min(100, metricValue("realized_vol_20") * 1500),
      "Safe Limit": 40,
    }
  ];

  const primaryColor = losingStreakBreached12h ? "#DC2626" : "#CBA153";

  return (
    <div className="w-full h-[280px] bg-card/45 border border-border/80 p-5 backdrop-blur-xl flex flex-col justify-between">
      <div className="flex items-center justify-between border-b border-border/60 pb-3 mb-2">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Behavioral DNA Profile</div>
          <div className="text-xs text-foreground/80 mt-1 font-medium">Real-time risk boundary vs. baseline limit</div>
        </div>
        <span className={`text-[9px] border px-2 py-0.5 font-mono tracking-wider font-bold ${
          losingStreakBreached12h 
            ? "bg-red-500/20 border-red-500/40 text-red-500 animate-pulse" 
            : "bg-primary/20 border-primary/40 text-primary"
        }`}>
          {losingStreakBreached12h ? "RESTRICTED SCAN" : "LIVE DNA SCAN"}
        </span>
      </div>

      <div className="flex-1 min-h-0 flex items-center justify-center">
        <ResponsiveContainer width="100%" height="95%">
          <RadarChart cx="50%" cy="50%" outerRadius="80%" data={normalizedData}>
            <PolarGrid stroke="rgba(255, 255, 255, 0.08)" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: "rgba(255, 255, 255, 0.6)", fontSize: 9, fontWeight: 500, letterSpacing: "0.05em" }}
            />
            <PolarRadiusAxis
              angle={30}
              domain={[0, 100]}
              tick={{ fill: "rgba(255, 255, 255, 0.3)", fontSize: 8 }}
              axisLine={false}
            />
            <Radar
              name="Active Sizing Risk"
              dataKey="Current Risk"
              stroke={primaryColor}
              fill={primaryColor}
              fillOpacity={0.2}
              strokeWidth={1.5}
            />
            <Radar
              name="Trader Safety Baseline"
              dataKey="Safe Limit"
              stroke="#D1D5DB"
              fill="#D1D5DB"
              fillOpacity={0.1}
              strokeWidth={1}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(10, 10, 10, 0.95)",
                borderColor: "rgba(255, 255, 255, 0.15)",
                borderRadius: "8px",
                fontSize: "10px",
                fontFamily: "monospace"
              }}
              itemStyle={{ color: "#fff" }}
            />
            <Legend
              wrapperStyle={{ fontSize: "9px", letterSpacing: "0.05em", color: "rgba(255, 255, 255, 0.7)" }}
              iconSize={8}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
