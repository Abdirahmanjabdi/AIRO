import { useQuery } from "@tanstack/react-query";
import { ActivitySquare, KeyRound, Radar, ShieldCheck, UsersRound } from "lucide-react";

import MetricCard from "@/components/MetricCard";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
import { sentinelApi } from "@/lib/api";
import { formatDecision, formatMode, formatTimestamp, riskTextTone } from "@/lib/presentation";

function statusTone(status: string | null): string {
  switch (status) {
    case "helm_command_prepared":
    case "ready":
      return "text-secondary border-secondary/30 bg-secondary/5";
    case "pulling_history":
    case "training":
      return "text-primary border-primary/30 bg-primary/5";
    case "failed":
      return "text-destructive border-destructive/30 bg-destructive/5";
    default:
      return "text-muted-foreground border-border bg-background/20";
  }
}

export default function Admin() {
  const overviewQuery = useQuery({
    queryKey: ["sentinel", "admin", "overview"],
    queryFn: sentinelApi.getAdminOverview,
    refetchInterval: 10000,
  });

  const overview = overviewQuery.data;

  return (
    <div className="space-y-6">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Admin"
          title="Operator control plane"
          description="Fleet-wide visibility across provisioned users, API keys, onboarding jobs, and the latest persisted audit state."
          aside={(
            <SurfacePanel className="p-4">
              <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                Fleet refresh
              </div>
              <div className="mt-2 font-display text-2xl font-bold text-foreground">
                Every 10s
              </div>
              <div className="mt-3 text-sm leading-7 text-muted-foreground">
                This pane stays tied to the backend overview endpoint instead of static operator copy.
              </div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      {overviewQuery.isLoading ? (
        <SurfacePanel className="p-8 text-sm text-muted-foreground">Loading fleet overview...</SurfacePanel>
      ) : overview ? (
        <>
          <Reveal delay={0.05}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
              <MetricCard
                label="Total users"
                value={overview.total_users}
                description="Known trader identities in the platform."
                accent="neutral"
                icon={<UsersRound size={18} />}
              />
              <MetricCard
                label="Baselines ready"
                value={overview.baseline_ready_users}
                description="Users with persisted personalized models."
                accent="secondary"
                icon={<ShieldCheck size={18} />}
              />
              <MetricCard
                label="API keys"
                value={overview.active_api_credentials}
                description="Active backend-issued credentials."
                accent="primary"
                icon={<KeyRound size={18} />}
              />
              <MetricCard
                label="Audits"
                value={overview.total_audits}
                description="Total stored decision records."
                accent="neutral"
                icon={<ActivitySquare size={18} />}
              />
              <MetricCard
                label="Blocked"
                value={overview.blocked_decisions}
                description="Block decisions across the visible fleet."
                accent="danger"
                icon={<Radar size={18} />}
              />
              <MetricCard
                label="Average risk"
                value={overview.average_risk_score.toFixed(4)}
                description="Mean fleet risk score across recent state."
                accent="primary"
                valueClassName={riskTextTone(overview.average_risk_score)}
              />
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_420px]">
              <SurfacePanel className="grid-fade">
                <div className="border-b border-border/70 px-5 py-4">
                  <div className="eyebrow-label">User fleet</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Live summary of user baselines, latest risk posture, and provisioning state.
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-border/60">
                        {[
                          "USER",
                          "BROKER",
                          "PLAN",
                          "STATUS",
                          "TRADES",
                          "RISK",
                          "DECISION",
                          "MODE",
                        ].map((header) => (
                          <th
                            key={header}
                            className="px-5 py-2 text-left text-[9px] font-normal tracking-[0.15em] text-muted-foreground"
                          >
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {overview.users.map((user, index) => (
                        <tr
                          key={user.user_id}
                          className={index % 2 === 0 ? "bg-card/30" : "bg-background/20"}
                        >
                          <td className="px-5 py-3">
                            <div className="text-foreground">{user.user_id}</div>
                            <div className="text-[10px] text-muted-foreground">
                              {user.email ?? "No email"}
                            </div>
                          </td>
                          <td className="px-5 py-3 text-muted-foreground">
                            {user.broker_server ?? "Not set"}
                          </td>
                          <td className="px-5 py-3 text-foreground">{user.plan ?? "n/a"}</td>
                          <td className="px-5 py-3">
                            <span
                              className={`inline-block border px-2 py-0.5 text-[9px] tracking-[0.12em] ${statusTone(
                                user.provisioning_state,
                              )}`}
                            >
                              {user.provisioning_state ?? "unknown"}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-foreground">{user.trade_count}</td>
                          <td className={`px-5 py-3 ${riskTextTone(user.latest_risk_score ?? 0)}`}>
                            {user.latest_risk_score?.toFixed(4) ?? "--"}
                          </td>
                          <td className="px-5 py-3 text-foreground">
                            {formatDecision(user.latest_decision)}
                          </td>
                          <td className="px-5 py-3 text-muted-foreground">
                            {formatMode(user.latest_mode)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SurfacePanel>

              <SurfacePanel accent="secondary" className="p-5">
                <div className="mb-5">
                  <div className="eyebrow-label">Recent jobs</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Latest onboarding and training activity from the fleet control plane.
                  </div>
                </div>
                <div className="max-h-[600px] space-y-3 overflow-y-auto pr-1">
                  {overview.recent_jobs.length ? (
                    overview.recent_jobs.map((job) => (
                      <div
                        key={job.job_id}
                        className="border border-border/70 bg-background/30 p-4"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-sm font-bold text-foreground">{job.user_id}</span>
                          <span
                            className={`inline-block border px-2 py-0.5 text-[9px] tracking-[0.12em] ${statusTone(
                              job.state,
                            )}`}
                          >
                            {job.state}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                          {job.message}
                        </p>
                        <div className="mt-3 grid gap-2 text-[10px] text-muted-foreground">
                          <span>Created: {formatTimestamp(job.created_at)}</span>
                          <span>Completed: {formatTimestamp(job.completed_at)}</span>
                          <span>Trades: {job.trade_count}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-muted-foreground">No onboarding jobs yet.</div>
                  )}
                </div>
              </SurfacePanel>
            </div>
          </Reveal>
        </>
      ) : (
        <SurfacePanel accent="danger" className="p-4 text-sm text-destructive">
          Unable to load the admin overview.
        </SurfacePanel>
      )}
    </div>
  );
}
