"""Project API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    """Full project representation returned by the API."""

    id: str
    key: str
    name: str
    state: str
    owner_person_key: str | None = None
    linear_project_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TimelineEventResponse(BaseModel):
    """A single event in a project timeline."""

    event_name: str
    actor_id: str
    object_type: str
    object_id: str
    change_summary: str
    event_time: str


class ProjectTimelineResponse(BaseModel):
    """Full project timeline with events."""

    project_id: str
    events: list[TimelineEventResponse] = Field(default_factory=list)
    total: int = 0
