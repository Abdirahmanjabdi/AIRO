#!/bin/bash
# =============================================================================
# Sentinel Pod Entrypoint
# Starts Xvfb (virtual display) → Wine + MT5 → Bridge Relay
# =============================================================================
set -e

echo "[Sentinel Pod] Starting virtual display..."
Xvfb :99 -screen 0 1024x768x16 &
sleep 2

echo "[Sentinel Pod] Starting MT5 Terminal..."
if [ -f /mt5/terminal/terminal64.exe ]; then
    wine64 /mt5/terminal/terminal64.exe /portable &
    sleep 5
    echo "[Sentinel Pod] MT5 Terminal started."
else
    echo "[Sentinel Pod] WARNING: No MT5 terminal found at /mt5/terminal/terminal64.exe"
    echo "[Sentinel Pod] Running in bridge-only mode (demo)."
fi

echo "[Sentinel Pod] Starting Bridge Relay..."
echo "[Sentinel Pod] Brain API: ${BRAIN_API_URL}"
echo "[Sentinel Pod] Account: ${MT5_ACCOUNT_ID} @ ${MT5_SERVER}"

# Run the bridge relay (stays in foreground)
python3 /mt5/bridge/mt5_relay.py

echo "[Sentinel Pod] Bridge exited."
