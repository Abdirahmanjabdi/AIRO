import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\SystemConfig.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import_target = """import { Binary, Cloud, DatabaseZap, ShieldCheck } from "lucide-react";"""
import_replacement = """import { useState, useEffect } from "react";
import { Binary, Cloud, DatabaseZap, ShieldCheck, Server } from "lucide-react";
import { getExecutionMode, setExecutionMode } from "@/lib/api";"""
content = content.replace(import_target, import_replacement)

component_start_target = """export default function SystemConfig({
  identity,
  dashboard,
  readiness,
  apiBaseUrl,
}: SystemConfigProps) {"""

component_start_replacement = """export default function SystemConfig({
  identity,
  dashboard,
  readiness,
  apiBaseUrl,
}: SystemConfigProps) {
  const [mode, setModeState] = useState<"local" | "cloud">(getExecutionMode());
  const [warning, setWarning] = useState<string | null>(null);

  const handleToggle = (newMode: "local" | "cloud") => {
    if (newMode === "local") {
      const isWindows = navigator.platform.indexOf('Win') > -1 || navigator.userAgent.indexOf('Windows') > -1;
      if (!isWindows) {
        setWarning("MT5 Native Library requires Windows. Switching to AWS Managed Bridge...");
        setTimeout(() => setWarning(null), 5000);
        return; // Block the switch
      }
    }
    setModeState(newMode);
    setExecutionMode(newMode);
    // Reload to apply API Base URL changes everywhere
    window.location.reload();
  };"""
content = content.replace(component_start_target, component_start_replacement)

header_target = """      <Reveal>
        <SectionHeader
          eyebrow="Workspace / Runtime"
          title="System configuration and runtime truth"
          description="Read-only runtime configuration exposed from the live control plane. This surface intentionally reflects backend truth instead of letting the browser drift into its own config state."
        />
      </Reveal>"""

header_replacement = """      <Reveal>
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <SectionHeader
            eyebrow="Workspace / Runtime"
            title="System configuration and runtime truth"
            description="Read-only runtime configuration exposed from the live control plane. This surface intentionally reflects backend truth instead of letting the browser drift into its own config state."
          />
          <SurfacePanel className="p-4 md:min-w-[320px]">
            <div className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-3">
              Execution Routing
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleToggle("cloud")}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold tracking-widest border transition-colors ${
                  mode === "cloud" ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                <Cloud size={14} /> CLOUD
              </button>
              <button
                onClick={() => handleToggle("local")}
                className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold tracking-widest border transition-colors ${
                  mode === "local" ? "border-secondary text-secondary bg-secondary/10" : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                <Server size={14} /> LOCAL
              </button>
            </div>
            {warning && (
              <div className="mt-3 text-xs text-danger font-mono bg-danger/10 border border-danger/30 p-2">
                {warning}
              </div>
            )}
          </SurfacePanel>
        </div>
      </Reveal>"""
content = content.replace(header_target, header_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SystemConfig.tsx patched successfully!")
