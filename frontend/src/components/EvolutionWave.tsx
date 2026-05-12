import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import SurfacePanel from "@/components/SurfacePanel";

interface EvolutionWaveProps {
  generations: Array<{
    version: string;
    title: string;
    description: string;
    icon: string;
    active?: boolean;
  }>;
}

export default function EvolutionWave({ generations }: EvolutionWaveProps) {
  return (
    <div className="w-full overflow-x-auto pb-8 pt-4 hide-scrollbar">
      <div className="flex gap-6 min-w-max px-2">
        {generations.map((generation, index) => (
          <motion.div
            key={generation.version}
            className="flex flex-col relative"
            initial={{ width: "240px", opacity: 0.8 }}
            whileHover={{ width: "320px", opacity: 1 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <SurfacePanel
              accent={generation.active ? "primary" : "neutral"}
              className="relative p-6 h-full flex flex-col justify-between overflow-hidden shadow-lg"
            >
              {generation.active && (
                <span className="absolute right-4 top-4 border border-primary/30 px-2 py-0.5 text-[9px] tracking-[0.15em] text-primary bg-primary/10">
                  ACTIVE
                </span>
              )}

              <span className="absolute -left-2 -top-2 text-[100px] font-display font-bold leading-none text-foreground/[0.03] pointer-events-none select-none">
                {generation.version}
              </span>

              <div className="relative z-10">
                <div className="mb-4 flex items-center justify-between">
                  <div className="text-lg font-bold tracking-[0.2em] text-secondary font-mono">
                    {generation.icon}
                  </div>
                  {index < generations.length - 1 && (
                    <ArrowRight size={20} className="text-muted-foreground/40" />
                  )}
                </div>
                
                <div className="mb-3 text-[12px] font-bold tracking-[0.18em] text-primary uppercase">
                  {generation.title}
                </div>
                
                <p className="text-sm leading-7 text-muted-foreground">
                  {generation.description}
                </p>
              </div>
            </SurfacePanel>
            
            {/* The underlying visual "wave" connector */}
            {index < generations.length - 1 && (
              <div className="absolute top-1/2 -right-6 w-6 h-px bg-border/80 z-0" />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
