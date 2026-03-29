"""Tests for request middleware (correlation ID)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

_CORR_HEADER = "X-Correlation-ID"


class TestCorrelationIDMiddleware:
    """Ensure every response carries a correlation ID."""

    def test_generates_correlation_id_when_absent(self) -> None:
        response = client.get("/api/v1/health")
        corr_id = response.headers.get(_CORR_HEADER)
        assert corr_id is not None
        # Should be a valid UUID
        uuid.UUID(corr_id)

    def test_echoes_provided_correlation_id(self) -> None:
        custom_id = "test-corr-12345"
        response = client.get(
            "/api/v1/health",
            headers={_CORR_HEADER: custom_id},
        )
        assert response.headers.get(_CORR_HEADER) == custom_id

    def test_different_requests_get_different_ids(self) -> None:
        r1 = client.get("/api/v1/health")
        r2 = client.get("/api/v1/health")
        assert r1.headers[_CORR_HEADER] != r2.headers[_CORR_HEADER]
