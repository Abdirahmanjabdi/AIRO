"""
Integration Tests — Brain API
================================
Tests the FastAPI application end-to-end using TestClient.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sentinel.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with startup lifespan."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """Tests for K8s probe endpoints."""

    def test_liveness(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_readiness(self, client: TestClient) -> None:
        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ready", "not_ready")
        assert "model_loaded" in data
        assert "vault_connected" in data
        assert "vault_required" in data


class TestAnalyzeEndpoint:
    """Tests for POST /v1/analyze."""

    def test_valid_analyze_request(self, client: TestClient) -> None:
        payload = {
            "user_id": "test-user-001",
            "hour_decimal": 14.5,
            "losing_streak": 2,
            "drawdown_state": 100.0,
            "lot_deviation": 0.5,
            "revenge_timer": 30.0,
            "lots": 1.0,
            "rr_ratio": 2.0,
            "realized_vol_20": 0.01,
            "trend_momentum": 0.005,
        }
        resp = client.post("/v1/analyze", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert data["decision"] in ("ALLOW", "BLOCK", "REDUCE_SIZE")
        assert 0.0 <= data["risk_score"] <= 1.0
        assert 0.0 <= data["size_multiplier"] <= 1.0
        assert "latency_ms" in data
        assert "explanation" in data

    def test_invalid_fields_rejected(self, client: TestClient) -> None:
        payload = {
            "user_id": "test-user-001",
            "hour_decimal": 25.0,  # Invalid
            "losing_streak": 0,
            "drawdown_state": 0.0,
            "lot_deviation": 0.0,
            "revenge_timer": 60.0,
            "lots": 1.0,
            "rr_ratio": 2.0,
        }
        resp = client.post("/v1/analyze", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_missing_required_fields(self, client: TestClient) -> None:
        resp = client.post("/v1/analyze", json={})
        assert resp.status_code == 422


class TestOnboardingEndpoint:
    """Tests for POST /v1/onboard (async 202 pattern)."""

    def test_onboard_returns_202(self, client: TestClient) -> None:
        payload = {
            "user_id": "test-user-001",
            "broker_server": "ICMarkets-Demo",
            "account_id": "12345678",
            "min_trades": 50,
        }
        resp = client.post("/v1/onboard", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["state"] in ("pending", "pulling_history")
        assert "job_id" in data
        assert data["user_id"] == "test-user-001"

    def test_onboard_status_poll(self, client: TestClient) -> None:
        # Start onboarding
        payload = {
            "user_id": "test-user-002",
            "broker_server": "ICMarkets-Demo",
            "account_id": "12345679",
        }
        resp = client.post("/v1/onboard", json=payload)
        job_id = resp.json()["job_id"]

        # Poll status
        resp = client.get(f"/v1/onboard/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["job_id"] == job_id

    def test_onboard_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/v1/onboard/nonexistent-job-id")
        assert resp.status_code == 404

    def test_onboard_min_trades_validation(self, client: TestClient) -> None:
        payload = {
            "user_id": "test-user-003",
            "broker_server": "ICMarkets-Demo",
            "account_id": "12345680",
            "min_trades": 10,  # Below minimum
        }
        resp = client.post("/v1/onboard", json=payload)
        assert resp.status_code == 422


class TestControlPlane:
    """Tests for credential vaulting and provisioning webhooks."""

    def test_credentials_are_stored_via_vault_route(self, client: TestClient) -> None:
        payload = {
            "user_id": "test-user-credentials",
            "broker_server": "ICMarkets-Demo",
            "account_id": "11223344",
            "read_only_password": "read-only-secret",
        }
        resp = client.post("/v1/credentials", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == payload["user_id"]
        assert data["stored"] is True
        assert data["vault_path"].endswith(f"/users/{payload['user_id']}/mt5")

    def test_whop_webhook_generates_api_key_and_helm_command(self, client: TestClient) -> None:
        payload = {
            "event": "membership.activated",
            "user_id": "whop-user-001",
            "email": "user@example.com",
            "plan": "pro",
        }
        resp = client.post("/v1/webhooks/whop", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["user_id"] == payload["user_id"]
        assert data["api_key"].startswith("sz_live_")
        assert data["api_key_last4"] == data["api_key"][-4:]
        assert data["helm_release"].startswith("sentinel-pod-whop-user-001")
        assert "helm upgrade --install" in data["helm_command"]
        assert "--set-string env.SENTINEL_USER_ID=whop-user-001" in data["helm_command"]


class TestUserProfile:
    """Tests for GET /v1/user/{user_id}/profile."""

    def test_get_profile(self, client: TestClient) -> None:
        resp = client.get("/v1/user/test-user-001/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test-user-001"
        assert "trade_count" in data
        assert "is_baseline_ready" in data


class TestDashboardReads:
    """Tests for dashboard summary and audit feeds."""

    def test_user_audits_feed(self, client: TestClient) -> None:
        payload = {
            "user_id": "dashboard-user-001",
            "symbol": "EURUSD",
            "hour_decimal": 10.25,
            "losing_streak": 1,
            "drawdown_state": 8.0,
            "lot_deviation": 0.18,
            "revenge_timer": 12.0,
            "lots": 0.3,
            "rr_ratio": 1.8,
            "realized_vol_20": 0.015,
            "trend_momentum": 0.12,
        }
        analyze = client.post("/v1/analyze", json=payload)
        assert analyze.status_code == 200

        audits = client.get("/v1/user/dashboard-user-001/audits")
        assert audits.status_code == 200
        data = audits.json()
        assert len(data) >= 1
        assert data[0]["user_id"] == "dashboard-user-001"
        assert data[0]["symbol"] == "EURUSD"

    def test_user_dashboard_summary(self, client: TestClient) -> None:
        resp = client.get("/v1/user/dashboard-user-001/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "dashboard-user-001"
        assert "profile" in data
        assert "recent_audits" in data
        assert "decision_counts" in data

    def test_admin_overview(self, client: TestClient) -> None:
        resp = client.get("/v1/admin/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "users" in data
        assert "recent_jobs" in data
