import { Suspense, lazy, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useOutletContext,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Toaster } from "@/components/ui/sonner";
import { getApiBaseUrl } from "@/lib/api";
import { frontendEnv } from "@/lib/env";
import { getWorkspaceTitle } from "@/lib/navigation";
import { useSentinelIdentity } from "@/hooks/useSentinelIdentity";
import { useSentinelWorkspace } from "@/hooks/useSentinelWorkspace";

const Landing = lazy(() => import("@/pages/Landing"));
const CommandCenter = lazy(() => import("@/pages/CommandCenter"));
const Timeline = lazy(() => import("@/pages/Timeline"));
const Analytics = lazy(() => import("@/pages/Analytics"));
const SystemConfig = lazy(() => import("@/pages/SystemConfig"));
const Onboarding = lazy(() => import("@/pages/Onboarding"));
const Trading = lazy(() => import("@/pages/Trading"));
const Admin = lazy(() => import("@/pages/Admin"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

interface WorkspaceContextValue {
  identity: ReturnType<typeof useSentinelIdentity>["identity"];
  setIdentity: ReturnType<typeof useSentinelIdentity>["setIdentity"];
  clearIdentity: ReturnType<typeof useSentinelIdentity>["clearIdentity"];
  readinessQuery: ReturnType<typeof useSentinelWorkspace>["readinessQuery"];
  healthQuery: ReturnType<typeof useSentinelWorkspace>["healthQuery"];
  dashboardQuery: ReturnType<typeof useSentinelWorkspace>["dashboardQuery"];
}

function useWorkspaceContext() {
  return useOutletContext<WorkspaceContextValue>();
}

function WorkspaceShell() {
  const { identity, setIdentity, clearIdentity } = useSentinelIdentity();
  const { readinessQuery, healthQuery, dashboardQuery } = useSentinelWorkspace(identity);
  const dashboard = dashboardQuery.data ?? null;
  const location = useLocation();
  const pageTitle = getWorkspaceTitle(location.pathname);
  const [navigationOpen, setNavigationOpen] = useState(false);

  const context: WorkspaceContextValue = {
    identity,
    setIdentity,
    clearIdentity,
    readinessQuery,
    healthQuery,
    dashboardQuery,
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="hidden h-screen lg:sticky lg:top-0 lg:block">
        <Sidebar />
      </aside>

      <Sheet open={navigationOpen} onOpenChange={setNavigationOpen}>
        <SheetContent
          side="left"
          className="w-[92vw] max-w-[340px] border-border/80 bg-background p-0"
        >
          <Sidebar className="border-r-0" onNavigate={() => setNavigationOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="min-w-0">
        <TopBar
          title={pageTitle}
          identity={identity}
          health={healthQuery.data}
          readiness={readinessQuery.data}
          latestAssessment={dashboard?.latest_assessment ?? null}
          onMenuToggle={() => setNavigationOpen(true)}
          onDisconnect={clearIdentity}
        />

        <main className="px-4 py-5 sm:px-6 lg:px-8">
          {readinessQuery.data?.status !== "ready" ? (
            <div className="mb-4 border border-primary/25 bg-primary/10 px-4 py-3 text-sm leading-7 text-muted-foreground">
              The control plane is reachable, but readiness is degraded. Some pages may be waiting
              on Redis, Postgres, or model loading before they become fully live.
            </div>
          ) : null}

          <Suspense fallback={<RouteSkeleton />}>
            <Outlet context={context} />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

function CommandCenterRoute() {
  const { identity, dashboardQuery, readinessQuery } = useWorkspaceContext();

  return (
    <CommandCenter
      identity={identity}
      dashboard={dashboardQuery.data ?? null}
      readiness={readinessQuery.data ?? null}
      isLoading={dashboardQuery.isLoading}
      onRefresh={() => {
        void dashboardQuery.refetch();
        void readinessQuery.refetch();
      }}
    />
  );
}

function AnalyticsRoute() {
  const { identity, dashboardQuery } = useWorkspaceContext();

  return (
    <Analytics
      identity={identity}
      dashboard={dashboardQuery.data ?? null}
      isLoading={dashboardQuery.isLoading}
    />
  );
}

function RuntimeRoute() {
  const { identity, dashboardQuery, readinessQuery } = useWorkspaceContext();

  return (
    <SystemConfig
      identity={identity}
      dashboard={dashboardQuery.data ?? null}
      readiness={readinessQuery.data ?? null}
      apiBaseUrl={getApiBaseUrl()}
    />
  );
}

function OnboardingRoute() {
  const { identity, setIdentity } = useWorkspaceContext();

  return (
    <Onboarding
      identity={identity}
      onConnected={(nextIdentity) => {
        setIdentity(nextIdentity);
      }}
    />
  );
}

function TradingRoute() {
  const { identity, dashboardQuery } = useWorkspaceContext();

  return <Trading identity={identity} dashboard={dashboardQuery.data ?? null} />;
}

function RouteTree() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/workspace" element={<WorkspaceShell />}>
        <Route index element={<CommandCenterRoute />} />
        <Route path="onboarding" element={<OnboardingRoute />} />
        <Route path="trading" element={<TradingRoute />} />
        <Route path="analytics" element={<AnalyticsRoute />} />
        <Route path="timeline" element={<Timeline />} />
        <Route path="config" element={<RuntimeRoute />} />
        {frontendEnv.adminEnabled ? <Route path="admin" element={<Admin />} /> : null}
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="/onboarding" element={<Navigate to="/workspace/onboarding" replace />} />
      <Route path="/trading" element={<Navigate to="/workspace/trading" replace />} />
      <Route path="/analytics" element={<Navigate to="/workspace/analytics" replace />} />
      <Route path="/timeline" element={<Navigate to="/workspace/timeline" replace />} />
      <Route path="/config" element={<Navigate to="/workspace/config" replace />} />
      <Route
        path="/admin"
        element={<Navigate to={frontendEnv.adminEnabled ? "/workspace/admin" : "/workspace"} replace />}
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
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
        <Suspense fallback={<RouteSkeleton />}>
          <RouteTree />
        </Suspense>
        <Toaster position="top-right" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
