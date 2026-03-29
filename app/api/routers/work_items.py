"""Work items API router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.enums import CanonicalState
from app.schemas.api.work_items import (
    ClarifyRequest,
    RouteRequest,
    TransitionRequest,
    WorkItemResponse,
)
from app.services import work_items as wi_service

router = APIRouter(prefix="/api/v1/work-items", tags=["work-items"])


def _wi_to_response(wi) -> WorkItemResponse:  # noqa: ANN001
    return WorkItemResponse(
        id=wi.id,
        project_id=wi.project_id,
        title=wi.title,
        description=wi.description,
        work_type=wi.work_type.value if hasattr(wi.work_type, "value") else wi.work_type,
        canonical_state=wi.canonical_state.value if hasattr(wi.canonical_state, "value") else wi.canonical_state,
        priority=wi.priority.value if hasattr(wi.priority, "value") else wi.priority,
        source_channel=wi.source_channel.value if hasattr(wi.source_channel, "value") else wi.source_channel,
        requester_person_key=wi.requester_person_key,
        owner_person_key=wi.owner_person_key,
        route_key=wi.route_key,
        risk_level=wi.risk_level,
        linear_issue_id=wi.linear_issue_id,
        created_at=wi.created_at,
        updated_at=wi.updated_at,
    )


@router.get("/{work_item_id}", response_model=WorkItemResponse)
async def get_work_item(work_item_id: str) -> WorkItemResponse:
    """Get a work item by ID."""
    wi = await wi_service.get_work_item(work_item_id)
    if wi is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return _wi_to_response(wi)


@router.post("/{work_item_id}/transition", response_model=WorkItemResponse)
async def transition_work_item(
    work_item_id: str, request: TransitionRequest
) -> WorkItemResponse:
    """Transition a work item to a new state."""
    try:
        to_state = CanonicalState(request.to_state)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {request.to_state}")

    result = await wi_service.transition_work_item(
        work_item_id, to_state, request.actor, request.reason or ""
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    wi = await wi_service.get_work_item(work_item_id)
    return _wi_to_response(wi)


@router.post("/{work_item_id}/route", response_model=WorkItemResponse)
async def route_work_item(
    work_item_id: str, request: RouteRequest
) -> WorkItemResponse:
    """Route a work item to a team/agent."""
    wi = await wi_service.update_work_item(
        work_item_id, actor=request.actor, route_key=request.route_key
    )
    if wi is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return _wi_to_response(wi)


@router.post("/{work_item_id}/clarify", response_model=WorkItemResponse)
async def clarify_work_item(
    work_item_id: str, request: ClarifyRequest
) -> WorkItemResponse:
    """Submit clarification and transition back from NEEDS_CLARIFICATION."""
    wi = await wi_service.get_work_item(work_item_id)
    if wi is None:
        raise HTTPException(status_code=404, detail="Work item not found")

    # Update description with clarification
    await wi_service.update_work_item(
        work_item_id,
        actor=request.actor,
        description=f"{wi.description}\n\n---\nClarification: {request.message}",
    )

    # Transition back to TRIAGE if currently in NEEDS_CLARIFICATION
    if wi.canonical_state == CanonicalState.NEEDS_CLARIFICATION:
        result = await wi_service.transition_work_item(
            work_item_id, CanonicalState.TRIAGE, request.actor, "Clarification received"
        )
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

    wi = await wi_service.get_work_item(work_item_id)
    return _wi_to_response(wi)
