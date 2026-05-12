import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\Onboarding.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add PipelineVisual import
import_target = """import MetricCard from "@/components/MetricCard";"""
import_replacement = """import MetricCard from "@/components/MetricCard";
import PipelineVisual from "@/components/PipelineVisual";"""
content = content.replace(import_target, import_replacement)

# 2. Replace static cards with PipelineVisual
cards_target = """      <Reveal delay={0.1}>
        <div className="grid gap-4 xl:grid-cols-4">
          {STEPS.map((stepItem, index) => {
            const isComplete = stage === "LIVE" || (currentStepIndex >= 0 && index < currentStepIndex);
            const isActive = stepItem.key === stage;
            const Icon = isComplete ? CheckCircle2 : stepItem.icon;

            return (
              <SurfacePanel
                key={stepItem.key}
                accent={isActive ? "primary" : isComplete ? "secondary" : "neutral"}
                className="p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    0{index + 1}
                  </div>
                  <Icon
                    size={18}
                    className={
                      isComplete
                        ? "text-secondary"
                        : isActive
                          ? "text-primary"
                          : "text-muted-foreground"
                    }
                  />
                </div>
                <div className="mt-6 font-display text-xl font-bold text-foreground">
                  {stepItem.label}
                </div>
                <div className="mt-3 text-sm leading-7 text-muted-foreground">
                  {stepItem.description}
                </div>
              </SurfacePanel>
            );
          })}
        </div>
      </Reveal>"""

cards_replacement = """      <Reveal delay={0.1}>
        <PipelineVisual steps={STEPS} currentStage={stage} />
      </Reveal>"""

content = content.replace(cards_target, cards_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Onboarding.tsx patched successfully!")
