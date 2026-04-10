import { useQuery } from "@tanstack/react-query";

import { sentinelApi } from "@/lib/api";
import { formatDecision, formatMode, formatTimestamp, riskTextTone } from "@/lib/presentation";

function statusTone(status: string | null): string {
  switch (status) {
    case "helm_command_prepared":
    case "ready":
      return "text-secondary border-secondary/30";
    case "pulling_history":
    case "training":
      return "text-primary border-primary/30";
    case "failed":
      return "text-destructive border-destructive/30";
    default:
      return "text-muted-foreground border-border";
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
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
          ADMIN CONTROL PLANE
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Fleet-wide visibility across provisioned users, API keys, onboarding jobs, and the
          latest persisted audit state.
        </p>
      </div>

      {overviewQuery.isLoading ? (
        <div className="border border-border/80 bg-card/75 p-8 text-sm text-muted-foreground backdrop-blur-xl">
          Loading fleet overview...
        </div>
      ) : overview ? (
        <>
          <div className="grid gap-px bg-border md:grid-cols-2 xl:grid-cols-6">
            {[
              { label: "TOTAL USERS", value: overview.total_users, accent: "text-foreground" },
              {
                label: "BASELINES READY",
                value: overview.baseline_ready_users,
                accent: "text-secondary",
              },
              {
                label: "API KEYS",
                value: overview.active_api_credentials,
                accent: "text-primary",
              },
              { label: "AUDITS", value: overview.total_audits, accent: "text-foreground" },
              {
                label: "BLOCKED",
                value: overview.blocked_decisions,
                accent: "text-destructive",
              },
              {
                label: "AVG RISK",
                value: overview.average_risk_score.toFixed(4),
                accent: riskTextTone(overview.average_risk_score),
              },
            ].map((item) => (
              <div key={item.label} className="bg-card/80 px-4 py-4 backdrop-blur-xl">
                <div className="mb-2 text-[8px] tracking-[0.15em] text-muted-foreground">
                  {item.label}
                </div>
                <div className={`text-lg font-bold ${item.accent}`}>{item.value}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_420px]">
            <div className="border border-border/80 bg-card/75 backdrop-blur-xl">
              <div className="border-b border-border/80 px-5 py-3 text-[10px] tracking-[0.18em] text-muted-foreground">
                USER FLEET
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
                        className={index % 2 === 0 ? "bg-card/80" : "bg-background/35"}
                      >
                        <td className="px-5 py-2">
                          <div className="text-foreground">{user.user_id}</div>
                          <div className="text-[10px] text-muted-foreground">
                            {user.email ?? "No email"}
                          </div>
                        </td>
                        <td className="px-5 py-2 text-muted-foreground">
                          {user.broker_server ?? "Not set"}
                        </td>
                        <td className="px-5 py-2 text-foreground">{user.plan ?? "n/a"}</td>
                        <td className="px-5 py-2">
                          <span
                            className={`inline-block border px-2 py-0.5 text-[9px] tracking-[0.12em] ${statusTone(
                              user.provisioning_state,
                            )}`}
                          >
                            {user.provisioning_state ?? "unknown"}
                          </span>
                        </td>
                        <td className="px-5 py-2 text-foreground">{user.trade_count}</td>
                        <td className={`px-5 py-2 ${riskTextTone(user.latest_risk_score ?? 0)}`}>
                          {user.latest_risk_score?.toFixed(4) ?? "--"}
                        </td>
                        <td className="px-5 py-2 text-foreground">
                          {formatDecision(user.latest_decision)}
                        </td>
                        <td className="px-5 py-2 text-muted-foreground">
                          {formatMode(user.latest_mode)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="border border-border/80 bg-card/75 backdrop-blur-xl">
              <div className="border-b border-border/80 px-5 py-3 text-[10px] tracking-[0.18em] text-muted-foreground">
                RECENT JOBS
              </div>
              <div className="max-h-[520px] overflow-y-auto p-4">
                {overview.recent_jobs.length ? (
                  <div className="space-y-3">
                    {overview.recent_jobs.map((job) => (
                      <div
                        key={job.job_id}
                        className="border border-border/80 bg-background/35 p-4"
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
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">No onboarding jobs yet.</div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          Unable to load the admin overview.
        </div>
      )}
    </div>
  );
}
