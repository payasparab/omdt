"""Approval request domain model."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.ids import generate_id
from app.domain.enums import ApprovalStatus


class ApprovalRequest(BaseModel):
    """An approval request for a guarded action."""

    id: str = Field(default_factory=generate_id)
    work_item_id: str
    action: str
    requester: str
    approvers: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decision_reason: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    decided_at: datetime | None = None
