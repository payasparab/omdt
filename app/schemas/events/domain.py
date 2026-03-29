"""Typed event payload models for key domain events.

Each model represents the ``payload`` dict for its corresponding
:class:`~app.core.events.DomainEvent`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------

class IntakeReceivedPayload(BaseModel):
    source_channel: str
    raw_body: str
    sender: str | None = None


class IntakeNormalizedPayload(BaseModel):
    work_item_id: str
    title: str
    priority: str | None = None
    requester: str | None = None


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

class TriageRouteProposedPayload(BaseModel):
    work_item_id: str
    proposed_agent: str
    confidence: float | None = None


class TriageClarificationRequestedPayload(BaseModel):
    work_item_id: str
    question: str
    channel: str | None = None


class TriageClarificationReceivedPayload(BaseModel):
    work_item_id: str
    answer: str
    responder: str | None = None


# ---------------------------------------------------------------------------
# PRD
# ---------------------------------------------------------------------------

class PRDCreatedPayload(BaseModel):
    prd_id: str
    project_id: str
    title: str


class PRDRevisedPayload(BaseModel):
    prd_id: str
    revision_number: int
    change_summary: str


class PRDApprovalRequestedPayload(BaseModel):
    prd_id: str
    requested_by: str


class PRDApprovedPayload(BaseModel):
    prd_id: str
    approved_by: str
    approval_id: str | None = None


# ---------------------------------------------------------------------------
# Project / Work Item
# ---------------------------------------------------------------------------

class ProjectCreatedPayload(BaseModel):
    project_id: str
    title: str
    owner: str | None = None


class WorkItemCreatedPayload(BaseModel):
    work_item_id: str
    project_id: str | None = None
    title: str
    item_type: str | None = None


class WorkItemStateChangedPayload(BaseModel):
    work_item_id: str
    previous_state: str
    new_state: str
    changed_by: str | None = None


# ---------------------------------------------------------------------------
# Linear sync
# ---------------------------------------------------------------------------

class LinearSyncStartedPayload(BaseModel):
    sync_id: str
    direction: str = "push"  # "push" | "pull"


class LinearSyncCompletedPayload(BaseModel):
    sync_id: str
    items_synced: int = 0


class LinearSyncFailedPayload(BaseModel):
    sync_id: str
    error: str


# ---------------------------------------------------------------------------
# Notion sync
# ---------------------------------------------------------------------------

class NotionSyncCompletedPayload(BaseModel):
    pages_synced: int = 0


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------

class AccessRequestCreatedPayload(BaseModel):
    request_id: str
    resource: str
    requester: str


class AccessProvisionedPayload(BaseModel):
    request_id: str
    resource: str
    granted_to: str


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class PipelineRunStartedPayload(BaseModel):
    pipeline_id: str
    run_id: str


class PipelineRunCompletedPayload(BaseModel):
    pipeline_id: str
    run_id: str
    status: str  # "success" | "failure"
    duration_ms: int | None = None


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

class DeploymentStartedPayload(BaseModel):
    deployment_id: str
    service: str
    environment: str


class DeploymentSucceededPayload(BaseModel):
    deployment_id: str
    service: str


class DeploymentFailedPayload(BaseModel):
    deployment_id: str
    service: str
    error: str


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------

class ArtifactCreatedPayload(BaseModel):
    artifact_id: str
    artifact_type: str
    name: str


class ArtifactPublishedPayload(BaseModel):
    artifact_id: str
    publish_target: str
    url: str | None = None


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

class DocumentationGeneratedPayload(BaseModel):
    document_id: str
    document_type: str
    title: str


class DocumentationPublishedPayload(BaseModel):
    document_id: str
    publish_target: str


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

class TrainingPlanGeneratedPayload(BaseModel):
    plan_id: str
    role: str
    modules: list[str] = Field(default_factory=list)


class TrainingMaterialPublishedPayload(BaseModel):
    material_id: str
    title: str


# ---------------------------------------------------------------------------
# Communication
# ---------------------------------------------------------------------------

class CommunicationSentPayload(BaseModel):
    channel: str  # "email", "linear_comment", "notion", etc.
    recipient: str
    subject: str | None = None
