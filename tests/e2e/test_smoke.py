"""E2E smoke test — start the FastAPI app and verify /health returns 200."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestSmoke:
    """Minimal smoke tests that exercise the live application."""

    def test_health_endpoint_returns_200(self) -> None:
        from app.api.main import app

        client = TestClient(app)
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_readiness_endpoint_returns_200(self) -> None:
        from app.api.main import app

        client = TestClient(app)
        response = client.get("/api/v1/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("ok", "degraded")
        assert "checks" in body
