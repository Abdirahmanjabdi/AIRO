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
import { sentinelApi, type OnboardingState, type TiltResponse, getExecutionMode } from "@/lib/api";

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
    label: "CREDENTIAL SECURE",
    description: "Encrypt broker credentials safely behind advanced security boundaries.",
    icon: LockKeyhole,
  },
  {
    key: "PROVISIONING",
    label: "TELEMETRY LINK",
    description: "Establish isolated telemetry link with the secure bridge environment.",
    icon: ServerCog,
  },
  {
    key: "SYNC",
    label: "HISTORY INDEXING",
    description: "Index past MT5 history and verify initial safety parameters.",
    icon: Radar,
  },
  {
    key: "AUDIT",
    label: "CALIBRATION",
    description: "Calibrate dynamic behavioral baseline and establish safety limits.",
    icon: Shield,
  },
];

const STORAGE_FACTS = [
  {
    title: "Encrypted Credentials Vault",
    detail: "Stores the read-only password path and encryption boundary.",
  },
  {
    title: "Securing Immutable Ledger",
    detail: "Keeps user metadata, onboarding jobs, and audit-ready state only.",
  },
  {
    title: "Encrypted Baseline Store",
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
      return { accent: "secondary", label: "System Governance Active" };
    case "VAULT":
      return { accent: "primary", label: "Securing Transit Boundary" };
    case "PROVISIONING":
      return { accent: "primary", label: "Establishing Isolated Telemetry Link" };
    case "SYNC":
      return { accent: "primary", label: "Synchronizing Historical Ledger" };
    case "AUDIT":
      return { accent: "secondary", label: "Calibrating Behavioral Baseline" };
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
  const [minTrades, setMinTrades] = useState(20);
  const [maxDrawdownPct, setMaxDrawdownPct] = useState(3);
  const [primaryInstrument, setPrimaryInstrument] = useState("NAS100");
  const [tradingStyle, setTradingStyle] = useState<"scalper" | "intraday" | "swing">("intraday");
  const [typicalDailyTrades, setTypicalDailyTrades] = useState(8);
  const [typicalLotSize, setTypicalLotSize] = useState(1);
  const [averageWinHoldMinutes, setAverageWinHoldMinutes] = useState(60);
  const [tiltResponse, setTiltResponse] = useState<TiltResponse>("wait_for_setup");
  const [lossReviewThreshold, setLossReviewThreshold] = useState(3);
  const [maxLotMultiplier, setMaxLotMultiplier] = useState(2);
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
        setStatusMessage("Establishing Isolated Telemetry Link...");
        appendLog("> Directing bridge proxy to secure isolated instance...");
        
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
        initial_parameters: {
          max_drawdown_pct: maxDrawdownPct,
          primary_instrument: primaryInstrument,
          trading_style: tradingStyle,
          typical_daily_trades: typicalDailyTrades,
          typical_lot_size: typicalLotSize,
          average_win_hold_minutes: averageWinHoldMinutes,
          tilt_response: tiltResponse,
          loss_review_threshold: lossReviewThreshold,
          max_lot_multiplier: maxLotMultiplier,
        },
      });
      const apiKey = onboarding.api_key;
      if (!apiKey) {
        throw new Error("Onboarding did not return an API key for this session.");
      }
      onConnected({ userId, brokerServer, accountId, apiKey });

      setJobId(onboarding.job_id);
      appendLog(`> Job accepted: ${onboarding.job_id}`);
      appendLog(`> API key issued for this browser session: ****${onboarding.api_key_last4 ?? apiKey.slice(-4)}`);
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
          setCompletionState("ready");
          setStage("LIVE");
          setIsBusy(false);
          toast.success("Sentinel baseline is ready for live telemetry.");
          return;
        }

        if (status.state === "blank_baseline") {
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
          title="Establish Telemetry Link, calibrate baseline, and activate governance."
          description="This onboarding flow describes the actual Qasali zero-trust link: encrypt credentials safely in the Credentials Vault, establish isolated telemetry links, index broker ledgers, and calibrate a private behavioral baseline."
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
            description="Risk DNA can graduate the model from 10 broker trades when history is available."
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
                    <div className="mt-2 text-[10px] text-primary/80 border border-primary/20 bg-primary/5 p-2 font-sans leading-5">
                      <strong>Sentinel Zero-Asset Protocol:</strong> Read-only credentials cannot execute withdrawals, asset transfers, or balance adjustments. Your capital remains completely locked within your broker environment.
                    </div>
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
                      <option value="20">20 trades</option>
                      <option value="25">25 trades</option>
                      <option value="50">50 trades</option>
                      <option value="100">100 trades</option>
                      <option value="250">250 trades</option>
                    </select>
                  </div>

                  <div className="sm:col-span-2 border border-border/70 bg-background/35 p-4">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">
                      RISK DNA
                    </div>
                    <div className="mt-2 text-sm leading-7 text-muted-foreground">
                      These answers bootstrap the first-session guardrails before Sentinel has
                      enough personal trading history to graduate the model.
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-drawdown"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      MAX DRAWDOWN BEFORE TILT (%)
                    </label>
                    <input
                      id="risk-dna-drawdown"
                      type="number"
                      min="0.1"
                      max="25"
                      step="0.1"
                      value={String(maxDrawdownPct)}
                      onChange={(event) => setMaxDrawdownPct(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-instrument"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      PRIMARY INSTRUMENT
                    </label>
                    <input
                      id="risk-dna-instrument"
                      type="text"
                      value={primaryInstrument}
                      onChange={(event) => setPrimaryInstrument(event.target.value)}
                      required
                      autoComplete="off"
                      spellCheck={false}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/40 focus:border-primary"
                      placeholder="NAS100, XAUUSD, EURUSD"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-daily-trades"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      TYPICAL ROUND-TRIP TRADES PER DAY
                    </label>
                    <input
                      id="risk-dna-daily-trades"
                      type="number"
                      min="1"
                      max="500"
                      step="1"
                      value={String(typicalDailyTrades)}
                      onChange={(event) => setTypicalDailyTrades(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-lot"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      STANDARD UNIT LOT SIZE FOR $100K
                    </label>
                    <input
                      id="risk-dna-lot"
                      type="number"
                      min="0.01"
                      max="500"
                      step="0.01"
                      value={String(typicalLotSize)}
                      onChange={(event) => setTypicalLotSize(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-style"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      STYLE REGIME
                    </label>
                    <select
                      id="risk-dna-style"
                      value={tradingStyle}
                      onChange={(event) => setTradingStyle(event.target.value as "scalper" | "intraday" | "swing")}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    >
                      <option value="scalper">Scalper</option>
                      <option value="intraday">Intraday</option>
                      <option value="swing">Swing</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-hold-time"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      AVERAGE WIN HOLD TIME (MINUTES)
                    </label>
                    <input
                      id="risk-dna-hold-time"
                      type="number"
                      min="1"
                      max="10080"
                      step="1"
                      value={String(averageWinHoldMinutes)}
                      onChange={(event) => setAverageWinHoldMinutes(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-tilt"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      AFTER A LOSS
                    </label>
                    <select
                      id="risk-dna-tilt"
                      value={tiltResponse}
                      onChange={(event) => setTiltResponse(event.target.value as TiltResponse)}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    >
                      <option value="wait_for_setup">Wait for the next setup</option>
                      <option value="mixed">Depends on market structure</option>
                      <option value="immediate_reentry">Often look for immediate re-entry</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="risk-dna-losses"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      CONSECUTIVE LOSSES BEFORE REVIEW
                    </label>
                    <input
                      id="risk-dna-losses"
                      type="number"
                      min="1"
                      max="20"
                      step="1"
                      value={String(lossReviewThreshold)}
                      onChange={(event) => setLossReviewThreshold(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label
                      htmlFor="risk-dna-lot-multiplier"
                      className="mb-1.5 block text-[10px] tracking-[0.15em] text-muted-foreground"
                    >
                      MAX LOT MULTIPLIER BEFORE REVIEW
                    </label>
                    <select
                      id="risk-dna-lot-multiplier"
                      value={String(maxLotMultiplier)}
                      onChange={(event) => setMaxLotMultiplier(Number(event.target.value))}
                      className="h-11 w-full border border-border bg-background/70 px-4 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    >
                      <option value="1.5">1.5x</option>
                      <option value="2">2x</option>
                      <option value="3">3x</option>
                      <option value="5">5x</option>
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
                      !readOnlyPassword.trim() ||
                      !primaryInstrument.trim() ||
                      maxDrawdownPct <= 0 ||
                      typicalDailyTrades <= 0 ||
                      typicalLotSize <= 0 ||
                      averageWinHoldMinutes <= 0 ||
                      lossReviewThreshold <= 0
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
                <div className="mt-8 border-t border-border/70 pt-6 text-[11px] leading-relaxed text-muted-foreground/60">
                  <p className="font-bold uppercase tracking-wider text-muted-foreground/80 mb-2">Legal Disclaimer</p>
                  "Sentinel Trading is a risk management software tool, not a financial advisor or brokerage. We do not guarantee profits or the prevention of all losses. You remain solely responsible for the capital in your trading accounts."
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
