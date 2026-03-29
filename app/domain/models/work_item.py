"""Work-item domain model (§14.2)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.ids import generate_id
from app.domain.enums import CanonicalState, Priority, SourceChannel, WorkItemType


class WorkItem(BaseModel):
    """Canonical work-item as described in §14.2."""

    id: str = Field(default_factory=generate_id)

    @field_validator("id", "project_id", "latest_prd_revision_id", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: object) -> object:
        return str(v) if v is not None and not isinstance(v, str) else v
    project_id: str | None = None
    title: str = Field(min_length=1)
    description: str | None = None
    work_type: WorkItemType = WorkItemType.UNKNOWN_NEEDS_CLARIFICATION
    canonical_state: CanonicalState = CanonicalState.NEW
    priority: Priority = Priority.MEDIUM
    source_channel: SourceChannel | None = None
    source_external_id: str | None = None
    requester_person_key: str | None = None
    owner_person_key: str | None = None
    route_key: str | None = None
    risk_level: str | None = None
    due_at: datetime | None = None
    requires_approval: bool = False
    latest_prd_revision_id: str | None = None
    linear_issue_id: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    closed_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)
