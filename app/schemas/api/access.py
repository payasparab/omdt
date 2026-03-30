"""Access request API schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateAccessRequest(BaseModel):
    """Request to create an access request."""

    requester_person_key: str
    requested_role_bundle: str
    justification: str = ""
    resources: list[str] = Field(default_factory=list)
    linear_issue_id: str | None = None


class ApproveAccessRequest(BaseModel):
    """Request to approve an access request."""

    approver: str


class RejectAccessRequest(BaseModel):
    """Request to reject an access request."""

    approver: str
    reason: str = ""


class AccessRequestResponse(BaseModel):
    """Access request record returned by the API."""

    id: str
    requester_person_key: str
    requested_role_bundle: str
    state: str
    policy_evaluated_at: datetime | None = None
    approval_id: str | None = None
    approved_at: datetime | None = None
    provisioning_started_at: datetime | None = None
    provisioned_at: datetime | None = None
    verified_at: datetime | None = None
    closed_at: datetime | None = None
    linear_issue_id: str | None = None
    created_at: datetime
    updated_at: datetime
