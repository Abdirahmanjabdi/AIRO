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


class TestAnalyzeEndpoint:
    """Tests for POST /v1/analyze."""

    def test_valid_analyze_request(self, client: TestClient) -> None:
        payload = {
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
        assert data["state"] == "pending"
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


class TestUserProfile:
    """Tests for GET /v1/user/{user_id}/profile."""

    def test_get_profile(self, client: TestClient) -> None:
        resp = client.get("/v1/user/test-user-001/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test-user-001"
        assert "trade_count" in data
        assert "is_baseline_ready" in data
