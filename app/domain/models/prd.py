"""PRD revision domain model (§11.2)."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.core.ids import generate_id
from app.domain.enums import PRDStatus


class PRDRevision(BaseModel):
    """A single revision of a PRD document."""

    id: str = Field(default_factory=generate_id)
    work_item_id: str
    revision_number: int
    content: str = ""
    author: str = ""
    artifact_id: str | None = None
    status: PRDStatus = PRDStatus.DRAFT
    frozen_at: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_frozen(self) -> bool:
        """A PRD is frozen once it has been approved."""
        return self.frozen_at is not None


class FeedbackRequest(BaseModel):
    """A request for feedback on a PRD revision."""

    id: str = Field(default_factory=generate_id)
    prd_revision_id: str
    work_item_id: str
    requested_by: str = ""
    status: str = "pending"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
