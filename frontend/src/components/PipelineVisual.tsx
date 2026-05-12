import { CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import SurfacePanel from "@/components/SurfacePanel";

interface PipelineVisualProps {
  steps: Array<{
    key: string;
    label: string;
    description: string;
    icon: any;
  }>;
  currentStage: string;
}

export default function PipelineVisual({ steps, currentStage }: PipelineVisualProps) {
  const currentIndex = steps.findIndex((s) => s.key === currentStage);
  const isLive = currentStage === "LIVE";
  
  // Calculate width for the glowing bar based on completion
  const fillWidth = isLive ? "100%" : currentIndex >= 0 ? `${(currentIndex / (steps.length - 1)) * 100}%` : "0%";

  return (
    <SurfacePanel className="p-6">
      <div className="mb-6">
        <div className="eyebrow-label">Data Flow & Initialization Pipeline</div>
        <div className="mt-2 text-sm text-muted-foreground">
          Visualizing credentials moving through transit encryption, sync, and artifact generation.
        </div>
      </div>
      
      <div className="relative pt-6 pb-2">
        {/* Background track */}
        <div className="absolute top-9 left-0 w-full h-1 bg-muted/40 rounded-full" />
        
        {/* Animated Fill Bar */}
        <motion.div 
          className="absolute top-9 left-0 h-1 rounded-full bg-gradient-to-r from-secondary to-primary shadow-[0_0_12px_rgba(245,166,35,0.6)]"
          initial={{ width: "0%" }}
          animate={{ width: fillWidth }}
          transition={{ duration: 0.8, ease: "easeInOut" }}
        />

        {/* Nodes */}
        <div className="relative flex justify-between">
          {steps.map((step, index) => {
            const isComplete = isLive || (currentIndex >= 0 && index < currentIndex);
            const isActive = step.key === currentStage;
            const isPending = !isComplete && !isActive;
            const Icon = isComplete ? CheckCircle2 : step.icon;

            return (
              <div key={step.key} className="flex flex-col items-center w-32 relative">
                <motion.div 
                  className={`w-8 h-8 rounded-full flex items-center justify-center border-2 mb-3 bg-card
                    ${isComplete ? "border-secondary text-secondary shadow-[0_0_10px_rgba(78,205,196,0.3)]" : 
                      isActive ? "border-primary text-primary shadow-[0_0_10px_rgba(245,166,35,0.4)]" : 
                      "border-muted text-muted-foreground"}`}
                  animate={isActive ? { scale: [1, 1.1, 1], boxShadow: ["0 0 0px rgba(245,166,35,0)", "0 0 15px rgba(245,166,35,0.6)", "0 0 0px rgba(245,166,35,0)"] } : {}}
                  transition={{ repeat: isActive ? Infinity : 0, duration: 2 }}
                >
                  <Icon size={14} />
                </motion.div>
                
                <div className={`text-[10px] uppercase font-bold tracking-widest text-center ${isComplete || isActive ? "text-foreground" : "text-muted-foreground"}`}>
                  {step.label}
                </div>
                <div className="mt-1 text-[10px] text-center text-muted-foreground/70 hidden sm:block">
                  {step.description}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SurfacePanel>
  );
}
