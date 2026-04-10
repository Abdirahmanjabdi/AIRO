from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from sentinel.api.main import app
from sentinel.bridge import mt5_history
from sentinel.bridge.mt5_history import MT5HistoryBridge
from sentinel.infra.s3 import model_store
from sentinel.infra.vault_client import vault_manager
from tests.mocks import mt5_simulator


def main() -> None:
    os.environ["SENTINEL_MT5_SIMULATOR_MODE"] = "success"
    os.environ["SENTINEL_MT5_SIMULATOR_TRADE_COUNT"] = "100"
    mt5_history.mt5 = mt5_simulator
    mt5_simulator.shutdown()
    use_live_infra = os.getenv("SENTINEL_USE_LIVE_INFRA") == "1"
    if not use_live_infra:
        model_store.client = None
        model_store._memory_models.clear()
        vault_manager.client = None
        vault_manager._memory_store.clear()

    user_id = "canary-user-001"
    bridge = MT5HistoryBridge("http://localhost:8000")

    with TestClient(app) as client:
        whop = client.post(
            "/v1/webhooks/whop",
            json={
                "event": "membership.activated",
                "user_id": user_id,
                "email": "canary@example.com",
                "plan": "pro",
            },
        )
        print("STEP whop", json.dumps(whop.json(), sort_keys=True))

        credentials = client.post(
            "/v1/credentials",
            json={
                "user_id": user_id,
                "broker_server": "ICMarkets-Demo",
                "account_id": "98765432",
                "read_only_password": "mock-password",
            },
        )
        print("STEP credentials", json.dumps(credentials.json(), sort_keys=True))
        if use_live_infra:
            stored_record = vault_manager.client.secrets.kv.v2.read_secret_version(  # type: ignore[union-attr]
                mount_point=vault_manager.kv_mount_point,
                path=f"users/{user_id}/mt5",
                raise_on_deleted_version=True,
            )["data"]["data"]
        else:
            stored_record = vault_manager._memory_store[user_id]
        print(
            "STEP vault_record",
            json.dumps(
                {
                    "keys": sorted(stored_record.keys()),
                    "ciphertext_prefix": stored_record["password_ciphertext"][:18],
                    "plaintext_present": "password" in stored_record,
                },
                sort_keys=True,
            ),
        )

        onboard = client.post(
            "/v1/onboard",
            json={
                "user_id": user_id,
                "broker_server": "ICMarkets-Demo",
                "account_id": "98765432",
                "min_trades": 100,
            },
        )
        onboard_json = onboard.json()
        print("STEP onboard", json.dumps(onboard_json, sort_keys=True))

        bridge.verify_credentials(user_id, "ICMarkets-Demo", "98765432")
        trades = bridge.fetch_recent_trades(limit=100)
        print(
            "STEP mt5_history",
            json.dumps(
                {
                    "trade_count": len(trades),
                    "first_symbol": trades[0].symbol,
                    "last_symbol": trades[-1].symbol,
                },
                sort_keys=True,
            ),
        )

        data_resp = client.post(
            "/v1/onboard/data",
            json={
                "job_id": onboard_json["job_id"],
                "user_id": user_id,
                "trades": [trade.model_dump(mode="json") for trade in trades],
            },
        )
        print("STEP onboard_data", json.dumps(data_resp.json(), sort_keys=True))

        status_resp = client.get(f"/v1/onboard/{onboard_json['job_id']}")
        print("STEP final_status", json.dumps(status_resp.json(), sort_keys=True))

        profile_resp = client.get(f"/v1/user/{user_id}/profile")
        profile = profile_resp.json()
        print("STEP profile", json.dumps(profile, sort_keys=True))

        model_key = model_store.build_model_key(user_id)
        payload = {
            "model_key": model_key,
            "model_exists": model_store.model_exists(model_key),
        }
        if use_live_infra:
            payload["storage_backend"] = "minio"
        else:
            payload["storage_backend"] = "memory"
            payload["stored_objects"] = sorted(model_store._memory_models.keys())
        print("STEP s3", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
