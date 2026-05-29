from __future__ import annotations

import asyncio
import importlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from sentinel.domain.models import HistoricalTrade, OnboardingDataSubmission
from sentinel.infra.vault_client import vault_manager


def _load_mt5_module() -> Any:
    module_name = os.getenv("SENTINEL_MT5_MODULE")
    if module_name:
        return importlib.import_module(module_name)

    try:
        import MetaTrader5 as live_mt5
    except ImportError:  # pragma: no cover - exercised only on MT5-capable hosts
        live_mt5 = None  # type: ignore[assignment]
    return live_mt5


mt5 = _load_mt5_module()

logger = logging.getLogger(__name__)


class MT5HistoryBridge:
    """Bridge-side MT5 history collector and onboarding callback client."""

    def __init__(self, api_base_url: str | None = None) -> None:
        self.api_base_url = (api_base_url or os.getenv("BRAIN_API_URL", "http://localhost:8000")).rstrip(
            "/"
        )
        self.lookback_days = int(os.getenv("MT5_HISTORY_LOOKBACK_DAYS", "180"))

    def _require_mt5(self) -> Any:
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 Python package is required for MT5 history collection."
            )
        return mt5

    def verify_credentials(
        self,
        user_id: str,
        broker_server: str,
        account_id: str,
    ) -> dict[str, Any]:
        mt5_module = self._require_mt5()
        credentials = vault_manager.fetch_broker_credentials(user_id)

        login = int(credentials["login"])
        server = str(credentials["server"])
        password = str(credentials["password"])

        if server != broker_server or str(login) != account_id:
            raise RuntimeError("Vault credentials do not match the onboarding request.")

        portable_path = f"C:\\Sentinel\\Users\\{user_id}\\terminal64.exe"
        if os.path.exists(portable_path) and os.path.getsize(portable_path) > 1024 * 1024:
            logger.info("Initializing MT5 in portable mode at %s", portable_path)
            initialized = mt5_module.initialize(
                path=portable_path,
                login=login,
                server=server,
                password=password,
                portable=True
            )
        else:
            logger.info("Initializing MT5 in standard mode (portable path absent or dummy mock)")
            initialized = mt5_module.initialize(login=login, server=server, password=password)

        if not initialized:
            raise RuntimeError(f"MT5 initialize failed: {mt5_module.last_error()}")

        account = mt5_module.account_info()
        if account is None:
            raise RuntimeError("MT5 account_info returned no result after login.")

        logger.info("Verified MT5 credentials for user %s against %s", user_id, broker_server)
        return credentials

    def _derive_rr_ratio(self, position_id: int, open_price: float) -> float:
        mt5_module = self._require_mt5()
        try:
            orders = mt5_module.history_orders_get(position=position_id)
        except Exception:
            orders = None

        if not orders:
            return 1.0

        for order in orders:
            stop_loss = float(getattr(order, "sl", 0.0) or 0.0)
            take_profit = float(getattr(order, "tp", 0.0) or 0.0)
            risk = abs(open_price - stop_loss)
            reward = abs(take_profit - open_price)
            if risk > 0 and reward > 0:
                return round(reward / risk, 4)
        return 1.0

    def fetch_recent_trades(self, limit: int = 100) -> list[HistoricalTrade]:
        mt5_module = self._require_mt5()
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        deals = mt5_module.history_deals_get(start, end)
        if deals is None:
            raise RuntimeError(f"history_deals_get failed: {mt5_module.last_error()}")
        if len(deals) == 0:
            logger.info("MT5 returned no historical deals. Producing blank baseline payload.")
            return []

        grouped: dict[int, list[Any]] = {}
        for deal in deals:
            position_id = int(getattr(deal, "position_id", 0) or 0)
            if position_id == 0:
                continue
            grouped.setdefault(position_id, []).append(deal)

        trades: list[HistoricalTrade] = []
        for position_id, position_deals in grouped.items():
            ordered = sorted(
                position_deals,
                key=lambda item: (
                    int(getattr(item, "time_msc", 0) or 0),
                    int(getattr(item, "time", 0) or 0),
                ),
            )
            if len(ordered) < 2:
                continue

            open_deal = ordered[0]
            close_deal = ordered[-1]
            open_time = datetime.fromtimestamp(int(getattr(open_deal, "time")), tz=timezone.utc)
            close_time = datetime.fromtimestamp(int(getattr(close_deal, "time")), tz=timezone.utc)
            if close_time <= open_time:
                continue

            open_price = float(getattr(open_deal, "price", 0.0) or 0.0)
            close_price = float(getattr(close_deal, "price", 0.0) or 0.0)
            lots = float(getattr(open_deal, "volume", 0.0) or 0.0)
            if open_price <= 0 or close_price <= 0 or lots <= 0:
                continue

            pnl = sum(
                float(getattr(item, "profit", 0.0) or 0.0)
                + float(getattr(item, "swap", 0.0) or 0.0)
                + float(getattr(item, "commission", 0.0) or 0.0)
                + float(getattr(item, "fee", 0.0) or 0.0)
                for item in ordered
            )
            symbol = str(getattr(open_deal, "symbol", "UNKNOWN") or "UNKNOWN")

            trades.append(
                HistoricalTrade(
                    symbol=symbol,
                    open_time=open_time,
                    close_time=close_time,
                    pnl=round(pnl, 4),
                    lots=lots,
                    open_price=open_price,
                    close_price=close_price,
                    rr_ratio=self._derive_rr_ratio(position_id, open_price),
                )
            )

        recent = sorted(trades, key=lambda trade: trade.close_time)[-limit:]
        return recent

    async def post_onboarding_data(
        self,
        job_id: str,
        user_id: str,
        trades: list[HistoricalTrade],
    ) -> None:
        submission = OnboardingDataSubmission(job_id=job_id, user_id=user_id, trades=trades)
        async with httpx.AsyncClient(base_url=self.api_base_url, timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(
                "/v1/onboard/data",
                json=submission.model_dump(mode="json"),
            )
            response.raise_for_status()

    async def post_onboarding_failure(
        self,
        job_id: str,
        user_id: str,
        error_message: str,
    ) -> None:
        """Mark the onboarding job as failed by posting a failure state to the Brain API."""
        try:
            async with httpx.AsyncClient(base_url=self.api_base_url, timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(
                    "/v1/onboard/fail",
                    json={"job_id": job_id, "user_id": user_id, "error": error_message},
                )
                if response.status_code == 404:
                    # Endpoint doesn't exist — fall back to submitting empty trades which will complete as blank_baseline
                    logger.warning("No /v1/onboard/fail endpoint. Submitting empty history as fallback.")
                    await self.post_onboarding_data(job_id, user_id, [])
                else:
                    response.raise_for_status()
        except Exception as exc:
            logger.error("Could not post failure for job %s: %s — submitting empty trades as fallback", job_id, exc)
            try:
                await self.post_onboarding_data(job_id, user_id, [])
            except Exception:
                logger.exception("Even empty-trade fallback failed for job %s", job_id)

    async def collect_and_submit(
        self,
        job_id: str,
        user_id: str,
        broker_server: str,
        account_id: str,
        limit: int = 100,
    ) -> None:
        """Collect MT5 history and submit to the Brain API.

        Handles three scenarios:
        - MT5 module not installed → submit empty trades (bootstrap mode)
        - MT5 auth failure → submit empty trades with warning logged
        - MT5 auth success → fetch trades and submit
        """
        if mt5 is None:
            logger.warning(
                "MetaTrader5 module not available on this host. "
                "Submitting empty history for job %s (user %s) — bootstrap onboarding.",
                job_id,
                user_id,
            )
            await self.post_onboarding_data(job_id, user_id, [])
            return

        initialized = False
        try:
            logger.info("Verifying MT5 credentials for job %s user %s...", job_id, user_id)
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        self.verify_credentials,
                        user_id,
                        broker_server,
                        account_id,
                    ),
                    timeout=15.0,
                )
                initialized = True
            except asyncio.TimeoutError:
                logger.warning(
                    "MT5 credential verification timed out after 15s for job %s (user %s). "
                    "Submitting empty history — bootstrap onboarding will proceed.",
                    job_id,
                    user_id,
                )
                await self.post_onboarding_data(job_id, user_id, [])
                return
            except Exception as auth_exc:
                logger.warning(
                    "MT5 credential verification failed for job %s (user %s): %s. "
                    "Submitting empty history — bootstrap onboarding will proceed.",
                    job_id,
                    user_id,
                    auth_exc,
                )
                await self.post_onboarding_data(job_id, user_id, [])
                return

            logger.info("Fetching trade history for job %s user %s...", job_id, user_id)
            trades = await asyncio.wait_for(
                asyncio.to_thread(self.fetch_recent_trades, limit),
                timeout=30.0,
            )
            logger.info("Fetched %d trades for job %s. Submitting...", len(trades), job_id)
            await self.post_onboarding_data(job_id, user_id, trades)
            logger.info("Successfully submitted %d trades for job %s.", len(trades), job_id)
        finally:
            if initialized:
                try:
                    await asyncio.to_thread(mt5.shutdown)
                except Exception:
                    logger.exception("Failed to shut down MT5 cleanly")

