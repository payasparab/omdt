"""Audit API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    """Single audit event returned by the API."""

    id: str
    event_type: str
    actor: str
    correlation_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    action: str | None = None
    detail: dict[str, object] = Field(default_factory=dict)
    timestamp: datetime


class AuditQueryRequest(BaseModel):
    """Query parameters for searching audit events."""

    actor: str | None = None
    event_type: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    correlation_id: str | None = None
    from_timestamp: datetime | None = None
    to_timestamp: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
