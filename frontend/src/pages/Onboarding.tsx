import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, LockKeyhole, Radar, ServerCog, Shield } from "lucide-react";

import { sentinelApi, type OnboardingState } from "@/lib/api";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";

type Stage = "IDLE" | "VAULT" | "PROVISIONING" | "SYNC" | "AUDIT" | "LIVE";

const STEPS: Array<{
  key: Exclude<Stage, "IDLE" | "LIVE">;
  label: string;
  description: string;
  icon: typeof LockKeyhole;
}> = [
  {
    key: "VAULT",
    label: "VAULT",
    description: "Encrypt broker credentials before they ever touch persistence.",
    icon: LockKeyhole,
  },
  {
    key: "PROVISIONING",
    label: "PROVISIONING",
    description: "Queue the onboarding job and hand it to the MT5 bridge.",
    icon: ServerCog,
  },
  {
    key: "SYNC",
    label: "SYNCING HISTORY",
    description: "Verify the broker session and pull the latest deal history.",
    icon: Radar,
  },
  {
    key: "AUDIT",
    label: "AUDITING",
    description: "Train the personalized baseline and persist the model artifact.",
    icon: Shield,
  },
];

function mapOnboardingState(state: OnboardingState): Stage {
  switch (state) {
    case "pending":
      return "PROVISIONING";
    case "pulling_history":
      return "SYNC";
    case "training":
    case "blank_baseline":
      return "AUDIT";
    case "ready":
      return "LIVE";
    case "failed":
      return "PROVISIONING";
    default:
      return "IDLE";
  }
}

