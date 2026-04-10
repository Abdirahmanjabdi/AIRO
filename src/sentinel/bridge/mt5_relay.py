"""
Sentinel Pod MT5 Bridge Relay
=============================
Relay-only bridge for MT5 connectivity, onboarding history pulls,
and live decision forwarding to the Brain API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from pathlib import Path

import httpx
from pydantic import BaseModel

from sentinel.bridge.mt5_history import MT5HistoryBridge
from sentinel.infra.redis_cache import cache_manager

logger = logging.getLogger(__name__)

BRAIN_API_URL: str = os.getenv("BRAIN_API_URL", "http://localhost:8000")
POLL_INTERVAL_SECONDS: float = float(os.getenv("POLL_INTERVAL", "0.5"))
DECISION_TIMEOUT_SECONDS: float = float(os.getenv("BRAIN_DECISION_TIMEOUT_SECONDS", "0.5"))
SIGNAL_FILE: str | None = os.getenv("MT5_SIGNAL_FILE")


class TradeTelemetry(BaseModel):
    user_id: str
    symbol: str = "UNKNOWN"
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
    decision: str
    risk_score: float
    size_multiplier: float
    is_anomaly: bool
    latency_ms: float | None = None


class MT5BridgeRelay:
    """
    Bridge loop responsibilities:
      1. Process onboarding commands from Redis.
      2. Forward live telemetry to the Brain API.
      3. Execute returned decisions on the MT5-side transport.
    """

    def __init__(self, brain_url: str = BRAIN_API_URL) -> None:
        self.brain_url = brain_url.rstrip("/")
        self._running = True
        self._client: httpx.AsyncClient | None = None
        self._history_bridge = MT5HistoryBridge(self.brain_url)

    async def start(self) -> None:
        logger.info("Bridge relay starting. Brain API: %s", self.brain_url)

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
                    await self._process_onboarding_jobs()
                    await self._poll_and_relay()
                except Exception as exc:
                    logger.error("Relay error: %s", exc, exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info("Bridge relay stopped.")

    async def _verify_brain_connection(self) -> None:
        assert self._client is not None
        response = await self._client.get("/healthz")
        response.raise_for_status()
        logger.info("Brain API connected and healthy.")

    async def _process_onboarding_jobs(self) -> None:
        command = await cache_manager.dequeue_onboarding_job(timeout_seconds=1)
        if command is None:
            return

        user_id = str(command["user_id"])
        await cache_manager.set_heartbeat(user_id)
        logger.info("Processing onboarding job %s for user %s", command["job_id"], user_id)
        await self._history_bridge.collect_and_submit(
            job_id=str(command["job_id"]),
            user_id=user_id,
            broker_server=str(command["broker_server"]),
            account_id=str(command["account_id"]),
            limit=int(command.get("min_trades", 100)),
        )

    async def _poll_and_relay(self) -> None:
        telemetry = self._poll_mt5_for_signal()
        if telemetry is None:
            return

        assert self._client is not None
        await cache_manager.set_heartbeat(telemetry.user_id)
        decision = await self._send_to_brain(telemetry)
        if decision is not None:
            self._execute_decision(decision, telemetry)

    async def _send_to_brain(self, telemetry: TradeTelemetry) -> BrainDecision | None:
        assert self._client is not None
        started_at = time.perf_counter()
        try:
            response = await self._client.post(
                "/v1/analyze",
                json=telemetry.model_dump(),
                timeout=httpx.Timeout(DECISION_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            decision = BrainDecision(**response.json())
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            model_latency_ms = decision.latency_ms or 0.0
            if elapsed_ms > DECISION_TIMEOUT_SECONDS * 1000 or model_latency_ms > 500.0:
                logger.warning(
                    "Decision loop exceeded budget for user %s: round_trip=%.2fms model=%.2fms",
                    telemetry.user_id,
                    elapsed_ms,
                    model_latency_ms,
                )
                return BrainDecision(
                    decision="BLOCK",
                    risk_score=1.0,
                    size_multiplier=0.0,
                    is_anomaly=False,
                    latency_ms=elapsed_ms,
                )
            return decision
        except httpx.TimeoutException:
            logger.error("Brain API decision timed out after %.0fms", DECISION_TIMEOUT_SECONDS * 1000)
            return BrainDecision(
                decision="BLOCK",
                risk_score=1.0,
                size_multiplier=0.0,
                is_anomaly=False,
                latency_ms=DECISION_TIMEOUT_SECONDS * 1000,
            )
        except httpx.HTTPError as exc:
            logger.error("Brain API request failed: %s", exc)
            return BrainDecision(
                decision="BLOCK",
                risk_score=1.0,
                size_multiplier=0.0,
                is_anomaly=False,
                latency_ms=(time.perf_counter() - started_at) * 1000,
            )

    def _poll_mt5_for_signal(self) -> TradeTelemetry | None:
        """
        Reads live trade telemetry from a sidecar-produced JSON signal file.
        This keeps the bridge as a transport layer while allowing broker-side
        tooling to hand off pre-computed telemetry to the Brain API.
        """

        if SIGNAL_FILE is None:
            return None

        signal_path = Path(SIGNAL_FILE)
        if not signal_path.exists():
            return None

        payload = json.loads(signal_path.read_text(encoding="utf-8"))
        signal_path.unlink(missing_ok=True)
        return TradeTelemetry.model_validate(payload)

    def _execute_decision(
        self,
        decision: BrainDecision,
        telemetry: TradeTelemetry,
    ) -> None:
        if decision.decision == "ALLOW":
            logger.info(
                "ALLOW %s for user %s at %.2f lots",
                telemetry.symbol,
                telemetry.user_id,
                telemetry.lots,
            )
            return

        if decision.decision == "REDUCE_SIZE":
            adjusted_lots = round(telemetry.lots * decision.size_multiplier, 2)
            logger.info(
                "REDUCE_SIZE %s for user %s: %.2f -> %.2f lots",
                telemetry.symbol,
                telemetry.user_id,
                telemetry.lots,
                adjusted_lots,
            )
            return

        logger.warning(
            "BLOCK %s for user %s (risk %.2f%%, anomaly=%s)",
            telemetry.symbol,
            telemetry.user_id,
            decision.risk_score * 100,
            decision.is_anomaly,
        )

    def _shutdown_handler(self, signum: int, frame: object) -> None:
        logger.info("Shutdown signal received (%d). Stopping relay...", signum)
        self._running = False


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    relay = MT5BridgeRelay()
    await relay.start()


if __name__ == "__main__":
    asyncio.run(main())
