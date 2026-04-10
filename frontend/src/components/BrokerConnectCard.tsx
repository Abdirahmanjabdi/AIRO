"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Database, KeyRound, ServerCog, ShieldCheck } from "lucide-react";
import { useState } from "react";
import "./Card.css";

type OnboardingStage = "IDLE" | "VAULT" | "PROVISIONING" | "LOGGING_IN" | "AUDITING" | "READY";

interface BrokerConnectCardProps {
  onConnected: (userId: string, server: string, accountId: string) => void;
}

interface OnboardingStatus {
  state: string;
  message: string;
}

const STAGES = [
  {
    key: "VAULT" as const,
    icon: KeyRound,
    title: "Vault",
    description: "Transit-encrypting your MT5 credentials before they touch the control plane.",
  },
  {
    key: "PROVISIONING" as const,
    icon: ServerCog,
    title: "Provisioning",
    description: "Preparing your dedicated Sentinel pod and wiring the broker bridge.",
  },
  {
    key: "LOGGING_IN" as const,
    icon: ShieldCheck,
    title: "Logging In",
    description: "Verifying the broker session and extracting your last 100 MT5 deals.",
  },
  {
    key: "AUDITING" as const,
    icon: Database,
    title: "Auditing",
    description: "Training and persisting your personalized baseline to S3.",
  },
] satisfies Array<{
  key: Exclude<OnboardingStage, "IDLE" | "READY">;
  icon: typeof KeyRound;
  title: string;
  description: string;
}>;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function resolveStage(status: OnboardingStatus): OnboardingStage {
  if (status.state === "pending") {
    return "PROVISIONING";
  }
  if (status.state === "pulling_history") {
    return "LOGGING_IN";
  }
  if (status.state === "training" || status.state === "blank_baseline") {
    return "AUDITING";
  }
  if (status.state === "ready") {
    return "READY";
  }
  return "PROVISIONING";
}

export default function BrokerConnectCard({ onConnected }: BrokerConnectCardProps) {
  const [stage, setStage] = useState<OnboardingStage>("IDLE");
  const [userId, setUserId] = useState("demo-user-001");
  const [server, setServer] = useState("ICMarkets-Demo");
  const [accountId, setAccountId] = useState("98765432");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("Secure the broker link and train a per-user baseline.");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleConnect = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrorMessage(null);
    setStage("VAULT");
    setStatusMessage("Encrypting credentials through Vault transit...");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_BRAIN_API_URL;
      if (!apiUrl) {
        throw new Error("NEXT_PUBLIC_BRAIN_API_URL is not configured.");
      }

      const credentialsResponse = await fetch(`${apiUrl}/v1/credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          broker_server: server,
          account_id: accountId,
          read_only_password: password,
        }),
      });

      if (!credentialsResponse.ok) {
        const details = await credentialsResponse.text();
        throw new Error(`Credential storage failed: ${details}`);
      }

      setStage("PROVISIONING");
      setStatusMessage("Provisioning your bridge and scheduling MT5 verification...");

      const onboardingResponse = await fetch(`${apiUrl}/v1/onboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          broker_server: server,
          account_id: accountId,
        }),
      });

      if (!onboardingResponse.ok) {
        const details = await onboardingResponse.text();
        throw new Error(`Onboarding request failed: ${details}`);
      }

      const onboarding = (await onboardingResponse.json()) as { job_id: string };
      const jobId = onboarding.job_id;

      for (let attempt = 0; attempt < 90; attempt += 1) {
        const statusResponse = await fetch(`${apiUrl}/v1/onboard/${jobId}`, {
          cache: "no-store",
        });
        if (!statusResponse.ok) {
          const details = await statusResponse.text();
          throw new Error(`Status polling failed: ${details}`);
        }

        const status = (await statusResponse.json()) as OnboardingStatus;
        const resolvedStage = resolveStage(status);
        setStage(resolvedStage);
        setStatusMessage(status.message);

        if (status.state === "ready") {
          onConnected(userId, server, accountId);
          return;
        }
        if (status.state === "blank_baseline") {
          throw new Error(
            "Blank baseline created. No MT5 trade history was found yet, so Sentinel will remain baseline-pending until more trades accumulate."
          );
        }
        if (status.state === "failed") {
          throw new Error(status.message);
        }

        await delay(2000);
      }

      throw new Error("Timed out waiting for onboarding to complete.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown onboarding error";
      setErrorMessage(message);
      setStage("IDLE");
      setStatusMessage("Secure the broker link and train a per-user baseline.");
    }
  };

  return (
    <div className="broker-card glass-panel animate-slide-up">
      <div className="card-header">
        <h2>Connect and Forget</h2>
        <p>Vault-secured onboarding, dedicated bridge provisioning, and an identity-bound risk baseline.</p>
      </div>

      {stage === "IDLE" ? (
        <form className="connect-form" onSubmit={handleConnect}>
          <div className="form-grid">
            <div className="form-group">
              <label>User ID</label>
              <input
                type="text"
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>MT5 Server</label>
              <input
                type="text"
                value={server}
                onChange={(event) => setServer(event.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Account ID</label>
              <input
                type="text"
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Read-Only Password</label>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="card-callout">
            <span className="callout-pill">Zero-Trust</span>
            <p>Credentials are encrypted before broker history retrieval and never written to Postgres.</p>
          </div>

          {errorMessage ? (
            <p className="text-error form-error">
              {errorMessage}
            </p>
          ) : null}

          <button type="submit" className="glow-btn connect-submit">
            Initialize Baseline
          </button>
        </form>
      ) : (
        <div className="stepper-container">
          {STAGES.map((step, index) => {
            const stageIndex = STAGES.findIndex((item) => item.key === stage);
            const isCompleted = stage === "READY" || index < stageIndex;
            const isActive = stage === step.key;
            const Icon = isCompleted ? CheckCircle2 : step.icon;

            return (
              <motion.div
                key={step.key}
                className={`step ${isActive ? "active" : isCompleted ? "completed" : "pending"}`}
                initial={{ opacity: 0, x: -18 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.08, duration: 0.35 }}
              >
                <div className="step-icon-shell">
                  <Icon className={isActive ? "text-blue pulse" : isCompleted ? "text-neon-mint" : "text-muted"} />
                </div>
                <div className="step-copy">
                  <strong>{step.title}</strong>
                  <span>{step.description}</span>
                </div>
              </motion.div>
            );
          })}

          <div className="stepper-status">
            <span className={stage === "READY" ? "text-neon-mint animate-pulse" : "text-muted"}>
              {stage === "READY" ? "Baseline Ready. Loading dashboard..." : statusMessage}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
