from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from sentinel.api.main import app
from sentinel.bridge import mt5_history
from sentinel.bridge.mt5_relay import MT5BridgeRelay, TradeTelemetry
from sentinel.infra.redis_cache import cache_manager
from sentinel.infra.s3 import model_store
from sentinel.infra import vault_client
from tests.mocks import mt5_simulator


def test_model_store_user_path_mapping() -> None:
    assert model_store.build_model_key("trader-123") == "models/trader-123/brain_v5.joblib"


def test_cache_key_is_scoped_to_user_and_hash() -> None:
    key = cache_manager.build_risk_cache_key(
        "trader-123",
        {"hour_decimal": 14.5, "lots": 1.0},
    )
    assert key.startswith("risk:trader-123:")
    assert len(key.split(":")[2]) == 64


def test_vault_storage_keeps_ciphertext_out_of_memory_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vault_client, "hvac", None)
    manager = vault_client.VaultManager()
    manager.store_broker_credentials(
        user_id="cipher-user",
        server="ICMarkets-Demo",
        login_id=123456,
        password_readonly="super-secret",
    )

    stored = manager._memory_store["cipher-user"]
    assert "password" not in stored
    assert stored["password_ciphertext"] != "super-secret"

    fetched = manager.fetch_broker_credentials("cipher-user")
    assert fetched["password"] == "super-secret"


def test_mt5_history_bridge_handles_blank_history(monkeypatch: object) -> None:
    monkeypatch.setattr(mt5_history, "mt5", mt5_simulator)
    mt5_simulator.shutdown()
    monkeypatch.setenv("SENTINEL_MT5_SIMULATOR_MODE", "blank")

    assert mt5_simulator.initialize(login=98765432, server="ICMarkets-Demo", password="secret")
    bridge = mt5_history.MT5HistoryBridge("http://localhost:8000")
    trades = bridge.fetch_recent_trades(limit=100)
    assert trades == []
    mt5_simulator.shutdown()


def test_mt5_history_bridge_success_shape(monkeypatch: object) -> None:
    monkeypatch.setattr(mt5_history, "mt5", mt5_simulator)
    mt5_simulator.shutdown()
    monkeypatch.setenv("SENTINEL_MT5_SIMULATOR_MODE", "success")
    monkeypatch.setenv("SENTINEL_MT5_SIMULATOR_TRADE_COUNT", "100")

    assert mt5_simulator.initialize(login=98765432, server="ICMarkets-Demo", password="secret")
    bridge = mt5_history.MT5HistoryBridge("http://localhost:8000")
    trades = bridge.fetch_recent_trades(limit=100)
    assert len(trades) == 100
    assert trades[0].symbol in {"EURUSD", "GBPUSD"}
    mt5_simulator.shutdown()


def test_blank_baseline_onboarding_state() -> None:
    client = TestClient(app)

    onboard_response = client.post(
        "/v1/onboard",
        json={
            "user_id": "blank-user",
            "broker_server": "ICMarkets-Demo",
            "account_id": "11111",
            "min_trades": 100,
        },
    )
    assert onboard_response.status_code == 202
    job_id = onboard_response.json()["job_id"]

    data_response = client.post(
        "/v1/onboard/data",
        json={
            "job_id": job_id,
            "user_id": "blank-user",
            "trades": [],
        },
    )
    assert data_response.status_code == 202
    assert data_response.json()["state"] == "blank_baseline"

    profile_response = client.get("/v1/user/blank-user/profile")
    assert profile_response.status_code == 200
    assert profile_response.json()["is_baseline_ready"] is False


class _TimeoutClient:
    async def post(self, path: str, json: dict[str, object], timeout: httpx.Timeout) -> object:
        _ = path, json, timeout
        raise httpx.TimeoutException("simulated timeout")


@pytest.mark.asyncio
async def test_bridge_enforces_fail_safe_timeout() -> None:
    relay = MT5BridgeRelay("http://brain:8000")
    relay._client = _TimeoutClient()  # type: ignore[assignment]
    telemetry = TradeTelemetry(
        user_id="timeout-user",
        symbol="EURUSD",
        hour_decimal=14.5,
        losing_streak=1,
        drawdown_state=120.0,
        lot_deviation=0.4,
        revenge_timer=15.0,
        lots=1.0,
        rr_ratio=2.0,
    )

    decision = await relay._send_to_brain(telemetry)
    assert decision is not None
    assert decision.decision == "BLOCK"
    assert decision.size_multiplier == 0.0
