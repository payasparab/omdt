"""Deployment API schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateDeploymentRequest(BaseModel):
    """Request to create a deployment."""

    git_sha: str
    environment: str
    branch_or_tag: str | None = None
    triggered_by_person_key: str | None = None
    linked_work_item_ids: list[str] = Field(default_factory=list)
    linked_release_notes_artifact_id: str | None = None
    render_deploy_id: str | None = None
    github_workflow_run_url: str | None = None


class ApproveDeploymentRequest(BaseModel):
    """Request to approve a deployment."""

    approver: str


class RollbackDeploymentRequest(BaseModel):
    """Request to rollback a deployment."""

    reason: str
    actor: str = "system"


class DeploymentResponse(BaseModel):
    """Deployment record returned by the API."""

    id: str
    git_sha: str
    branch_or_tag: str | None = None
    environment: str
    triggered_by_person_key: str | None = None
    state: str
    linked_work_item_ids: list[str] = Field(default_factory=list)
    migration_result: str | None = None
    smoke_test_result: str | None = None
    rollback_reference_id: str | None = None
    render_deploy_id: str | None = None
    github_workflow_run_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
