import type { ReactNode } from "react";

import SurfacePanel from "@/components/SurfacePanel";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  accent?: "neutral" | "primary" | "secondary" | "danger";
  className?: string;
  valueClassName?: string;
}

export default function MetricCard({
  label,
  value,
  description,
  icon,
  accent = "neutral",
  className,
  valueClassName,
}: MetricCardProps) {
  return (
    <SurfacePanel accent={accent} className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
        {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      </div>
      <div className={cn("mt-4 font-display text-3xl font-bold text-foreground", valueClassName)}>
        {value}
      </div>
      {description ? (
        <div className="mt-3 text-sm leading-7 text-muted-foreground">{description}</div>
      ) : null}
    </SurfacePanel>
  );
}
