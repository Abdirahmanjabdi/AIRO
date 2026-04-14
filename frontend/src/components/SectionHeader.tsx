import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  aside?: ReactNode;
  className?: string;
}

export default function SectionHeader({
  eyebrow,
  title,
  description,
  aside,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between", className)}>
      <div className="max-w-3xl">
        {eyebrow ? <div className="eyebrow-label">{eyebrow}</div> : null}
        <h1 className="mt-3 font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          {title}
        </h1>
        {description ? (
          <div className="mt-3 text-sm leading-8 text-muted-foreground sm:text-base">
            {description}
          </div>
        ) : null}
      </div>
      {aside ? <div className="lg:min-w-[280px]">{aside}</div> : null}
    </div>
  );
}
