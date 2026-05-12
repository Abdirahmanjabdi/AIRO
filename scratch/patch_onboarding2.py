import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\pages\Onboarding.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update mapOnboardingState
import_target = """import { sentinelApi, type OnboardingState } from "@/lib/api";"""
import_replacement = """import { sentinelApi, type OnboardingState, getExecutionMode } from "@/lib/api";"""
content = content.replace(import_target, import_replacement)

# 2. Update logic inside handleSubmit
logic_target = """      const credentialResponse = await sentinelApi.storeCredentials({
        user_id: userId,
        broker_server: brokerServer,
        account_id: accountId,
        read_only_password: readOnlyPassword,
      });

      appendLog(`> Vault path confirmed: ${credentialResponse.vault_path}`);

      setStage("PROVISIONING");
      setStatusMessage("Dispatching onboarding to the MT5 bridge.");
      appendLog("> Queueing personalized onboarding job.");"""

logic_replacement = """      const credentialResponse = await sentinelApi.storeCredentials({
        user_id: userId,
        broker_server: brokerServer,
        account_id: accountId,
        read_only_password: readOnlyPassword,
      });

      appendLog(`> Vault path confirmed: ${credentialResponse.vault_path}`);

      setStage("PROVISIONING");
      
      const mode = getExecutionMode();
      if (mode === "cloud") {
        setStatusMessage("Provisioning Sentinel Bridge AWS Pod...");
        appendLog("> Requesting AWS EKS Windows Node for bridge isolation...");
        
        const provisionResponse = await sentinelApi.provisionBridge(userId);
        appendLog(`> Provisioning bridge pod: ${provisionResponse.pod_id}`);
        
        // Wait for WebSocket handshake
        await new Promise<void>((resolve, reject) => {
          const cleanup = sentinelApi.wsBridgeProvisioning(provisionResponse.pod_id, (msg) => {
            appendLog(`> [WS] ${msg.message}`);
            if (msg.status === "initialized") {
              resolve();
            }
          });
          // Timeout after 30 seconds for safety
          setTimeout(() => {
            cleanup();
            reject(new Error("WebSocket timeout waiting for Windows Bridge initialization."));
          }, 30000);
        });
      }

      setStatusMessage("Dispatching onboarding to the MT5 bridge.");
      appendLog("> Queueing personalized onboarding job.");"""

content = content.replace(logic_target, logic_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Onboarding.tsx patched successfully!")
