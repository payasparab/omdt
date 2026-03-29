"""Artifact domain model (§14.3)."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from app.core.ids import generate_id
from app.domain.enums import ApprovalStatus, ArtifactType


class Artifact(BaseModel):
    """An artifact registered in the artifact registry."""

    id: str = Field(default_factory=generate_id)

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: object) -> object:
        return str(v) if v is not None and not isinstance(v, str) else v

    artifact_type: ArtifactType
    version: str | None = None
    storage_uri: str = Field(min_length=1)
    mime_type: str | None = None
    hash_sha256: str = Field(min_length=64, max_length=64)
    created_by: str | None = None
    source_run_id: str | None = None
    linked_object_type: str | None = None
    linked_object_id: str | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    published_at: datetime | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ArtifactLink(BaseModel):
    """Links an artifact to a parent object (work-item, project, etc.)."""

    id: str = Field(default_factory=generate_id)
    artifact_id: str
    linked_object_type: str
    linked_object_id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
