import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\CommandCenter.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add useState and useEffect imports if not present, and import KillSwitchModal
import_target = """import RiskGauge from "@/components/RiskGauge";"""
import_replacement = """import RiskGauge from "@/components/RiskGauge";
import KillSwitchModal from "@/components/KillSwitchModal";
import { useState, useEffect } from "react";"""
content = content.replace(import_target, import_replacement)

# 2. Add state and effect
component_target = """export default function CommandCenter({
  identity,
  dashboard,
  readiness,
  isLoading,
  onRefresh,
}: CommandCenterProps) {"""

component_replacement = """export default function CommandCenter({
  identity,
  dashboard,
  readiness,
  isLoading,
  onRefresh,
}: CommandCenterProps) {
  const [isKillSwitchOpen, setIsKillSwitchOpen] = useState(false);

  useEffect(() => {
    const latest = dashboard?.latest_assessment;
    if (latest?.decision === "BLOCK" && latest?.top_reason?.toLowerCase().includes("revenge")) {
      setIsKillSwitchOpen(true);
    }
  }, [dashboard?.latest_assessment]);"""
content = content.replace(component_target, component_replacement)

# 3. Render KillSwitchModal
return_target = """  return (
    <div className="space-y-6">
      <Reveal>"""

return_replacement = """  return (
    <div className="space-y-6">
      <KillSwitchModal isOpen={isKillSwitchOpen} onAcknowledge={() => setIsKillSwitchOpen(false)} />
      <Reveal>"""
content = content.replace(return_target, return_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("CommandCenter.tsx patched successfully!")
