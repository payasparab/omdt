"""Audit events API router."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.core.audit import get_audit_log
from app.schemas.api.audit import AuditEventResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventResponse])
async def list_audit_events(
    actor: str | None = None,
    event_type: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    correlation_id: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AuditEventResponse]:
    """Query audit events with filters per §15.8."""
    log = get_audit_log()

    # Apply filters
    if actor:
        log = [r for r in log if r.get("actor_id") == actor]
    if event_type:
        log = [r for r in log if r.get("event_name") == event_type]
    if target_type:
        log = [r for r in log if r.get("object_type") == target_type]
    if target_id:
        log = [r for r in log if r.get("object_id") == target_id]
    if correlation_id:
        log = [r for r in log if r.get("correlation_id") == correlation_id]
    if from_timestamp:
        log = [r for r in log if r.get("event_time", "") >= from_timestamp.isoformat()]
    if to_timestamp:
        log = [r for r in log if r.get("event_time", "") <= to_timestamp.isoformat()]

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_items = log[start:end]

    return [
        AuditEventResponse(
            id=r.get("correlation_id", ""),
            event_type=r.get("event_name", ""),
            actor=r.get("actor_id", ""),
            correlation_id=r.get("correlation_id"),
            target_type=r.get("object_type"),
            target_id=r.get("object_id"),
            action=r.get("event_name"),
            detail={"change_summary": r.get("change_summary", "")},
            timestamp=datetime.fromisoformat(r["event_time"]) if r.get("event_time") else datetime.min,
        )
        for r in page_items
    ]
