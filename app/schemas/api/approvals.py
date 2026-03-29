"""Approvals API schemas — required by existing approvals router."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalDecisionRequest(BaseModel):
    """Request to approve or reject an approval."""

    actor: str = Field(..., description="Person key of the decision-maker")
    reason: str | None = None


class ApprovalResponse(BaseModel):
    """Approval record returned by the API."""

    id: str
    work_item_id: str
    action: str
    requester: str
    approvers: list[str] = Field(default_factory=list)
    status: str
    decided_by: str | None = None
    decision_reason: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None
