"""Projects API router — project detail and timeline."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.audit import get_audit_log
from app.schemas.api.projects import (
    ProjectResponse,
    ProjectTimelineResponse,
    TimelineEventResponse,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# In-memory project store (shared with other services in future waves)
_project_store: dict[str, dict] = {}


def get_project_store() -> dict[str, dict]:
    return _project_store


def set_project_store(store: dict[str, dict]) -> None:
    global _project_store
    _project_store = store


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """Get a project with its current state."""
    project = _project_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**project)


@router.get("/{project_id}/timeline", response_model=ProjectTimelineResponse)
async def get_project_timeline(project_id: str) -> ProjectTimelineResponse:
    """Get the full timeline of events for a project."""
    project = _project_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Collect audit events related to this project
    audit_log = get_audit_log()
    events = []
    for record in audit_log:
        # Match events for work items in this project or the project itself
        obj_id = record.get("object_id", "")
        if obj_id == project_id or record.get("correlation_id", "").startswith(f"proj-{project_id}"):
            events.append(TimelineEventResponse(
                event_name=record.get("event_name", ""),
                actor_id=record.get("actor_id", ""),
                object_type=record.get("object_type", ""),
                object_id=obj_id,
                change_summary=record.get("change_summary", ""),
                event_time=record.get("event_time", ""),
            ))

    return ProjectTimelineResponse(
        project_id=project_id,
        events=events,
        total=len(events),
    )
