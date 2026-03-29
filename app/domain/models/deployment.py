"""Deployment domain model (§17.7)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import DeploymentState


class DeploymentRecord(BaseModel):
    """Tracks a deployment through its lifecycle."""

    id: UUID
    git_sha: str
    branch_or_tag: str | None = None
    environment: str
    triggered_by_person_key: str | None = None
    state: DeploymentState = DeploymentState.BUILD_PENDING
    linked_work_item_ids: list[UUID] = []
    linked_release_notes_artifact_id: UUID | None = None
    migration_result: str | None = None
    smoke_test_result: str | None = None
    rollback_reference_id: UUID | None = None
    render_deploy_id: str | None = None
    github_workflow_run_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
