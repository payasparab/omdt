"""Pydantic models for creating, reading, and querying audit events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AuditEventCreate(BaseModel):
    """Schema for *creating* a new audit event.  Fields that the
    :class:`~app.core.audit.AuditWriter` computes (sequence_number,
    prev_event_hash, event_hash) are omitted.
    """

    event_name: str
    actor_type: Literal["human", "agent", "system"]
    actor_id: str
    initiator_person_key: str | None = None
    correlation_id: str | None = None
    object_type: str
    object_id: str
    before_snapshot_hash: str | None = None
    after_snapshot_hash: str | None = None
    change_summary: str = ""
    tool_name: str | None = None
    approval_id: str | None = None
    source_ip_or_channel: str | None = None


class AuditEventRead(BaseModel):
    """Schema for *reading* a fully sealed audit event."""

    audit_event_id: str
    sequence_number: int
    event_time: datetime
    event_name: str
    actor_type: Literal["human", "agent", "system"]
    actor_id: str
    initiator_person_key: str | None = None
    correlation_id: str | None = None
    object_type: str
    object_id: str
    before_snapshot_hash: str | None = None
    after_snapshot_hash: str | None = None
    change_summary: str = ""
    tool_name: str | None = None
    approval_id: str | None = None
    source_ip_or_channel: str | None = None
    prev_event_hash: str | None = None
    event_hash: str


class AuditQueryFilters(BaseModel):
    """Filters accepted by the audit viewer (§15.8)."""

    project_id: str | None = None
    work_item_id: str | None = None
    actor_id: str | None = None
    event_name: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    after: datetime | None = None
    before: datetime | None = None
    tool_name: str | None = None
    approval_id: str | None = None
    source_ip_or_channel: str | None = None
    environment: str | None = None
