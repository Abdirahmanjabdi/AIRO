export const PRODUCT_TAGLINE = "Stop blowing funded accounts. Algorithmic hard-coded lockout and 12-hour breach protection for serious futures and forex traders.";

export const heroPillars = [
  {
    eyebrow: "Stop Revenge Trading",
    title: "Willpower is a failed risk management strategy.",
    description:
      "When tilt hits, logic vanishes. Sentinel Zero acts as a hard-coded physical lockout layer, intercepting toxic sizing cascades and revenge re-entries inside the broker engine before your drawdown limit is breached.",
  },
  {
    eyebrow: "12-Hour Breach Protection",
    title: "Dynamic anomaly sensitivity when you need it most.",
    description:
      "If you experience a consecutive loss streak (2+ losses), the ML engine automatically tightens anomaly sensitivity to 0.05. It restricts execution speed, slashes size limits, and blocks reckless trades for a full 12 hours.",
  },
  {
    eyebrow: "Institutional Safeguards",
    title: "Vault-secured read-only monitoring for MT5.",
    description:
      "We connect using read-only API access keys, encrypted instantly via HashiCorp Vault. Sentinel monitors execution telemetry, calculates realtime SHAP values, and keeps your trading account 100% secure.",
  },
];

export const platformFacts = [
  "Algorithmic Hard-Coded Lockout with sub-50ms intercept speed",
  "12-Hour Breach Protection that automatically tightens risk boundaries on streak loss",
  "No chrome extensions or local delays—runs directly inside EKS Win Server MT5 relays",
  "Detailed decision audit ledger with SHAP values explaining every intercept",
];

export const workflowSteps = [
  {
    id: "vault",
    title: "Secure MT5 API",
    description:
      "Input your read-only broker credentials. They are immediately sealed inside Vault-level AES-256 encrypted storage.",
  },
  {
    id: "provision",
    title: "Spawn Relay",
    description:
      "Sentinel registers your identity and spins up a dedicated high-speed Windows Server MT5 relay node on our EC2 cluster.",
  },
  {
    id: "history",
    title: "Train Baseline",
    description:
      "The system syncs your trading history to map your personalized variance baseline and emotional anomaly threshold.",
  },
  {
    id: "baseline",
    title: "Arm Sentinel",
    description:
      "The risk gateway is armed. Live telemetry is analyzed. If emotional tilt or drawdown bounds are breached, execution is terminated.",
  },
];

export const productCapabilities = [
  {
    title: "Emotional Tilt Intercept",
    description:
      "Detects rapid lot-size escalations, revenge timer compressions, and extreme lot deviation anomalies, terminating access to cool you down.",
  },
  {
    title: "12-Hour Streak Tightening",
    description:
      "If a losing streak is detected within a 12h window, risk parameters dynamically tighten, reducing your max allowable size.",
  },
  {
    title: "Explainable Risk Audits",
    description:
      "Every single trade decision is logged with deep explainability showing exactly which feature triggered the intercept.",
  },
  {
    title: "Physical Terminal Lockout",
    description:
      "No client-side workarounds. Sentinel executes physical closing orders at the broker layer, preventing web-terminal override.",
  },
];

export const faqs = [
  {
    question: "How does Sentinel prevent me from blowing a prop firm account?",
    answer:
      "Prop firms fail 95% of traders due to strict daily drawdown limits. Sentinel continuously tracks your drawdown state and revenge trading metrics. If you tilt or hit a losing streak, Sentinel blocks trading at the gateway level, keeping you well within your daily drawdown boundaries.",
  },
  {
    question: "What is the 12-Hour Breach Protection?",
    answer:
      "If you hit 2 or more losses within a 12-hour lookback window, Sentinel enters Restricted Mode. It tightens its anomaly sensitivity threshold from normal to 0.05. This means any deviation in your lot size, hold time, or contract volume will trigger an immediate trade blocker.",
  },
  {
    question: "Can I bypass the lockout if I get angry?",
    answer:
      "No. Sentinel's lockout is enforced directly by the Windows MT5 relay node in the cloud. Even if you close your web browser or uninstall your local workspace, the lockout remains active for the full duration of your cooldown timer.",
  },
  {
    question: "How are my MT5 credentials protected?",
    answer:
      "Sentinel uses read-only passwords to monitor and close positions. Your broker credentials are never exposed and are encrypted with HashiCorp Vault. Sentinel cannot withdraw funds or execute arbitrary trades beyond risk management protocols.",
  },
  {
    question: "Does it support new accounts?",
    answer:
      "Yes. If your account is brand new, Sentinel initiates a Blank Baseline state. It enforces standard conservative limits while it trains a customized behavioral model on your first 20-50 trades.",
  },
  {
    question: "What is the response latency?",
    answer:
      "Sentinel processes telemetry and evaluates risk in less than 50 milliseconds. The EKS Windows Server relay intercepts trade signals instantly, ensuring you are blocked before a trade fills.",
  },
];

export const workspaceHighlights = [
  {
    label: "Active Lockout Speed",
    value: "Sub-50ms",
    detail: "High-frequency trade intercepts at the MT5 relay gateway.",
  },
  {
    label: "Drawdown Defense",
    value: "Tilt Blocker",
    detail: "Un-bypasable cloud-enforced locks to protect prop firm funding.",
  },
  {
    label: "Breach Lookback",
    value: "12-Hour Streak",
    detail: "Dynamic risk tightening to 0.05 sensitivity on consecutive losses.",
  },
];
