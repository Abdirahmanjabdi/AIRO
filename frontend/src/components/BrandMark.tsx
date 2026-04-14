import { ShieldHalf } from "lucide-react";

import { cn } from "@/lib/utils";

interface BrandMarkProps {
  compact?: boolean;
  className?: string;
}

export default function BrandMark({ compact = false, className }: BrandMarkProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="relative flex h-11 w-11 items-center justify-center border border-secondary/30 bg-secondary/10 text-secondary shadow-[0_0_32px_rgba(78,205,196,0.12)]">
        <ShieldHalf size={18} />
        <div className="absolute inset-[6px] border border-secondary/20" />
      </div>
      {!compact ? (
        <div className="min-w-0">
          <div className="font-display text-sm font-bold uppercase tracking-[0.28em] text-foreground">
            Sentinel Zero
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Identity-first trade protection
          </div>
        </div>
      ) : null}
    </div>
  );
}
