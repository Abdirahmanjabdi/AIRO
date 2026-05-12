import { AlertTriangle, Lock } from "lucide-react";

interface KillSwitchModalProps {
  isOpen: boolean;
  onAcknowledge: () => void;
}

export default function KillSwitchModal({ isOpen, onAcknowledge }: KillSwitchModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/95 backdrop-blur-md">
      <div className="max-w-lg p-8 border-2 border-danger bg-danger/10 text-center shadow-[0_0_50px_rgba(255,51,51,0.15)] relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-danger animate-pulse" />
        
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-danger/20 mb-6 border border-danger/40">
          <AlertTriangle className="h-10 w-10 text-danger" />
        </div>

        <h2 className="text-2xl font-display font-bold text-foreground mb-3 uppercase tracking-widest">
          Equity Guard Triggered
        </h2>
        
        <p className="text-base text-foreground/80 mb-6 leading-7">
          The Sentinel AI has identified a severe <strong className="text-danger">"Revenge Trading"</strong> signature. This execution has been blocked to protect your <span className="font-mono text-secondary">FTMO / Max Daily Drawdown</span> limits.
        </p>

        <div className="bg-background/50 border border-border/50 p-4 mb-8 text-left">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground mb-2 flex items-center gap-2">
            <Lock size={12} /> Mandatory Intervention
          </div>
          <div className="text-sm font-mono text-foreground/70">
            System requires a 15-minute cool-off period or manual stabilization of your Risk-to-Reward profile before trading can resume.
          </div>
        </div>

        <button
          onClick={onAcknowledge}
          className="w-full py-4 text-[11px] font-bold tracking-[0.2em] text-background bg-danger hover:bg-danger/90 transition-colors uppercase"
        >
          I acknowledge this intervention
        </button>
      </div>
    </div>
  );
}
