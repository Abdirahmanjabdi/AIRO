"""
Sentinel Pod — MT5 Bridge Relay
=================================
STATELESS RELAY ONLY. Sends trade telemetry to Brain API,
receives decisions, executes on MT5.

IP PROTECTION (AI_CONTRACT §3):
  - NO anomaly detection
  - NO risk classification
  - NO Bayesian logic
  - NO SHAP explanations
  This script is a DUMB PIPE.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from typing import NoReturn

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

BRAIN_API_URL: str = os.getenv("BRAIN_API_URL", "http://localhost:8000")
POLL_INTERVAL_SECONDS: float = float(os.getenv("POLL_INTERVAL", "0.5"))
HEARTBEAT_INTERVAL: float = 30.0


# =============================================================================
# DATA MODELS (minimal — no risk logic)
# =============================================================================

class TradeTelemetry(BaseModel):
    """Raw telemetry from MT5 terminal. Relay sends this to Brain API."""
    hour_decimal: float
    losing_streak: int
    drawdown_state: float
    lot_deviation: float
    revenge_timer: float
    lots: float
    rr_ratio: float
    realized_vol_20: float = 0.0
    trend_momentum: float = 0.0


class BrainDecision(BaseModel):
    """Decision received from Brain API. Relay executes this."""
    decision: str       # ALLOW | BLOCK | REDUCE_SIZE
    risk_score: float
    size_multiplier: float
    is_anomaly: bool


# =============================================================================
# BRIDGE RELAY
# =============================================================================

class MT5BridgeRelay:
    """
    The bridge relay loop:
      1. Poll MT5 for pending trade signals
      2. Forward telemetry to Brain API
      3. Execute the Brain's decision on MT5
    """

    def __init__(self, brain_url: str = BRAIN_API_URL) -> None:
        self.brain_url = brain_url.rstrip("/")
        self._running: bool = True
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Start the relay loop."""
        logger.info("Bridge relay starting. Brain API: %s", self.brain_url)

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._shutdown_handler)

        async with httpx.AsyncClient(
            base_url=self.brain_url,
            timeout=httpx.Timeout(5.0),
        ) as client:
            self._client = client
            await self._verify_brain_connection()

            while self._running:
                try:
                    await self._poll_and_relay()
                except Exception as exc:
                    logger.error("Relay error: %s", exc)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info("Bridge relay stopped.")

    async def _verify_brain_connection(self) -> None:
        """Verify Brain API is reachable."""
        assert self._client is not None
        try:
            resp = await self._client.get("/healthz")
            if resp.status_code == 200:
                logger.info("Brain API connected and healthy.")
            else:
                logger.warning("Brain API responded with status %d", resp.status_code)
        except httpx.ConnectError:
            logger.error("Cannot connect to Brain API at %s", self.brain_url)

    async def _poll_and_relay(self) -> None:
        """
        One iteration of the relay loop:
          1. Check MT5 for pending trade signals
          2. If pending, extract telemetry and send to Brain
          3. Execute brain's decision
        """
        # TODO: Replace with real MT5 API polling
        # This is the integration point where we read from the MT5 terminal
        # via the MQL5 bridge or TCP socket.
        telemetry = self._poll_mt5_for_signal()

        if telemetry is None:
            return  # No pending signal

        assert self._client is not None
        decision = await self._send_to_brain(telemetry)

        if decision is not None:
            self._execute_decision(decision, telemetry)

    async def _send_to_brain(self, telemetry: TradeTelemetry) -> BrainDecision | None:
        """Forward telemetry to POST /v1/analyze."""
        assert self._client is not None
        try:
            resp = await self._client.post(
                "/v1/analyze",
                json=telemetry.model_dump(),
            )
            resp.raise_for_status()
            return BrainDecision(**resp.json())
        except httpx.HTTPError as exc:
            logger.error("Brain API request failed: %s", exc)
            # FAIL-SAFE: If Brain is unreachable, block the trade
            return BrainDecision(
                decision="BLOCK",
                risk_score=1.0,
                size_multiplier=0.0,
                is_anomaly=False,
            )

    def _poll_mt5_for_signal(self) -> TradeTelemetry | None:
        """
        Poll MT5 terminal for pending trade signals.

        TODO: Implement real MT5 polling via:
          - MQL5 DLL bridge
          - Named pipe / TCP socket
          - File-based signal exchange

        Returns None if no signal pending.
        """
        # Placeholder — in production, read from MT5 terminal
        return None

    def _execute_decision(
        self,
        decision: BrainDecision,
        telemetry: TradeTelemetry,
    ) -> None:
        """
        Execute the Brain's decision on the MT5 terminal.

        Actions:
          ALLOW      → Let trade execute at original size
          REDUCE_SIZE → Modify lot size by size_multiplier
          BLOCK      → Cancel/reject the trade signal
        """
        if decision.decision == "ALLOW":
            logger.info(
                "ALLOW: Trade at %.2f lots (risk: %.2f%%)",
                telemetry.lots,
                decision.risk_score * 100,
            )
            # TODO: Send ALLOW signal to MT5

        elif decision.decision == "REDUCE_SIZE":
            adjusted_lots = round(telemetry.lots * decision.size_multiplier, 2)
            logger.info(
                "REDUCE_SIZE: %.2f → %.2f lots (risk: %.2f%%, mult: %.2f)",
                telemetry.lots,
                adjusted_lots,
                decision.risk_score * 100,
                decision.size_multiplier,
            )
            # TODO: Modify order size in MT5

        elif decision.decision == "BLOCK":
            logger.warning(
                "BLOCK: Trade rejected (risk: %.2f%%, anomaly: %s)",
                decision.risk_score * 100,
                decision.is_anomaly,
            )
            # TODO: Cancel trade in MT5

    def _shutdown_handler(self, signum: int, frame: object) -> None:
        """Graceful shutdown on SIGINT/SIGTERM."""
        logger.info("Shutdown signal received (%d). Stopping relay...", signum)
        self._running = False


# =============================================================================
# ENTRYPOINT
# =============================================================================

async def main() -> None:
    """Bridge relay entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    relay = MT5BridgeRelay()
    await relay.start()


if __name__ == "__main__":
    asyncio.run(main())
