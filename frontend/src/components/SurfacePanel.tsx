import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SurfacePanelProps extends HTMLAttributes<HTMLDivElement> {
  accent?: "neutral" | "primary" | "secondary" | "danger";
  children: ReactNode;
}

const accentClassMap: Record<NonNullable<SurfacePanelProps["accent"]>, string> = {
  neutral: "surface-panel",
  primary: "surface-panel surface-panel-primary",
  secondary: "surface-panel surface-panel-secondary",
  danger: "surface-panel surface-panel-danger",
};

export default function SurfacePanel({
  accent = "neutral",
  className,
  children,
  ...props
}: SurfacePanelProps) {
  return (
    <div className={cn(accentClassMap[accent], className)} {...props}>
      {children}
    </div>
  );
}
