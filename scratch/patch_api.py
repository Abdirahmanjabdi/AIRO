import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\frontend\src\lib\api.ts"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update resolveApiBaseUrl and add get/set execution mode
resolve_target = """function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_BRAIN_API_URL?.trim();
  if (configured) {
    return configured.replace(/\\/+$/, "");
  }

  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

const API_BASE_URL = resolveApiBaseUrl();

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}"""

resolve_replacement = """export function getExecutionMode(): "local" | "cloud" {
  return (localStorage.getItem("execution_mode") as "local" | "cloud") || "cloud";
}

export function setExecutionMode(mode: "local" | "cloud") {
  localStorage.setItem("execution_mode", mode);
  window.dispatchEvent(new Event("executionModeChanged"));
}

function resolveApiBaseUrl(): string {
  if (getExecutionMode() === "cloud") {
    return "https://api.sentinel-zero.cloud";
  }

  const configured = import.meta.env.VITE_BRAIN_API_URL?.trim();
  if (configured) {
    return configured.replace(/\\/+$/, "");
  }

  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8000`;
}

export function getApiBaseUrl(): string {
  return resolveApiBaseUrl();
}"""
content = content.replace(resolve_target, resolve_replacement)

# 2. Update apiRequest to use dynamic API_BASE_URL instead of the static one
api_request_target = """    response = await fetch(`${API_BASE_URL}${path}`, {"""
api_request_replacement = """    response = await fetch(`${getApiBaseUrl()}${path}`, {"""
content = content.replace(api_request_target, api_request_replacement)

# 3. Add provisionBridge and wsBridgeProvisioning to sentinelApi
api_methods_target = """  getAdminOverview(): Promise<AdminOverview> {
    return apiRequest("/v1/admin/overview");
  },
};"""

api_methods_replacement = """  getAdminOverview(): Promise<AdminOverview> {
    return apiRequest("/v1/admin/overview");
  },

  // Mock Provisioning Endpoint
  provisionBridge(userId: string): Promise<{ status: string; pod_id: string }> {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({ status: "provisioning", pod_id: `eks-win-${Math.random().toString(36).substring(7)}` });
      }, 1500);
    });
  },

  // Mock WebSocket Handshake
  wsBridgeProvisioning(podId: string, onMessage: (msg: any) => void): () => void {
    const sequence = [
      { status: "pulling_image", message: "Spinning up AWS Windows Server Pod..." },
      { status: "booting", message: "Starting MetaTrader 5 Terminal via bridge..." },
      { status: "initialized", message: "mt5.initialize() successful. Handshake complete." }
    ];
    
    let step = 0;
    const interval = setInterval(() => {
      if (step < sequence.length) {
        onMessage(sequence[step]);
        step++;
      } else {
        clearInterval(interval);
      }
    }, 2500);

    return () => clearInterval(interval);
  }
};"""
content = content.replace(api_methods_target, api_methods_replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("api.ts patched successfully!")
