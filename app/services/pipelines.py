"""Pipeline definition and run management service.

All mutations emit domain events and audit records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import PipelineType
from app.domain.models.pipeline import PipelineDefinition, PipelineRun

# In-memory stores. Will be backed by SQLAlchemy + Postgres in a future wave.
_pipeline_store: dict[str, PipelineDefinition] = {}
_run_store: dict[str, PipelineRun] = {}


def get_store() -> dict[str, PipelineDefinition]:
    return _pipeline_store


def get_run_store() -> dict[str, PipelineRun]:
    return _run_store


def clear_store() -> None:
    _pipeline_store.clear()
    _run_store.clear()


async def create_pipeline(
    *,
    pipeline_key: str,
    pipeline_type: PipelineType,
    description: str | None = None,
    owner_person_key: str | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    upstream_dependencies: list[str] | None = None,
    schedule: str | None = None,
    environment_targets: list[str] | None = None,
    quality_checks: list[dict[str, object]] | None = None,
    rollback_notes: str | None = None,
    linked_prd_artifact_id: UUID | None = None,
    linked_linear_issue_id: str | None = None,
    alert_rules: list[dict[str, object]] | None = None,
) -> PipelineDefinition:
    """Create a new pipeline definition."""
    now = datetime.now(timezone.utc)
    pipeline = PipelineDefinition(
        id=uuid4(),
        pipeline_key=pipeline_key,
        pipeline_type=pipeline_type,
        description=description,
        owner_person_key=owner_person_key,
        inputs=inputs or [],
        outputs=outputs or [],
        upstream_dependencies=upstream_dependencies or [],
        schedule=schedule,
        environment_targets=environment_targets or [],
        quality_checks=quality_checks or [],
        rollback_notes=rollback_notes,
        linked_prd_artifact_id=linked_prd_artifact_id,
        linked_linear_issue_id=linked_linear_issue_id,
        alert_rules=alert_rules or [],
        created_at=now,
        updated_at=now,
    )
    _pipeline_store[str(pipeline.id)] = pipeline

    corr_id = generate_correlation_id()
    await emit(
        "pipeline.created",
        {
            "pipeline_id": str(pipeline.id),
            "pipeline_key": pipeline_key,
            "pipeline_type": pipeline_type.value,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="pipeline.created",
        actor_type="system",
        actor_id=owner_person_key or "system",
        object_type="pipeline",
        object_id=str(pipeline.id),
        change_summary=f"Created pipeline: {pipeline_key}",
        correlation_id=corr_id,
    )
    return pipeline


async def update_pipeline(
    pipeline_key: str,
    *,
    actor: str = "system",
    **updates: Any,
) -> PipelineDefinition | None:
    """Update fields on an existing pipeline definition."""
    pipeline = _find_by_key(pipeline_key)
    if pipeline is None:
        return None

    changed: list[str] = []
    for key, value in updates.items():
        if hasattr(pipeline, key) and key not in ("id", "pipeline_key", "created_at"):
            setattr(pipeline, key, value)
            changed.append(key)

    if changed:
        pipeline.updated_at = datetime.now(timezone.utc)
        corr_id = generate_correlation_id()
        await emit(
            "pipeline.updated",
            {
                "pipeline_id": str(pipeline.id),
                "pipeline_key": pipeline_key,
                "fields_changed": changed,
                "correlation_id": corr_id,
            },
        )
        record_audit_event(
            event_name="pipeline.updated",
            actor_type="human",
            actor_id=actor,
            object_type="pipeline",
            object_id=str(pipeline.id),
            change_summary=f"Updated pipeline {pipeline_key}: {', '.join(changed)}",
            correlation_id=corr_id,
        )
    return pipeline


async def get_pipeline(pipeline_key: str) -> PipelineDefinition | None:
    """Retrieve a pipeline definition by key."""
    return _find_by_key(pipeline_key)


async def get_pipeline_by_id(pipeline_id: str) -> PipelineDefinition | None:
    """Retrieve a pipeline definition by ID."""
    return _pipeline_store.get(pipeline_id)


async def list_pipelines(
    *,
    pipeline_type: PipelineType | None = None,
    owner: str | None = None,
    environment: str | None = None,
) -> list[PipelineDefinition]:
    """List pipeline definitions with optional filters."""
    results = list(_pipeline_store.values())
    if pipeline_type is not None:
        results = [p for p in results if p.pipeline_type == pipeline_type]
    if owner is not None:
        results = [p for p in results if p.owner_person_key == owner]
    if environment is not None:
        results = [p for p in results if environment in p.environment_targets]
    return results


async def record_pipeline_run(
    pipeline_key: str,
    *,
    status: str,
    triggered_by: str | None = None,
    duration_seconds: float | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PipelineRun | None:
    """Record a pipeline run execution."""
    pipeline = _find_by_key(pipeline_key)
    if pipeline is None:
        return None

    now = datetime.now(timezone.utc)
    corr_id = generate_correlation_id()
    run = PipelineRun(
        id=uuid4(),
        pipeline_definition_id=pipeline.id,
        status=status,
        triggered_by=triggered_by,
        correlation_id=corr_id,
        duration_seconds=duration_seconds,
        error_message=error_message,
        started_at=now,
        completed_at=now if status in ("completed", "failed") else None,
    )
    _run_store[str(run.id)] = run

    await emit(
        "pipeline.run_started",
        {
            "run_id": str(run.id),
            "pipeline_key": pipeline_key,
            "status": status,
            "correlation_id": corr_id,
        },
    )
    if status in ("completed", "failed"):
        await emit(
            "pipeline.run_completed",
            {
                "run_id": str(run.id),
                "pipeline_key": pipeline_key,
                "status": status,
                "duration_seconds": duration_seconds,
                "correlation_id": corr_id,
            },
        )

    record_audit_event(
        event_name=f"pipeline.run_{status}",
        actor_type="system",
        actor_id=triggered_by or "system",
        object_type="pipeline_run",
        object_id=str(run.id),
        change_summary=f"Pipeline {pipeline_key} run {status}",
        correlation_id=corr_id,
    )
    return run


async def get_pipeline_runs(pipeline_key: str) -> list[PipelineRun]:
    """Get all runs for a pipeline."""
    pipeline = _find_by_key(pipeline_key)
    if pipeline is None:
        return []
    return [r for r in _run_store.values() if r.pipeline_definition_id == pipeline.id]


async def get_pipeline_dependencies(pipeline_key: str) -> dict[str, list[str]]:
    """Return the dependency graph for a pipeline.

    Returns a dict mapping pipeline_key -> list of upstream dependency keys.
    """
    pipeline = _find_by_key(pipeline_key)
    if pipeline is None:
        return {}

    graph: dict[str, list[str]] = {pipeline_key: list(pipeline.upstream_dependencies)}
    # Recursively resolve upstream dependencies
    visited: set[str] = {pipeline_key}
    queue = list(pipeline.upstream_dependencies)
    while queue:
        dep_key = queue.pop(0)
        if dep_key in visited:
            continue
        visited.add(dep_key)
        dep = _find_by_key(dep_key)
        if dep is not None:
            graph[dep_key] = list(dep.upstream_dependencies)
            queue.extend(dep.upstream_dependencies)
        else:
            graph[dep_key] = []
    return graph


def _find_by_key(pipeline_key: str) -> PipelineDefinition | None:
    """Find a pipeline by its pipeline_key."""
    for p in _pipeline_store.values():
        if p.pipeline_key == pipeline_key:
            return p
    return None
