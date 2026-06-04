import { useQuery } from "@tanstack/react-query";

import { sentinelApi } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";

export function useSentinelWorkspace(identity: SentinelIdentity | null) {
  const userId = identity?.userId;

  const readinessQuery = useQuery({
    queryKey: ["sentinel", "readyz"],
    queryFn: sentinelApi.getReadiness,
    refetchInterval: 10000,
  });

  const healthQuery = useQuery({
    queryKey: ["sentinel", "healthz"],
    queryFn: sentinelApi.getHealth,
    refetchInterval: 15000,
  });

  const dashboardQuery = useQuery({
    queryKey: ["sentinel", "dashboard", userId],
    queryFn: () => sentinelApi.getDashboard(userId as string),
    enabled: Boolean(userId),
    staleTime: 5000,
    refetchInterval: 10000,
  });

  return {
    readinessQuery,
    healthQuery,
    dashboardQuery,
  };
}
