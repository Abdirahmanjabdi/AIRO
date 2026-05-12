import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\Timeline.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import_target = """import SurfacePanel from "@/components/SurfacePanel";"""
import_replacement = """import SurfacePanel from "@/components/SurfacePanel";
import EvolutionWave from "@/components/EvolutionWave";"""
content = content.replace(import_target, import_replacement)

cards_target = """      <Reveal delay={0.05}>
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
      </Reveal>"""

cards_replacement = """      <Reveal delay={0.05}>
        <EvolutionWave generations={generations} />
      </Reveal>"""

content = content.replace(cards_target, cards_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Timeline.tsx patched successfully!")
