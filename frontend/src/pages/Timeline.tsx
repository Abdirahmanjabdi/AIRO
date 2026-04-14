import { ArrowRight } from "lucide-react";

import Reveal from "@/components/Reveal";
import SectionHeader from "@/components/SectionHeader";
import SurfacePanel from "@/components/SurfacePanel";

const generations = [
  {
    version: "V1",
    title: "BASELINE SIGNALS",
    description:
      "The first anomaly path focused on simple drawdown and streak awareness with a single threshold.",
    icon: "01",
  },
  {
    version: "V2",
    title: "REGIME GATE",
    description:
      "Market-context features added volatility and momentum so the brain could separate chop from directional flow.",
    icon: "02",
  },
  {
    version: "V3",
    title: "OPTIMIZED THRESHOLD",
    description:
      "Threshold and tree depth were tuned into the current production defaults around 0.6537 and depth 10.",
    icon: "03",
  },
  {
    version: "V4",
    title: "CONTINUOUS SIZING",
    description:
      "Risk moved from a binary gate to a continuous size multiplier so protection could scale instead of snap.",
    icon: "04",
  },
  {
    version: "V5",
    title: "PERSONALIZED BASELINES",
    description:
      "Each trader now gets a private model artifact, Vault-backed onboarding, and audit persistence.",
    icon: "05",
    active: true,
  },
];

export default function Timeline() {
  return (
    <div className="space-y-8">
      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Timeline"
          title="How Sentinel evolved into the current control plane"
          description="The visual shell is now backed by the production Sentinel stack. This timeline shows how the risk engine matured from basic anomaly gating into identity-aware protection."
        />
      </Reveal>

      <Reveal delay={0.05}>
        <div className="grid gap-4 xl:grid-cols-5">
          {generations.map((generation, index) => (
            <SurfacePanel
              key={generation.version}
              accent={generation.active ? "primary" : "neutral"}
              className="relative p-5"
            >
              {generation.active ? (
                <span className="absolute right-3 top-3 border border-primary/30 px-2 py-0.5 text-[9px] tracking-[0.15em] text-primary">
                  ACTIVE
                </span>
              ) : null}

              <span className="absolute left-3 top-2 text-[72px] font-display font-bold leading-none text-foreground/[0.05]">
                {generation.version}
              </span>

              <div className="relative z-10 pt-16">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm font-bold tracking-[0.2em] text-secondary">
                    {generation.icon}
                  </div>
                  {index < generations.length - 1 ? (
                    <ArrowRight size={16} className="text-muted-foreground/70" />
                  ) : null}
                </div>
                <div className="mb-2 text-[11px] font-bold tracking-[0.18em] text-primary">
                  {generation.title}
                </div>
                <p className="text-sm leading-7 text-muted-foreground">
                  {generation.description}
                </p>
              </div>
            </SurfacePanel>
          ))}
        </div>
      </Reveal>

      <Reveal delay={0.1}>
        <SurfacePanel accent="secondary" className="p-6 font-mono text-sm">
          <div className="mb-2 text-muted-foreground">{">"} ACTIVE_FORMULA</div>
          <div className="text-foreground">size = max(0, 1 - (risk * sensitivity))</div>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-muted-foreground">
            <span>
              threshold = <span className="text-primary">0.6537</span>
            </span>
            <span>|</span>
            <span>
              contamination = <span className="text-secondary">0.0399</span>
            </span>
            <span>|</span>
            <span>
              model = <span className="text-foreground">IsolationForest + RandomForest</span>
            </span>
          </div>
        </SurfacePanel>
      </Reveal>
    </div>
  );
}
