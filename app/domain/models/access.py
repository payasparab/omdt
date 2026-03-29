"""Access provisioning domain models (§16.5–16.6)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import AccessRequestState


class AccessRequest(BaseModel):
    """A request for warehouse / tool access."""

    id: UUID
    requester_person_key: str
    requested_role_bundle: str
    state: AccessRequestState = AccessRequestState.REQUESTED
    policy_evaluated_at: datetime | None = None
    approval_id: UUID | None = None
    approved_at: datetime | None = None
    provisioning_started_at: datetime | None = None
    provisioned_at: datetime | None = None
    verified_at: datetime | None = None
    closed_at: datetime | None = None
    linear_issue_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RoleBundle(BaseModel):
    """A predefined bundle of permissions."""

    name: str
    allowed_databases: list[str] = []
    allowed_schemas: list[str] = []
    warehouse_defaults: str | None = None
    temp_object_rights: bool = False
    grant_prerequisites: list[str] = []
    approval_threshold: str = "lead"
    expiration_policy: str | None = None
    review_cadence: str | None = None
