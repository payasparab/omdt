"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """GET /api/v1/health."""

    def test_returns_200(self) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_response_structure(self) -> None:
        data = client.get("/api/v1/health").json()
        assert data["service"] == "omdt"
        assert data["version"] == "0.1.0"
        assert data["status"] == "ok"
        assert "environment" in data
        assert "timestamp" in data

    def test_environment_default(self) -> None:
        data = client.get("/api/v1/health").json()
        assert data["environment"] == "development"


class TestReadinessEndpoint:
    """GET /api/v1/health/ready."""

    def test_returns_200(self) -> None:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200

    def test_includes_dependency_checks(self) -> None:
        data = client.get("/api/v1/health/ready").json()
        assert "checks" in data
        assert len(data["checks"]) >= 2
        names = {c["name"] for c in data["checks"]}
        assert "database" in names
        assert "redis" in names

    def test_overall_status(self) -> None:
        data = client.get("/api/v1/health/ready").json()
        assert data["status"] in ("ok", "degraded")
