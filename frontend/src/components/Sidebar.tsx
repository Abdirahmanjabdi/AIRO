import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Layers,
  Settings,
  Shield,
  TrendingUp,
  UserPlus,
} from "lucide-react";

const NAV_MAIN = [
  { path: "/", icon: Activity, label: "COMMAND" },
  { path: "/trading", icon: TrendingUp, label: "TRADING" },
  { path: "/analytics", icon: BarChart3, label: "ANALYTICS" },
  { path: "/timeline", icon: Layers, label: "TIMELINE" },
  { path: "/config", icon: Settings, label: "CONFIG" },
];

const NAV_SENTINEL = [
  { path: "/onboarding", icon: UserPlus, label: "ONBOARD" },
  { path: "/admin", icon: Shield, label: "ADMIN" },
];

export default function Sidebar() {
  const [expanded, setExpanded] = useState(false);
  const location = useLocation();

  return (
    <nav
      className="fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-border/80 bg-card/80 backdrop-blur-xl transition-all duration-200"
      style={{ width: expanded ? 200 : 52 }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <div className="flex h-10 items-center justify-center border-b border-border/80">
        <span className="font-display text-xs font-bold tracking-[0.3em] text-secondary">
          {expanded ? "SENTINEL" : "SZ"}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-0.5 px-1.5 py-4">
        {NAV_MAIN.map((item) => {
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`relative flex h-9 items-center gap-3 px-3 text-[10px] tracking-[0.15em] transition-all duration-150 ${
                active ? "text-secondary" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {active ? (
                <div
                  className="absolute bottom-1 left-0 top-1 w-[2px] bg-secondary"
                  style={{ boxShadow: "0 0 10px rgba(78, 205, 196, 0.4)" }}
                />
              ) : null}
              <item.icon size={15} strokeWidth={1.5} />
              {expanded ? <span className="whitespace-nowrap">{item.label}</span> : null}
            </Link>
          );
        })}

        <div className="mx-3 my-2 border-t border-border/50" />
        {expanded ? (
          <span className="mb-1 px-3 text-[7px] tracking-[0.2em] text-muted-foreground/40">
            CONTROL
          </span>
        ) : null}

        {NAV_SENTINEL.map((item) => {
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`relative flex h-9 items-center gap-3 px-3 text-[10px] tracking-[0.15em] transition-all duration-150 ${
                active ? "text-primary" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {active ? (
                <div
                  className="absolute bottom-1 left-0 top-1 w-[2px] bg-primary"
                  style={{ boxShadow: "0 0 10px rgba(245, 166, 35, 0.35)" }}
                />
              ) : null}
              <item.icon size={15} strokeWidth={1.5} />
              {expanded ? <span className="whitespace-nowrap">{item.label}</span> : null}
            </Link>
          );
        })}
      </div>

      <div className="px-3 pb-3 text-center">
        <span className="text-[8px] tracking-widest text-muted-foreground/50">ZERO V1</span>
      </div>
    </nav>
  );
}
