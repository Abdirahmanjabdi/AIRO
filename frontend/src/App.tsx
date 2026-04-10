import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Suspense, lazy } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { getApiBaseUrl } from "@/lib/api";
import { useSentinelIdentity } from "@/hooks/useSentinelIdentity";
import { useSentinelWorkspace } from "@/hooks/useSentinelWorkspace";

const CommandCenter = lazy(() => import("@/pages/CommandCenter"));
const Timeline = lazy(() => import("@/pages/Timeline"));
const Analytics = lazy(() => import("@/pages/Analytics"));
const SystemConfig = lazy(() => import("@/pages/SystemConfig"));
const Onboarding = lazy(() => import("@/pages/Onboarding"));
const Trading = lazy(() => import("@/pages/Trading"));
const Admin = lazy(() => import("@/pages/Admin"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
    },
  },
});

function DashboardShell() {
  const { identity, setIdentity, clearIdentity } = useSentinelIdentity();
  const { readinessQuery, healthQuery, dashboardQuery } = useSentinelWorkspace(identity);
  const dashboard = dashboardQuery.data ?? null;

  return (
    <div className="min-h-screen">
      <Sidebar />
      <TopBar
        identity={identity}
        health={healthQuery.data}
        readiness={readinessQuery.data}
        latestAssessment={dashboard?.latest_assessment ?? null}
        onDisconnect={clearIdentity}
      />
      <main className="ml-[52px] mt-10 px-3 py-4 sm:px-4 lg:px-6">
        <Suspense fallback={<RouteSkeleton />}>
          <Routes>
            <Route
              path="/"
              element={
                <CommandCenter
                  identity={identity}
                  dashboard={dashboard}
                  readiness={readinessQuery.data ?? null}
                  isLoading={dashboardQuery.isLoading}
                  onRefresh={() => {
                    void dashboardQuery.refetch();
                    void readinessQuery.refetch();
                  }}
                />
              }
            />
            <Route path="/timeline" element={<Timeline />} />
            <Route
              path="/analytics"
              element={
                <Analytics
                  identity={identity}
                  dashboard={dashboard}
                  isLoading={dashboardQuery.isLoading}
                />
              }
            />
            <Route
              path="/config"
              element={
                <SystemConfig
                  identity={identity}
                  dashboard={dashboard}
                  readiness={readinessQuery.data ?? null}
                  apiBaseUrl={getApiBaseUrl()}
                />
              }
            />
            <Route
              path="/onboarding"
              element={
                <Onboarding
                  identity={identity}
                  onConnected={(nextIdentity) => {
                    setIdentity(nextIdentity);
                  }}
                />
              }
            />
            <Route
              path="/trading"
              element={
                <Trading
                  identity={identity}
                  dashboard={dashboard}
                />
              }
            />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

function RouteSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="h-32 rounded-3xl border border-white/10 bg-white/5 backdrop-blur-md animate-pulse" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-64 rounded-3xl border border-white/10 bg-white/5 backdrop-blur-md animate-pulse" />
        <div className="h-64 rounded-3xl border border-white/10 bg-white/5 backdrop-blur-md animate-pulse" />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DashboardShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
