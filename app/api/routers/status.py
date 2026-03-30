"""Status API — Lovable dashboard endpoints (§15.8).

Provides summary views of projects, work items, deployments, audit events,
and pipeline health for the Lovable dashboard frontend.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.audit import get_audit_log
from app.domain.enums import CanonicalState, DeploymentState
from app.services import deployments, pipelines, work_items

router = APIRouter(prefix="/api/v1/status", tags=["status"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProjectSummaryItem(BaseModel):
    id: str
    title: str
    state: str
    priority: str
    owner: str | None = None


class ProjectSummaryResponse(BaseModel):
    total: int
    by_state: dict[str, int] = Field(default_factory=dict)
    items: list[ProjectSummaryItem] = Field(default_factory=list)


class WorkItemSummaryResponse(BaseModel):
    total: int
    active: int
    by_state: dict[str, int] = Field(default_factory=dict)
    items: list[ProjectSummaryItem] = Field(default_factory=list)


class DeploymentSummaryItem(BaseModel):
    id: str
    git_sha: str
    environment: str
    state: str
    triggered_by: str | None = None


class DeploymentSummaryResponse(BaseModel):
    total: int
    recent: list[DeploymentSummaryItem] = Field(default_factory=list)
    by_state: dict[str, int] = Field(default_factory=dict)


class AuditEventItem(BaseModel):
    event_name: str
    actor_id: str
    object_type: str
    object_id: str
    change_summary: str
    event_time: str


class AuditSummaryResponse(BaseModel):
    total: int
    recent: list[AuditEventItem] = Field(default_factory=list)


class PipelineHealthItem(BaseModel):
    pipeline_key: str
    pipeline_type: str
    last_run_status: str = "unknown"
    run_count: int = 0


class PipelineHealthResponse(BaseModel):
    total: int
    healthy: int = 0
    unhealthy: int = 0
    pipelines: list[PipelineHealthItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

_TERMINAL_STATES = {CanonicalState.DONE, CanonicalState.ARCHIVED}


@router.get("/projects", response_model=ProjectSummaryResponse)
async def get_project_summary() -> ProjectSummaryResponse:
    """Project summary for the Lovable dashboard."""
    all_items = await work_items.list_work_items()
    by_state: dict[str, int] = {}
    items = []
    for wi in all_items:
        state_val = wi.canonical_state.value
        by_state[state_val] = by_state.get(state_val, 0) + 1
        items.append(ProjectSummaryItem(
            id=wi.id,
            title=wi.title,
            state=state_val,
            priority=wi.priority.value,
            owner=wi.owner_person_key,
        ))

    return ProjectSummaryResponse(total=len(all_items), by_state=by_state, items=items[:50])


@router.get("/work-items", response_model=WorkItemSummaryResponse)
async def get_work_items_summary() -> WorkItemSummaryResponse:
    """Active work items summary for the Lovable dashboard."""
    all_items = await work_items.list_work_items()
    active = [wi for wi in all_items if wi.canonical_state not in _TERMINAL_STATES]
    by_state: dict[str, int] = {}
    items = []
    for wi in active:
        state_val = wi.canonical_state.value
        by_state[state_val] = by_state.get(state_val, 0) + 1
        items.append(ProjectSummaryItem(
            id=wi.id,
            title=wi.title,
            state=state_val,
            priority=wi.priority.value,
            owner=wi.owner_person_key,
        ))

    return WorkItemSummaryResponse(
        total=len(all_items),
        active=len(active),
        by_state=by_state,
        items=items[:50],
    )


@router.get("/deployments", response_model=DeploymentSummaryResponse)
async def get_deployments_summary() -> DeploymentSummaryResponse:
    """Recent deployments summary for the Lovable dashboard."""
    all_deps = await deployments.list_deployments()
    by_state: dict[str, int] = {}
    recent = []
    for dep in all_deps:
        state_val = dep.state.value
        by_state[state_val] = by_state.get(state_val, 0) + 1
        recent.append(DeploymentSummaryItem(
            id=str(dep.id),
            git_sha=dep.git_sha,
            environment=dep.environment,
            state=state_val,
            triggered_by=dep.triggered_by_person_key,
        ))

    return DeploymentSummaryResponse(
        total=len(all_deps),
        recent=recent[:20],
        by_state=by_state,
    )


@router.get("/audit", response_model=AuditSummaryResponse)
async def get_audit_summary() -> AuditSummaryResponse:
    """Recent audit events for the Lovable dashboard."""
    log = get_audit_log()
    recent = []
    for record in log[-50:]:
        recent.append(AuditEventItem(
            event_name=record.get("event_name", ""),
            actor_id=record.get("actor_id", ""),
            object_type=record.get("object_type", ""),
            object_id=record.get("object_id", ""),
            change_summary=record.get("change_summary", ""),
            event_time=record.get("event_time", ""),
        ))

    return AuditSummaryResponse(total=len(log), recent=recent)


@router.get("/pipelines", response_model=PipelineHealthResponse)
async def get_pipeline_health() -> PipelineHealthResponse:
    """Pipeline health summary for the Lovable dashboard."""
    all_pipelines = await pipelines.list_pipelines()
    items = []
    healthy = 0
    unhealthy = 0

    for pipe in all_pipelines:
        runs = await pipelines.get_pipeline_runs(pipe.pipeline_key)
        last_status = "unknown"
        if runs:
            last_status = runs[-1].status
        if last_status in ("completed", "unknown"):
            healthy += 1
        else:
            unhealthy += 1

        items.append(PipelineHealthItem(
            pipeline_key=pipe.pipeline_key,
            pipeline_type=pipe.pipeline_type.value,
            last_run_status=last_status,
            run_count=len(runs),
        ))

    return PipelineHealthResponse(
        total=len(all_pipelines),
        healthy=healthy,
        unhealthy=unhealthy,
        pipelines=items,
    )
