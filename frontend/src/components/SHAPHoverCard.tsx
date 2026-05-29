import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { type FeatureContribution } from "@/lib/api";
import { deJargonizeFeatureName } from "@/lib/presentation";

interface SHAPHoverCardProps {
  children: React.ReactNode;
  explanation: FeatureContribution[];
  contamination?: number;
}

export default function SHAPHoverCard({ children, explanation, contamination = 0.0399 }: SHAPHoverCardProps) {
  if (!explanation || explanation.length === 0) {
    return <>{children}</>;
  }

  // Find max absolute contribution for scaling
  const maxAbs = Math.max(...explanation.map((e) => Math.abs(e.impact)), 0.01);

  return (
    <HoverCard openDelay={100} closeDelay={100}>
      <HoverCardTrigger asChild>
        <span className="cursor-help underline decoration-dashed decoration-muted-foreground/50 underline-offset-4">
          {children}
        </span>
      </HoverCardTrigger>
      <HoverCardContent side="top" align="center" className="w-72 bg-popover/95 backdrop-blur-xl border-border/80">
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-border/50 pb-2">
            <span className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-mono">
              Sentinel Telemetry Scan
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">
              Telemetry Weight
            </span>
          </div>
          <div className="space-y-2">
            {explanation.map((feature, idx) => {
              const width = Math.min(100, Math.max(2, (Math.abs(feature.impact) / maxAbs) * 100));
              const isPositive = feature.impact > 0;
              return (
                <div key={idx} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[11px] font-mono">
                    <span className="text-foreground/90 truncate mr-2">{deJargonizeFeatureName(feature.feature)}</span>
                    <span className={isPositive ? "text-danger" : "text-secondary"}>
                      {isPositive ? "+" : ""}{(feature.impact * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-muted/30 rounded-full overflow-hidden flex">
                    {!isPositive && (
                      <div className="w-1/2 flex justify-end">
                        <div 
                           className="h-full bg-secondary" 
                           style={{ width: `${width}%` }} 
                        />
                      </div>
                    )}
                    {isPositive && (
                      <div className="w-1/2 flex justify-start ml-auto">
                        <div 
                           className="h-full bg-danger" 
                           style={{ width: `${width}%` }} 
                        />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          
          <div className="pt-3 mt-2 border-t border-border/50 text-[10px] text-muted-foreground font-mono bg-background/20 p-2 rounded-sm">
            <div className="text-secondary font-bold mb-1">RISK BOUNDARY CALIBRATION</div>
            <div>Disciplinary Deviation Cap: {(contamination * 100).toFixed(2)}%</div>
            <div className="mt-1 leading-4 text-foreground/60 font-sans">
              The risk boundary is dynamically calculated against your personal baseline. If behavioral deviation spikes beyond the calibrated statistical limit, protective sizing blocks or isolation links activate immediately.
            </div>
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
