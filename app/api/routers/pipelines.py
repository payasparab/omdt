"""Pipelines API router."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.domain.enums import PipelineType
from app.schemas.api.pipelines import (
    CreatePipelineRequest,
    PipelineResponse,
    PipelineRunResponse,
    RecordRunRequest,
)
from app.services import pipelines as pipeline_service

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


def _pipeline_to_response(p, runs: list | None = None) -> PipelineResponse:  # noqa: ANN001
    return PipelineResponse(
        id=str(p.id),
        pipeline_key=p.pipeline_key,
        pipeline_type=p.pipeline_type.value if hasattr(p.pipeline_type, "value") else p.pipeline_type,
        description=p.description,
        owner_person_key=p.owner_person_key,
        inputs=p.inputs,
        outputs=p.outputs,
        upstream_dependencies=p.upstream_dependencies,
        schedule=p.schedule,
        environment_targets=p.environment_targets,
        linked_linear_issue_id=p.linked_linear_issue_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
        runs=[_run_to_response(r) for r in (runs or [])],
    )


def _run_to_response(r) -> PipelineRunResponse:  # noqa: ANN001
    return PipelineRunResponse(
        id=str(r.id),
        pipeline_definition_id=str(r.pipeline_definition_id),
        status=r.status,
        triggered_by=r.triggered_by,
        correlation_id=r.correlation_id,
        duration_seconds=r.duration_seconds,
        error_message=r.error_message,
        started_at=r.started_at,
        completed_at=r.completed_at,
    )


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    pipeline_type: str | None = None,
    owner: str | None = None,
    environment: str | None = None,
) -> list[PipelineResponse]:
    """List pipeline definitions."""
    pt = PipelineType(pipeline_type) if pipeline_type else None
    items = await pipeline_service.list_pipelines(
        pipeline_type=pt,
        owner=owner,
        environment=environment,
    )
    return [_pipeline_to_response(p) for p in items]


@router.get("/{pipeline_key}", response_model=PipelineResponse)
async def get_pipeline(pipeline_key: str) -> PipelineResponse:
    """Get a pipeline definition with its run history."""
    p = await pipeline_service.get_pipeline(pipeline_key)
    if p is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    runs = await pipeline_service.get_pipeline_runs(pipeline_key)
    return _pipeline_to_response(p, runs)


@router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(request: CreatePipelineRequest) -> PipelineResponse:
    """Create a new pipeline definition."""
    try:
        pt = PipelineType(request.pipeline_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid pipeline type: {request.pipeline_type}")

    p = await pipeline_service.create_pipeline(
        pipeline_key=request.pipeline_key,
        pipeline_type=pt,
        description=request.description,
        owner_person_key=request.owner_person_key,
        inputs=request.inputs,
        outputs=request.outputs,
        upstream_dependencies=request.upstream_dependencies,
        schedule=request.schedule,
        environment_targets=request.environment_targets,
        quality_checks=request.quality_checks,
        rollback_notes=request.rollback_notes,
        linked_prd_artifact_id=UUID(request.linked_prd_artifact_id) if request.linked_prd_artifact_id else None,
        linked_linear_issue_id=request.linked_linear_issue_id,
        alert_rules=request.alert_rules,
    )
    return _pipeline_to_response(p)


@router.post("/{pipeline_key}/runs", response_model=PipelineRunResponse, status_code=201)
async def record_run(pipeline_key: str, request: RecordRunRequest) -> PipelineRunResponse:
    """Record a pipeline run."""
    run = await pipeline_service.record_pipeline_run(
        pipeline_key,
        status=request.status,
        triggered_by=request.triggered_by,
        duration_seconds=request.duration_seconds,
        error_message=request.error_message,
        metadata=request.metadata,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return _run_to_response(run)
