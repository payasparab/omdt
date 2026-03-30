"""Pipeline API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreatePipelineRequest(BaseModel):
    """Request to create a pipeline definition."""

    pipeline_key: str = Field(..., min_length=1)
    pipeline_type: str
    description: str | None = None
    owner_person_key: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    upstream_dependencies: list[str] = Field(default_factory=list)
    schedule: str | None = None
    environment_targets: list[str] = Field(default_factory=list)
    quality_checks: list[dict[str, Any]] = Field(default_factory=list)
    rollback_notes: str | None = None
    linked_prd_artifact_id: str | None = None
    linked_linear_issue_id: str | None = None
    alert_rules: list[dict[str, Any]] = Field(default_factory=list)


class RecordRunRequest(BaseModel):
    """Request to record a pipeline run."""

    status: str
    triggered_by: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRunResponse(BaseModel):
    """Pipeline run record returned by the API."""

    id: str
    pipeline_definition_id: str
    status: str
    triggered_by: str | None = None
    correlation_id: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class PipelineResponse(BaseModel):
    """Pipeline definition returned by the API."""

    id: str
    pipeline_key: str
    pipeline_type: str
    description: str | None = None
    owner_person_key: str | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    upstream_dependencies: list[str] = Field(default_factory=list)
    schedule: str | None = None
    environment_targets: list[str] = Field(default_factory=list)
    linked_linear_issue_id: str | None = None
    created_at: datetime
    updated_at: datetime
    runs: list[PipelineRunResponse] = Field(default_factory=list)
