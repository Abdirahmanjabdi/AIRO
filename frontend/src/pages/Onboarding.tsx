import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  CheckCircle2,
  LockKeyhole,
  Radar,
  ServerCog,
  Shield,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import MetricCard from "@/components/MetricCard";
import PipelineVisual from "@/components/PipelineVisual";
import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";
import { toast } from "@/components/ui/sonner";
import type { SentinelIdentity } from "@/hooks/useSentinelIdentity";
import { sentinelApi, type OnboardingState, getExecutionMode } from "@/lib/api";

type Stage = "IDLE" | "VAULT" | "PROVISIONING" | "SYNC" | "AUDIT" | "LIVE";

type StepKey = Exclude<Stage, "IDLE" | "LIVE">;

const STEPS: Array<{
  key: StepKey;
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

const STORAGE_FACTS = [
  {
    title: "Vault transit",
    detail: "Stores the read-only password path and encryption boundary.",
  },
  {
    title: "Postgres",
    detail: "Keeps user metadata, onboarding jobs, and audit-ready state only.",
  },
  {
    title: "S3 / MinIO",
    detail: "Receives the personalized model artifact after baseline training.",
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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function stageTone(stage: Stage, hasError: boolean): {
  accent: "neutral" | "primary" | "secondary" | "danger";
  label: string;
} {
  if (hasError) {
    return { accent: "danger", label: "Needs operator attention" };
  }

  switch (stage) {
    case "LIVE":
      return { accent: "secondary", label: "Live and monitoring" };
    case "VAULT":
      return { accent: "primary", label: "Securing credentials" };
    case "PROVISIONING":
      return { accent: "primary", label: "Provisioning the bridge" };
    case "SYNC":
      return { accent: "primary", label: "Syncing broker history" };
    case "AUDIT":
      return { accent: "secondary", label: "Training the baseline" };
    default:
      return { accent: "neutral", label: "Waiting for initialization" };
  }
}

interface OnboardingProps {
  identity: SentinelIdentity | null;
  onConnected: (identity: SentinelIdentity) => void;
}

export default function Onboarding({ identity, onConnected }: OnboardingProps) {
  const navigate = useNavigate();
  const [userId, setUserId] = useState(identity?.userId ?? "");
  const [brokerServer, setBrokerServer] = useState(identity?.brokerServer ?? "");
  const [accountId, setAccountId] = useState(identity?.accountId ?? "");
  const [readOnlyPassword, setReadOnlyPassword] = useState("");
  const [minTrades, setMinTrades] = useState(10);
  const [stage, setStage] = useState<Stage>("IDLE");
  const [jobId, setJobId] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState(
    "Secure the MT5 bridge, verify history, and train a private baseline.",
  );
  const [logs, setLogs] = useState<string[]>([]);
  const [completionState, setCompletionState] = useState<"ready" | "blank_baseline" | null>(null);
  const pollTokenRef = useRef(0);

  useEffect(() => {
    if (!identity) {
      return;
    }

    setUserId(identity.userId);
    setBrokerServer(identity.brokerServer);
    setAccountId(identity.accountId);
  }, [identity]);

  useEffect(() => {
    return () => {
      pollTokenRef.current += 1;
    };
  }, []);

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
    const pollToken = Date.now();
    pollTokenRef.current = pollToken;
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
      
      const mode = getExecutionMode();
      if (mode === "cloud") {
        setStatusMessage("Provisioning Sentinel Bridge AWS Pod...");
        appendLog("> Requesting AWS EKS Windows Node for bridge isolation...");
        
        const provisionResponse = await sentinelApi.provisionBridge(userId);
        appendLog(`> Provisioning bridge pod: ${provisionResponse.pod_id}`);
        
        // Wait for WebSocket handshake
        await new Promise<void>((resolve, reject) => {
          const cleanup = sentinelApi.wsBridgeProvisioning(provisionResponse.pod_id, (msg) => {
            appendLog(`> [WS] ${msg.message}`);
            if (msg.status === "initialized") {
              resolve();
            }
          });
          // Timeout after 30 seconds for safety
          setTimeout(() => {
            cleanup();
            reject(new Error("WebSocket timeout waiting for Windows Bridge initialization."));
          }, 30000);
        });
      }

      setStatusMessage("Dispatching onboarding to the MT5 bridge.");
      appendLog("> Queueing personalized onboarding job.");

      const onboarding = await sentinelApi.startOnboarding({
        user_id: userId,
        broker_server: brokerServer,
        account_id: accountId,
        min_trades: minTrades,
      });

      setJobId(onboarding.job_id);
      appendLog(`> Job accepted: ${onboarding.job_id}`);
      appendLog(`> ${onboarding.message}`);

      for (let attempt = 0; attempt < 90; attempt += 1) {
        if (pollTokenRef.current !== pollToken) {
          return;
        }

        await sleep(attempt === 0 ? 400 : 2000);
        if (pollTokenRef.current !== pollToken) {
          return;
        }

        const status = await sentinelApi.getOnboardingStatus(onboarding.job_id);
        if (pollTokenRef.current !== pollToken) {
          return;
        }

        setStage(mapOnboardingState(status.state));
        setStatusMessage(status.message);
        appendLog(`> ${status.message}`);

        if (status.state === "ready") {
          onConnected({ userId, brokerServer, accountId });
          setCompletionState("ready");
          setStage("LIVE");
          setIsBusy(false);
          toast.success("Sentinel baseline is ready for live telemetry.");
          return;
        }

        if (status.state === "blank_baseline") {
          onConnected({ userId, brokerServer, accountId });
          setCompletionState("blank_baseline");
          setStage("LIVE");
          setIsBusy(false);
          appendLog("> Blank baseline recorded. Monitoring can start while more history accumulates.");
          toast.success("Blank baseline created. The account is connected and awaiting more history.");
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
      toast.error(
        submissionError instanceof Error
          ? submissionError.message
          : "Unknown onboarding error.",
      );
    }
  }

  const currentStepIndex = STEPS.findIndex((stepItem) => stepItem.key === stage);
  const progressPercent =
    stage === "LIVE"
      ? 100
      : currentStepIndex >= 0
        ? ((currentStepIndex + 1) / STEPS.length) * 100
        : 6;
  const tone = stageTone(stage, Boolean(error));

  return (
    <div className="space-y-6">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Onboarding"
          title="Seal the MT5 bridge, train the baseline, and open the live lane."
          description="This onboarding flow describes the actual control plane path: encrypt credentials in Vault, queue the MT5 bridge, verify broker history, and persist a personalized model artifact for the connected trader."
          aside={(
            <SurfacePanel accent={tone.accent} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    Current lane
                  </div>
                  <div className="mt-2 font-display text-2xl font-bold text-foreground">
                    {stage === "IDLE" ? "Idle" : stage === "LIVE" ? "Live" : stage}
                  </div>
                </div>
                <span className="inline-flex items-center gap-2 border border-border/70 bg-background/35 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  <Activity size={12} />
                  {tone.label}
                </span>
              </div>

              <div className="mt-5">
                <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  <span>Pipeline progress</span>
                  <span>{Math.round(progressPercent)}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden border border-border/70 bg-background/40">
                  <div
                    className="h-full bg-[linear-gradient(90deg,rgba(78,205,196,0.9),rgba(245,166,35,0.9))] transition-[width] duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>

              <div className="mt-5 text-sm leading-7 text-muted-foreground">{statusMessage}</div>
            </SurfacePanel>
          )}
        />
      </Reveal>

      <Reveal delay={0.05}>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Zero-trust storage"
            value="Vault"
            description="Credentials move from browser to Vault transit before the bridge sees them."
            accent="secondary"
            icon={<LockKeyhole size={18} />}
            valueClassName="text-xl text-secondary"
          />
          <MetricCard
            label="History target"
            value={`${minTrades} trades`}
            description="Minimum broker history required before the baseline graduates from onboarding."
            accent="primary"
            icon={<Radar size={18} />}
            valueClassName="text-xl text-primary"
          />
          <MetricCard
            label="Job handle"
            value={jobId ? jobId.slice(0, 8) : "Queued at submit"}
            description="A live onboarding job id appears here once the backend accepts the request."
            accent="neutral"
            icon={<ServerCog size={18} />}
            valueClassName="text-xl text-foreground"
          />
          <MetricCard
            label="Activity feed"
            value={`${logs.length}`}
            description="Runtime messages from Vault, the bridge, and model training accumulate here."
            accent={logs.length > 0 ? "secondary" : "neutral"}
            icon={<Sparkles size={18} />}
          />
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <PipelineVisual steps={STEPS} currentStage={stage} />
      </Reveal>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_400px]">
        <Reveal delay={0.15}>
          <SurfacePanel className="p-6 sm:p-7">
            {completionState ? (
              <div className="space-y-6">
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="mt-1 text-secondary" size={22} />
                    <div>
                      <div className="eyebrow-label">Onboarding complete</div>
                      <h2 className="mt-3 font-display text-3xl font-bold text-foreground">
                        {completionState === "ready" ? "Baseline ready for live telemetry." : "Blank baseline created safely."}
                      </h2>
                      <p className="mt-3 max-w-2xl text-sm leading-8 text-muted-foreground">
                        {completionState === "ready"
                          ? "The model is persisted, the trader identity is connected, and the workspace can now read real risk telemetry from the live backend."
                          : "The broker history came back empty, so Sentinel recorded a blank baseline instead of crashing. Monitoring can begin while more history accumulates."}
                      </p>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-2 border border-secondary/30 bg-secondary/10 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-secondary">
                    <ShieldCheck size={14} />
                    Ready for workspace
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard
                    label="User id"
                    value={userId}
                    description="Identity bound to the saved baseline."
                    accent="neutral"
                    valueClassName="text-lg break-all text-foreground"
                  />
                  <MetricCard
                    label="Broker server"
                    value={brokerServer}
                    description="Broker endpoint used during verification."
                    accent="secondary"
                    valueClassName="text-lg break-all text-secondary"
                  />
                  <MetricCard
                    label="Account id"
                    value={accountId}
                    description="MT5 account associated with this onboarding run."
                    accent="primary"
                    valueClassName="text-lg break-all text-primary"
                  />
                </div>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => navigate("/workspace")}
                    className="inline-flex items-center justify-center gap-2 border border-secondary/35 bg-secondary/10 px-5 py-3 text-[11px] font-bold tracking-[0.18em] text-secondary transition-colors hover:bg-secondary/20"
                  >
                    OPEN COMMAND CENTER
                    <Sparkles size={14} />
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
                    className="border border-border px-5 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                  >
                    RUN AGAIN
                  </button>
                </div>
              </div>
            ) : (
              <form className="space-y-6" onSubmit={handleSubmit}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <div className="eyebrow-label">Secure the broker link</div>
                    <h2 className="mt-3 font-display text-3xl font-bold text-foreground">
                      Connect the trader once, then let the control plane do the hard part.
                    </h2>
                    <p className="mt-3 max-w-2xl text-sm leading-8 text-muted-foreground">
                      The password is stored only in Vault. Postgres receives metadata and job
                      state, never the secret itself.
                    </p>
                  </div>

                  <span className="inline-flex items-center gap-2 border border-border/70 bg-background/35 px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    <Shield size={13} />
                    ZERO-TRUST STORAGE
                  </span>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor="onboarding-user-id"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      USER ID
                    </label>
                    <input
                      id="onboarding-user-id"
                      type="text"
                      value={userId}
                      onChange={(event) => setUserId(event.target.value)}
                      required
                      autoComplete="off"
                      spellCheck={false}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                      placeholder="whop-user-001"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="onboarding-broker-server"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      BROKER SERVER
                    </label>
                    <input
                      id="onboarding-broker-server"
                      type="text"
                      value={brokerServer}
                      onChange={(event) => setBrokerServer(event.target.value)}
                      required
                      autoComplete="off"
                      spellCheck={false}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                      placeholder="ICMarkets-Demo"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="onboarding-account-id"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      ACCOUNT ID
                    </label>
                    <input
                      id="onboarding-account-id"
                      type="text"
                      value={accountId}
                      onChange={(event) => setAccountId(event.target.value)}
                      required
                      autoComplete="off"
                      inputMode="numeric"
                      spellCheck={false}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                      placeholder="12345678"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="onboarding-password"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      READ-ONLY PASSWORD
                    </label>
                    <input
                      id="onboarding-password"
                      type="password"
                      value={readOnlyPassword}
                      onChange={(event) => setReadOnlyPassword(event.target.value)}
                      required
                      autoComplete="new-password"
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                      placeholder="Stored through Vault transit"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label
                      htmlFor="onboarding-min-trades"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      MINIMUM HISTORY
                    </label>
                    <select
                      id="onboarding-min-trades"
                      value={String(minTrades)}
                      onChange={(event) => setMinTrades(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    >
                      <option value="1">Any trades (new account)</option>
                      <option value="5">5 trades</option>
                      <option value="10">10 trades</option>
                      <option value="25">25 trades</option>
                      <option value="50">50 trades</option>
                      <option value="100">100 trades</option>
                      <option value="250">250 trades</option>
                    </select>
                  </div>
                </div>

                <SurfacePanel accent="secondary" className="p-5">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">
                    ZERO-TRUST STORAGE
                  </div>
                  <div className="mt-3 text-sm leading-8 text-muted-foreground">
                    Credentials move from the browser to Vault and from Vault to the bridge.
                    They are not stored in plain text in Postgres, Redis, or audit logs.
                  </div>
                </SurfacePanel>

                {error ? (
                  <SurfacePanel accent="danger" className="p-4 text-sm leading-7 text-destructive">
                    {error}
                  </SurfacePanel>
                ) : null}

                <div className="flex flex-col gap-3 sm:flex-row">
                  <button
                    type="submit"
                    disabled={
                      isBusy ||
                      !userId.trim() ||
                      !brokerServer.trim() ||
                      !accountId.trim() ||
                      !readOnlyPassword.trim()
                    }
                    className="inline-flex items-center justify-center gap-2 border border-primary/40 bg-primary/10 px-5 py-3 text-[11px] font-bold tracking-[0.18em] text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isBusy ? "ONBOARDING IN PROGRESS" : "INITIALIZE SENTINEL"}
                    <Sparkles size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setReadOnlyPassword("");
                      setError(null);
                      setStage("IDLE");
                      setLogs([]);
                      setJobId(null);
                      setStatusMessage(
                        "Secure the MT5 bridge, verify history, and train a private baseline.",
                      );
                    }}
                    className="border border-border px-5 py-3 text-[11px] tracking-[0.18em] text-muted-foreground transition-colors hover:border-secondary/40 hover:text-secondary"
                  >
                    RESET FORM
                  </button>
                </div>
              </form>
            )}
          </SurfacePanel>
        </Reveal>

        <Reveal delay={0.2}>
          <div className="space-y-4">
            <SurfacePanel accent="primary" className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="eyebrow-label">Onboarding feed</div>
                  <div className="mt-2 text-sm leading-7 text-muted-foreground">
                    Live runtime messages from Vault, the bridge, and baseline training.
                  </div>
                </div>
                {jobId ? (
                  <span className="border border-border/70 bg-background/35 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    {jobId.slice(0, 8)}
                  </span>
                ) : null}
              </div>

              <div className="mt-5 max-h-[420px] space-y-2 overflow-y-auto border border-border/70 bg-background/35 p-4 font-mono text-[11px] leading-6">
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
            </SurfacePanel>

            <SurfacePanel className="p-5">
              <div className="eyebrow-label">What gets written where</div>
              <div className="mt-4 space-y-4">
                {STORAGE_FACTS.map((fact) => (
                  <div key={fact.title} className="border border-border/70 bg-background/35 p-4">
                    <div className="text-[11px] font-bold tracking-[0.16em] text-foreground">
                      {fact.title}
                    </div>
                    <div className="mt-2 text-sm leading-7 text-muted-foreground">
                      {fact.detail}
                    </div>
                  </div>
                ))}
              </div>
            </SurfacePanel>
          </div>
        </Reveal>
      </div>
    </div>
  );
}
