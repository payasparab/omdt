"""Common API response schemas used across all endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Single error detail within an error response."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: str
    detail: str | None = None
    errors: list[ErrorDetail] = Field(default_factory=list)
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(BaseModel):
    """Health check response."""

    service: str = "omdt"
    version: str
    environment: str
    status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReadinessCheck(BaseModel):
    """Individual dependency readiness check."""

    name: str
    status: str  # "ok" | "degraded" | "unavailable"
    latency_ms: float | None = None
    message: str | None = None


class ReadinessResponse(BaseModel):
    """Readiness probe response with dependency checks."""

    service: str = "omdt"
    version: str
    status: str
    checks: list[ReadinessCheck] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SuccessResponse(BaseModel):
    """Generic success response wrapper."""

    success: bool = True
    message: str | None = None
    correlation_id: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response wrapper."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50
    has_more: bool = False
