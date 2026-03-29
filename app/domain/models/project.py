"""Project domain model (Appendix F)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import CanonicalState


class Project(BaseModel):
    """A project grouping one or more work-items."""

    id: UUID
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: CanonicalState = CanonicalState.NEW
    owner_person_key: str | None = None
    linear_project_id: str | None = None
    created_at: datetime
    updated_at: datetime
