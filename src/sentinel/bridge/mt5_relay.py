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
        self._mt5_ready = False  # True once MT5 is initialized for live monitoring
        self._monitor_user_id: str = os.getenv("SENTINEL_USER_ID", "")

    async def start(self) -> None:
        logger.info("Bridge relay starting. Brain API: %s", self.brain_url)

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._shutdown_handler)

        # Try to initialize MT5 for live monitoring on startup
        await asyncio.to_thread(self._ensure_mt5_connected)

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

    def _ensure_mt5_connected(self) -> None:
        """Initialize MT5 using vault credentials for live position monitoring."""
        if self._mt5_ready:
            return
        if not self._monitor_user_id:
            return

        try:
            from sentinel.bridge.mt5_history import mt5 as mt5_module
            if mt5_module is None:
                return

            # Check if already initialized
            info = mt5_module.terminal_info()
            if info is not None:
                self._mt5_ready = True
                logger.info("MT5 already initialized for live monitoring.")
                return

            from sentinel.infra.vault_client import vault_manager
            creds = vault_manager.fetch_broker_credentials(self._monitor_user_id)
            login = int(creds["login"])
            server = str(creds["server"])
            password = str(creds["password"])

            initialized = mt5_module.initialize(login=login, server=server, password=password)
            if initialized:
                self._mt5_ready = True
                logger.info(
                    "MT5 initialized for live monitoring: user=%s server=%s",
                    self._monitor_user_id,
                    server,
                )
            else:
                logger.warning("MT5 initialize failed for live monitoring: %s", mt5_module.last_error())
        except Exception as exc:
            logger.warning("Could not initialize MT5 for live monitoring: %s", exc)

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
        Live position monitor for manual traders.
        Reads open MT5 positions directly every poll cycle and derives
        behavioural telemetry (drawdown, losing streak, revenge timer, lot deviation).
        """
        # Re-attempt MT5 init if not ready
        if not self._mt5_ready:
            self._ensure_mt5_connected()

        try:
            from sentinel.bridge.mt5_history import mt5 as mt5_module
        except Exception:
            mt5_module = None

        if mt5_module is None or not self._mt5_ready:
            # Fallback: signal file
            if SIGNAL_FILE is None:
                return None
            signal_path = Path(SIGNAL_FILE)
            if not signal_path.exists():
                return None
            payload = json.loads(signal_path.read_text(encoding="utf-8"))
            signal_path.unlink(missing_ok=True)
            return TradeTelemetry.model_validate(payload)

        try:
            positions = mt5_module.positions_get()
        except Exception as exc:
            logger.debug("MT5 positions_get failed: %s", exc)
            self._mt5_ready = False  # Force re-init next cycle
            return None

        if not positions:
            return None

        pos = positions[0]
        symbol = str(getattr(pos, "symbol", "UNKNOWN"))
        lots = float(getattr(pos, "volume", 0.01))
        open_time_ts = int(getattr(pos, "time", 0))

        account = None
        try:
            account = mt5_module.account_info()
        except Exception:
            pass

        balance = float(getattr(account, "balance", 10000.0)) if account else 10000.0
        equity = float(getattr(account, "equity", balance)) if account else balance
        drawdown_state = max(0.0, round((balance - equity) / max(balance, 1.0), 4))

        import time as _time
        now_ts = int(_time.time())
        revenge_timer = float(max(0, now_ts - open_time_ts)) if open_time_ts > 0 else 0.0

        from datetime import datetime, timezone
        hour_decimal = datetime.now(timezone.utc).hour + datetime.now(timezone.utc).minute / 60.0
        lot_deviation = max(0.0, round(lots / 0.01 - 1.0, 2))

        losing_streak = 0
        try:
            from datetime import timedelta
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=30)
            deals = mt5_module.history_deals_get(start, end)
            if deals:
                for deal in reversed(list(deals)):
                    p = float(getattr(deal, "profit", 0.0))
                    if p < 0:
                        losing_streak += 1
                    elif p > 0:
                        break
        except Exception:
            pass

        user_id = self._monitor_user_id or os.getenv("SENTINEL_USER_ID", "Chllanger-01")

        logger.info("Live position: %s %.2f lots | drawdown=%.2f%% | streak=%d", symbol, lots, drawdown_state * 100, losing_streak)

        return TradeTelemetry(
            user_id=user_id,
            symbol=symbol,
            hour_decimal=hour_decimal,
            losing_streak=losing_streak,
            drawdown_state=drawdown_state,
            lot_deviation=lot_deviation,
            revenge_timer=min(revenge_timer, 3600.0),
            lots=lots,
            rr_ratio=1.0,
            realized_vol_20=0.0,
            trend_momentum=0.0,
        )

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
            "⚠️  BLOCK %s for user %s (risk %.2f%%, anomaly=%s) — Equity Guard triggered!",
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
