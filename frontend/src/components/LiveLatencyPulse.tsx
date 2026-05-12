import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function LiveLatencyPulse() {
  const [latency, setLatency] = useState(42); // Initial simulated sub-50ms latency

  useEffect(() => {
    // Simulate real-time latency fluctuations between 38ms and 48ms
    const interval = setInterval(() => {
      setLatency(Math.floor(Math.random() * 10) + 38);
    }, 800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl flex flex-col justify-between h-full">
      <div className="flex justify-between items-center">
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Decision Budget</div>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
          <span className="text-[9px] uppercase tracking-widest text-secondary font-mono">Live</span>
        </div>
      </div>
      
      <div className="mt-3 flex items-end justify-between">
        <div className="font-display text-3xl font-bold text-secondary">
          {latency}
          <span className="text-xl text-secondary/70 ml-1">ms</span>
        </div>
        
        <div className="flex items-end gap-0.5 h-8">
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={i}
              className="w-1 bg-secondary/80 rounded-t-sm"
              initial={{ height: "20%" }}
              animate={{
                height: [`${Math.random() * 40 + 20}%`, `${Math.random() * 80 + 20}%`, `${Math.random() * 40 + 20}%`],
              }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                delay: i * 0.1,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
