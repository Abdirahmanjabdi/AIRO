#!/bin/sh
set -eu

echo "[Sentinel Pod] Starting virtual display..."
Xvfb :99 -screen 0 1024x768x16 &
sleep 2

echo "[Sentinel Pod] Starting bridge relay..."
python -m sentinel.bridge.mt5_relay
