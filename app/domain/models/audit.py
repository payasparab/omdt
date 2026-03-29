"""Audit and domain-event models (§15.9)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import ActorType


class AuditEvent(BaseModel):
    """Append-only audit record with tamper-evident hash chain."""

    audit_event_id: UUID
    sequence_number: int
    event_time: datetime
    event_name: str
    actor_type: ActorType
    actor_id: str
    correlation_id: str
    object_type: str
    object_id: str
    change_summary: str
    tool_name: str | None = None
    approval_id: str | None = None
    prev_event_hash: str | None = None
    event_hash: str


class DomainEvent(BaseModel):
    """A typed domain event emitted when state changes."""

    id: UUID
    event_name: str
    aggregate_type: str
    aggregate_id: str
    correlation_id: str
    actor_type: ActorType | None = None
    actor_id: str | None = None
    payload: dict[str, object] = {}
    created_at: datetime
