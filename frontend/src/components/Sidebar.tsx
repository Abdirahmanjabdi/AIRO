import { Link, useLocation } from "react-router-dom";
import { ArrowUpRight, ChevronRight } from "lucide-react";

import BrandMark from "@/components/BrandMark";
import { frontendEnv } from "@/lib/env";
import { getWorkspaceNav } from "@/lib/navigation";
import { cn } from "@/lib/utils";

interface SidebarProps {
  className?: string;
  onNavigate?: () => void;
}

export default function Sidebar({ className, onNavigate }: SidebarProps) {
  const location = useLocation();
  const navigation = getWorkspaceNav(frontendEnv.adminEnabled);

  return (
    <nav className={cn("flex h-full flex-col border-r border-border/80 bg-card/80 backdrop-blur-2xl", className)}>
      <div className="border-b border-border/80 px-4 py-5">
        <BrandMark />
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-5">
        <div className="mb-3 px-3 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Workspace
        </div>

        <div className="space-y-1">
          {navigation.map((item) => {
            const active = location.pathname === item.path;
            const Icon = item.icon;

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onNavigate}
                className={cn(
                  "group flex items-center gap-3 border px-3 py-3 transition-all duration-150",
                  active
                    ? "border-secondary/35 bg-secondary/10 text-secondary"
                    : "border-transparent text-muted-foreground hover:border-border/70 hover:bg-background/45 hover:text-foreground",
                )}
              >
                <Icon size={18} />
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-bold uppercase tracking-[0.16em]">
                    {item.label}
                  </div>
                  <div className="mt-1 text-[11px] leading-5 text-muted-foreground group-hover:text-muted-foreground">
                    {item.description}
                  </div>
                </div>
                <ChevronRight size={14} className={active ? "text-secondary" : "text-muted-foreground/60"} />
              </Link>
            );
          })}
        </div>
      </div>

      <div className="space-y-3 border-t border-border/80 px-4 py-5">
        <Link
          to="/"
          onClick={onNavigate}
          className="flex items-center justify-between border border-border/70 bg-background/35 px-3 py-3 text-sm text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
        >
          <span>Back to landing page</span>
          <ArrowUpRight size={15} />
        </Link>

        <div className="border border-border/70 bg-background/35 px-3 py-3">
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Runtime profile
          </div>
          <div className="mt-2 text-sm leading-6 text-muted-foreground">
            Production shell for onboarding, analytics, and live operator monitoring.
          </div>
        </div>
      </div>
    </nav>
  );
}
