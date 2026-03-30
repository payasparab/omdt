"""Schedule synchronisation bridge.

Reads pipeline schedule definitions from OMDT and ensures Render cron jobs
and GitHub Actions schedules are in sync.
"""
from __future__ import annotations

from typing import Any

from app.core.audit import record_audit_event
from app.core.ids import generate_correlation_id
from app.services import pipelines as pipeline_service


async def sync_schedules(
    *,
    render_adapter: Any | None = None,
) -> dict[str, Any]:
    """Synchronise all pipeline schedules with Render cron jobs.

    Returns a summary of actions taken.
    """
    all_pipelines = await pipeline_service.list_pipelines()
    scheduled = [p for p in all_pipelines if p.schedule]

    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for pipeline in scheduled:
        if render_adapter is None:
            skipped.append(pipeline.pipeline_key)
            continue

        try:
            result = await create_render_cron(
                pipeline.pipeline_key,
                pipeline.schedule,  # type: ignore[arg-type]
                render_adapter=render_adapter,
            )
            if result.get("action") == "created":
                created.append(pipeline.pipeline_key)
            elif result.get("action") == "updated":
                updated.append(pipeline.pipeline_key)
            else:
                skipped.append(pipeline.pipeline_key)
        except Exception:
            skipped.append(pipeline.pipeline_key)

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="schedule.sync_completed",
        actor_type="system",
        actor_id="schedule_sync",
        object_type="schedule",
        object_id="all",
        change_summary=f"Schedule sync: {len(created)} created, {len(updated)} updated, {len(skipped)} skipped",
        correlation_id=corr_id,
    )

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(scheduled),
    }


async def create_render_cron(
    pipeline_key: str,
    schedule: str,
    *,
    render_adapter: Any | None = None,
) -> dict[str, Any]:
    """Create a Render cron job for a pipeline schedule."""
    if render_adapter is None:
        return {"action": "skipped", "pipeline_key": pipeline_key}

    result = await render_adapter.execute(
        "create_cron_job",
        {
            "name": f"omdt-{pipeline_key}",
            "schedule": schedule,
            "command": f"python -m app.jobs.run_pipeline {pipeline_key}",
        },
    )

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="schedule.cron_created",
        actor_type="system",
        actor_id="schedule_sync",
        object_type="cron_job",
        object_id=pipeline_key,
        change_summary=f"Render cron created for {pipeline_key}: {schedule}",
        correlation_id=corr_id,
    )

    return {"action": "created", "pipeline_key": pipeline_key, "result": result}


async def update_render_cron(
    pipeline_key: str,
    schedule: str,
    *,
    render_adapter: Any | None = None,
) -> dict[str, Any]:
    """Update an existing Render cron job for a pipeline schedule."""
    if render_adapter is None:
        return {"action": "skipped", "pipeline_key": pipeline_key}

    result = await render_adapter.execute(
        "update_cron_job",
        {
            "name": f"omdt-{pipeline_key}",
            "schedule": schedule,
        },
    )

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="schedule.cron_updated",
        actor_type="system",
        actor_id="schedule_sync",
        object_type="cron_job",
        object_id=pipeline_key,
        change_summary=f"Render cron updated for {pipeline_key}: {schedule}",
        correlation_id=corr_id,
    )

    return {"action": "updated", "pipeline_key": pipeline_key, "result": result}