interface OnboardingProps {
  identity: SentinelIdentity | null;
  onConnected: (identity: SentinelIdentity) => void;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function Onboarding({ identity, onConnected }: OnboardingProps) {
  const navigate = useNavigate();
  const [userId, setUserId] = useState(identity?.userId ?? "");
  const [brokerServer, setBrokerServer] = useState(identity?.brokerServer ?? "");
  const [accountId, setAccountId] = useState(identity?.accountId ?? "");
  const [readOnlyPassword, setReadOnlyPassword] = useState("");
  const [stage, setStage] = useState<Stage>("IDLE");
  const [jobId, setJobId] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState(
    "Secure the MT5 bridge, verify history, and train a private baseline.",
  );
  const [logs, setLogs] = useState<string[]>([]);
  const [completionState, setCompletionState] = useState<"ready" | "blank_baseline" | null>(null);

  useEffect(() => {
    if (!identity) {
      return;
    }

    setUserId(identity.userId);
    setBrokerServer(identity.brokerServer);
    setAccountId(identity.accountId);
  }, [identity]);

  function appendLog(message: string) {
    setLogs((previous) => {
      if (previous[previous.length - 1] === message) {
        return previous;
      }
      return [...previous, message];
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setError(null);
    setCompletionState(null);
    setLogs([]);
    setJobId(null);

    try {
      setStage("VAULT");
      setStatusMessage("Encrypting broker credentials through Vault transit.");
      appendLog("> Sealing MT5 read-only credentials in Vault transit.");

      const credentialResponse = await sentinelApi.storeCredentials({
        user_id: userId,
        broker_server: brokerServer,
        account_id: accountId,
        read_only_password: readOnlyPassword,
      });

      appendLog(`> Vault path confirmed: ${credentialResponse.vault_path}`);

      setStage("PROVISIONING");
      setStatusMessage("Dispatching onboarding to the MT5 bridge.");
      appendLog("> Queueing personalized onboarding job.");

      const onboarding = await sentinelApi.startOnboarding({
        user_id: userId,
        broker_server: brokerServer,
        account_id: accountId,
      });

      setJobId(onboarding.job_id);
      appendLog(`> Job accepted: ${onboarding.job_id}`);
      appendLog(`> ${onboarding.message}`);

      for (let attempt = 0; attempt < 90; attempt += 1) {
        await sleep(attempt === 0 ? 400 : 2000);

        const status = await sentinelApi.getOnboardingStatus(onboarding.job_id);
        setStage(mapOnboardingState(status.state));
        setStatusMessage(status.message);
        appendLog(`> ${status.message}`);

        if (status.state === "ready") {
          onConnected({ userId, brokerServer, accountId });
          setCompletionState("ready");
          setStage("LIVE");
          setIsBusy(false);
          return;
        }

        if (status.state === "blank_baseline") {
          onConnected({ userId, brokerServer, accountId });
          setCompletionState("blank_baseline");
          setStage("LIVE");
          setIsBusy(false);
          appendLog("> Blank baseline recorded. Monitoring can start while more history accumulates.");
          return;
        }

        if (status.state === "failed") {
          throw new Error(status.message);
        }
      }

      throw new Error("Timed out waiting for MT5 history and model training.");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Unknown onboarding error.",
      );
      setStage("IDLE");
      setStatusMessage("Secure the MT5 bridge, verify history, and train a private baseline.");
      setIsBusy(false);
    }
  }

  const currentStepIndex = STEPS.findIndex((stepItem) => stepItem.key === stage);

  return (
    <div className="mx-auto max-w-5xl py-4 sm:py-8">
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold tracking-wide text-foreground">
          SENTINEL ONBOARDING
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          This flow stores the read-only MT5 password in Vault, queues the MT5 bridge,
          pulls broker history, and trains an identity-bound baseline.
        </p>
      </div>

      <div className="mb-8 grid gap-3 border border-border/80 bg-card/75 p-3 backdrop-blur-xl md:grid-cols-4">
        {STEPS.map((stepItem, index) => {
          const isComplete =
            stage === "LIVE" || (currentStepIndex >= 0 && index < currentStepIndex);
          const isActive = stepItem.key === stage;
          const Icon = isComplete ? CheckCircle2 : stepItem.icon;

          return (
            <div
              key={stepItem.key}
              className={`rounded-none border p-3 transition-colors ${
                isActive
                  ? "border-primary/60 bg-primary/10"
                  : isComplete
                    ? "border-secondary/40 bg-secondary/5"
                    : "border-border/80 bg-background/40"
              }`}
            >
              <div className="mb-3 flex items-center gap-2">
                <Icon
                  size={16}
                  className={
                    isComplete
                      ? "text-secondary"
                      : isActive
                        ? "text-primary"
                        : "text-muted-foreground"
                  }
                />
                <span
                  className={`text-[11px] font-bold tracking-[0.18em] ${
                    isComplete
                      ? "text-secondary"
                      : isActive
                        ? "text-primary"
                        : "text-muted-foreground"
                  }`}
                >
                  {stepItem.label}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {stepItem.description}
              </p>
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl sm:p-6">
          {completionState ? (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="text-secondary" size={20} />
                <div>
                  <h2 className="font-display text-xl font-bold text-foreground">
                    {completionState === "ready"
                      ? "Baseline Ready"
                      : "Blank Baseline Created"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {completionState === "ready"
                      ? "The model is persisted and the command center is ready for live telemetry."
                      : "The account has no broker history yet, so Sentinel will stay baseline-pending until more trades arrive."}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 border border-border/80 bg-background/40 p-4 sm:grid-cols-3">
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    USER ID
                  </span>
                  <span className="text-sm font-bold text-foreground">{userId}</span>
                </div>
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    SERVER
                  </span>
                  <span className="text-sm font-bold text-foreground">{brokerServer}</span>
                </div>
                <div>
                  <span className="block text-[10px] tracking-[0.15em] text-muted-foreground">
                    ACCOUNT
                  </span>
                  <span className="text-sm font-bold text-foreground">{accountId}</span>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={() => navigate("/")}
                  className="border border-secondary/40 bg-secondary/10 px-4 py-3 text-[11px] font-bold tracking-[0.18em] text-secondary transition-colors hover:bg-secondary/20"
                >
                  OPEN COMMAND CENTER
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCompletionState(null);
                    setReadOnlyPassword("");
                    setLogs([]);
                    setStatusMessage(
                      "Secure the MT5 bridge, verify history, and train a private baseline.",
                    );
                    setStage("IDLE");
                  }}
                  className="border border-border px-4 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  RUN AGAIN
                </button>
              </div>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmit}>
              <div>
                <h2 className="font-display text-lg font-bold tracking-wide text-foreground">
                  Secure the Broker Link
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  The password is stored only in Vault. Postgres receives metadata and job
                  state, never the secret itself.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground">
                    USER ID
                  </label>
                  <input
                    type="text"
                    value={userId}
                    onChange={(event) => setUserId(event.target.value)}
                    required
                    className="h-10 w-full border border-border bg-background/70 px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                    placeholder="whop-user-001"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground">
                    BROKER SERVER
                  </label>
                  <input
                    type="text"
                    value={brokerServer}
                    onChange={(event) => setBrokerServer(event.target.value)}
                    required
                    className="h-10 w-full border border-border bg-background/70 px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                    placeholder="ICMarkets-Demo"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground">
                    ACCOUNT ID
                  </label>
                  <input
                    type="text"
                    value={accountId}
                    onChange={(event) => setAccountId(event.target.value)}
                    required
                    className="h-10 w-full border border-border bg-background/70 px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                    placeholder="12345678"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground">
                    READ-ONLY PASSWORD
                  </label>
                  <input
                    type="password"
                    value={readOnlyPassword}
                    onChange={(event) => setReadOnlyPassword(event.target.value)}
                    required
                    className="h-10 w-full border border-border bg-background/70 px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                    placeholder="Stored through Vault transit"
                  />
                </div>
              </div>

              <div className="border border-border/80 bg-background/40 p-4 text-sm text-muted-foreground">
                <div className="mb-2 flex items-center gap-2 text-secondary">
                  <Shield size={16} />
                  <span className="text-[11px] font-bold tracking-[0.18em]">
                    ZERO-TRUST STORAGE
                  </span>
                </div>
                Credentials move from the browser to Vault and from Vault to the bridge. They
                are not stored in plain text in Postgres, Redis, or audit logs.
              </div>

              {error ? (
                <div className="border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={
                  isBusy ||
                  !userId.trim() ||
                  !brokerServer.trim() ||
                  !accountId.trim() ||
                  !readOnlyPassword.trim()
                }
                className="w-full border border-primary/50 bg-primary/10 px-4 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isBusy ? "ONBOARDING IN PROGRESS" : "INITIALIZE SENTINEL"}
              </button>
            </form>
          )}
        </section>

        <aside className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl sm:p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg font-bold text-foreground">Onboarding Feed</h3>
            {jobId ? (
              <span className="text-[10px] tracking-[0.15em] text-muted-foreground">
                {jobId.slice(0, 8)}
              </span>
            ) : null}
          </div>

          <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            {statusMessage}
          </p>

          <div className="max-h-[420px] space-y-2 overflow-y-auto border border-border/80 bg-background/40 p-3 font-mono text-[11px]">
            {logs.length === 0 ? (
              <div className="text-muted-foreground/70">
                Runtime messages will appear here as Vault, the bridge, and the brain move the
                job forward.
              </div>
            ) : (
              logs.map((line, index) => (
                <div key={`${line}-${index}`} className="text-muted-foreground">
                  {line}
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
