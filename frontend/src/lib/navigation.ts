import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Layers,
  Settings,
  Shield,
  TrendingUp,
  UserPlus,
} from "lucide-react";

export interface WorkspaceNavItem {
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  operatorOnly?: boolean;
}

const BASE_NAV: WorkspaceNavItem[] = [
  {
    path: "/workspace",
    label: "Command",
    description: "Live portfolio protection and baseline status.",
    icon: Activity,
  },
  {
    path: "/workspace/onboarding",
    label: "Onboarding",
    description: "Vault-sealed MT5 connection and baseline training.",
    icon: UserPlus,
  },
  {
    path: "/workspace/trading",
    label: "Trading",
    description: "Decision probe and trade-context testing surface.",
    icon: TrendingUp,
  },
  {
    path: "/workspace/analytics",
    label: "Analytics",
    description: "Persisted risk analytics and audit explanations.",
    icon: BarChart3,
  },
  {
    path: "/workspace/timeline",
    label: "Timeline",
    description: "Product evolution and model-generation milestones.",
    icon: Layers,
  },
  {
    path: "/workspace/config",
    label: "Runtime",
    description: "Resolved API target and runtime configuration state.",
    icon: Settings,
  },
  {
    path: "/workspace/admin",
    label: "Admin",
    description: "Fleet-wide operator console and onboarding jobs.",
    icon: Shield,
    operatorOnly: true,
  },
];

export function getWorkspaceNav(adminEnabled: boolean): WorkspaceNavItem[] {
  if (adminEnabled) {
    return BASE_NAV;
  }

  return BASE_NAV.filter((item) => !item.operatorOnly);
}

export function getWorkspaceTitle(pathname: string): string {
  const matched = BASE_NAV.find((item) => item.path === pathname);
  if (matched) {
    return matched.label;
  }

  if (pathname.startsWith("/workspace/")) {
    return pathname.replace("/workspace/", "").replace(/-/g, " ");
  }

  return "Workspace";
}
