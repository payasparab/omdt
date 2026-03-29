"""Tests for API common schema models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.api.common import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    ReadinessCheck,
    ReadinessResponse,
    SuccessResponse,
)


class TestErrorDetail:
    def test_minimal(self) -> None:
        d = ErrorDetail(message="something went wrong")
        assert d.message == "something went wrong"
        assert d.field is None

    def test_with_field(self) -> None:
        d = ErrorDetail(field="body.name", message="required", code="missing")
        assert d.field == "body.name"
        assert d.code == "missing"


class TestErrorResponse:
    def test_defaults(self) -> None:
        r = ErrorResponse(error="bad_request")
        assert r.error == "bad_request"
        assert r.errors == []
        assert isinstance(r.timestamp, datetime)

    def test_with_correlation_id(self) -> None:
        r = ErrorResponse(error="not_found", correlation_id="abc-123")
        assert r.correlation_id == "abc-123"


class TestHealthResponse:
    def test_required_fields(self) -> None:
        h = HealthResponse(version="0.1.0", environment="test", status="ok")
        assert h.service == "omdt"
        assert h.version == "0.1.0"


class TestReadinessResponse:
    def test_with_checks(self) -> None:
        checks = [ReadinessCheck(name="db", status="ok")]
        r = ReadinessResponse(version="0.1.0", status="ok", checks=checks)
        assert len(r.checks) == 1
        assert r.checks[0].name == "db"


class TestSuccessResponse:
    def test_default(self) -> None:
        s = SuccessResponse()
        assert s.success is True
        assert s.message is None


class TestPaginatedResponse:
    def test_with_items(self) -> None:
        p = PaginatedResponse[str](items=["a", "b"], total=2)
        assert p.items == ["a", "b"]
        assert p.total == 2
        assert p.page == 1
        assert p.has_more is False

    def test_has_more(self) -> None:
        p = PaginatedResponse[int](items=[1], total=100, page=1, page_size=1, has_more=True)
        assert p.has_more is True
