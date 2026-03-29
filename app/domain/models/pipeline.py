"""Pipeline domain models (§17.2–17.3)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import PipelineType


class PipelineDefinition(BaseModel):
    """Metadata for a managed pipeline."""

    id: UUID
    pipeline_key: str = Field(min_length=1)
    description: str | None = None
    owner_person_key: str | None = None
    pipeline_type: PipelineType
    inputs: list[str] = []
    outputs: list[str] = []
    upstream_dependencies: list[str] = []
    schedule: str | None = None
    environment_targets: list[str] = []
    quality_checks: list[dict[str, object]] = []
    rollback_notes: str | None = None
    linked_prd_artifact_id: UUID | None = None
    linked_linear_issue_id: str | None = None
    alert_rules: list[dict[str, object]] = []
    created_at: datetime
    updated_at: datetime


class PipelineRun(BaseModel):
    """A single execution of a pipeline."""

    id: UUID
    pipeline_definition_id: UUID
    status: str
    triggered_by: str | None = None
    correlation_id: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
