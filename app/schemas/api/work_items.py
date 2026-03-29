"""Work item API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkItemResponse(BaseModel):
    """Full work item representation returned by the API."""

    id: str
    project_id: str | None = None
    title: str
    description: str | None = None
    work_type: str | None = None
    canonical_state: str
    priority: str | None = None
    source_channel: str | None = None
    requester_person_key: str | None = None
    owner_person_key: str | None = None
    route_key: str | None = None
    risk_level: str | None = None
    linear_issue_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkItemListResponse(BaseModel):
    """Paginated list of work items."""

    items: list[WorkItemResponse]
    total: int
    page: int = 1
    page_size: int = 50


class TransitionRequest(BaseModel):
    """Request to transition a work item to a new canonical state."""

    to_state: str
    actor: str
    reason: str | None = None


class RouteRequest(BaseModel):
    """Request to route a work item to a team or agent."""

    route_key: str = Field(..., description="Target team/agent route key")
    actor: str


class ClarifyRequest(BaseModel):
    """Request to submit clarification on a work item."""

    message: str = Field(..., min_length=1)
    actor: str


class WorkItemRouteRequest(BaseModel):
    """Route a work item — alias used by PRD spec."""

    route_key: str
    actor: str
    reason: str | None = None


class WorkItemClarifyRequest(BaseModel):
    """Clarify a work item — alias used by PRD spec."""

    message: str = Field(..., min_length=1)
    actor: str
    attachments: list[str] = Field(default_factory=list)
