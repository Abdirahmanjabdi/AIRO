export const PRODUCT_TAGLINE = "Identity-first trade protection for MT5 operators and funded-trader businesses.";

export const heroPillars = [
  {
    eyebrow: "Identity-First Inference",
    title: "Every trader gets a private behavioral baseline.",
    description:
      "Sentinel Zero trains and loads a dedicated model per trader, so the system reacts to their actual revenge-trading signature instead of a generic average.",
  },
  {
    eyebrow: "Zero-Trust Security",
    title: "Broker secrets move through Vault, not through your database.",
    description:
      "Read-only MT5 credentials are sealed before persistence, then handed to the bridge only for the onboarding and telemetry flow that needs them.",
  },
  {
    eyebrow: "Elastic Control Plane",
    title: "The platform watches latency, readiness, and fleet state in one place.",
    description:
      "The same interface that onboards a trader also surfaces readiness, audits, model artifacts, and cluster-backed control-plane health.",
  },
];

export const platformFacts = [
  "FastAPI brain with personalized ML inference",
  "AWS-ready EKS deployment with Redis, Postgres, Vault, and S3",
  "MT5 relay bridge that stays dumb and passes telemetry upstream",
  "Per-user audit trail for ROM, coaching, and compliance",
];

export const workflowSteps = [
  {
    id: "vault",
    title: "Vault",
    description:
      "The browser submits the read-only password through the credentials endpoint so the secret is sealed before the rest of onboarding begins.",
  },
  {
    id: "provision",
    title: "Provision",
    description:
      "The backend registers the user identity, persists the onboarding job, and dispatches the MT5 bridge work for that trader.",
  },
  {
    id: "history",
    title: "History",
    description:
      "The bridge verifies the broker session and pulls the latest MT5 deals so the feature engine has real trading behavior to learn from.",
  },
  {
    id: "baseline",
    title: "Baseline",
    description:
      "The brain engineers features, trains the model, persists the artifact to S3 or MinIO, and exposes the baseline to live inference.",
  },
];

export const productCapabilities = [
  {
    title: "Behavioral anomaly detection",
    description:
      "Blend Isolation Forest and Random Forest outputs into a single risk decision that can allow, block, or reduce position size.",
  },
  {
    title: "Blank-baseline onboarding",
    description:
      "New accounts do not crash the workflow. If there is no broker history yet, Sentinel records a blank baseline and keeps the account ready for future retraining.",
  },
  {
    title: "Decision audit stream",
    description:
      "Every score is stored with latency, explanation features, mode, and cache metadata so the operator can prove what was prevented and why.",
  },
  {
    title: "Operator-grade runtime status",
    description:
      "Redis, Postgres, model loading, and readiness are surfaced directly in the UI instead of hidden behind generic green-dot dashboards.",
  },
];

export const faqs = [
  {
    question: "What makes Sentinel Zero different from a generic risk bot?",
    answer:
      "Sentinel Zero does not score a trader against an average population. It trains a baseline tied to that trader's own MT5 history, then applies it during live inference so protection reflects their personal behavior.",
  },
  {
    question: "Do you store the trader's broker password in the database?",
    answer:
      "No. The frontend sends the read-only password to the credentials endpoint, which is designed to move the secret into Vault-backed storage. Postgres stores metadata and job state, not plaintext credentials.",
  },
  {
    question: "What happens if an account is brand new and has no MT5 history?",
    answer:
      "The onboarding flow records a blank baseline instead of failing. That lets the trader connect immediately while the platform waits for enough history to retrain a personalized model.",
  },
  {
    question: "Can the frontend run without Supabase?",
    answer:
      "Yes. The current product can run end to end against the FastAPI backend, Redis, Postgres, Vault, and S3. A dedicated auth platform like Supabase or Clerk can still be added later if you want richer customer identity and session management.",
  },
  {
    question: "What does the admin plane show?",
    answer:
      "The operator view aggregates users, onboarding jobs, recent decision state, and baseline readiness so the team can monitor rollout quality and operational health.",
  },
  {
    question: "How does Sentinel fit into a funded-trader or Whop workflow?",
    answer:
      "Whop can drive membership lifecycle events while Sentinel handles onboarding, model training, and decision monitoring. The frontend is built to present that as one continuous SaaS workflow.",
  },
];

export const workspaceHighlights = [
  {
    label: "Live decision budget",
    value: "500 ms",
    detail: "Target telemetry-to-decision loop for the protected path.",
  },
  {
    label: "Model storage",
    value: "S3 / MinIO",
    detail: "Per-user artifacts persisted for repeatable inference.",
  },
  {
    label: "Infra readiness",
    value: "Redis + Postgres",
    detail: "Runtime checks surfaced directly in the operator UI.",
  },
];
