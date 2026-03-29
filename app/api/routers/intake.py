"""Intake API router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.enums import SourceChannel
from app.schemas.api.intake import CLIIntakeRequest, IntakeMessageRequest
from app.schemas.api.work_items import WorkItemResponse
from app.services import intake as intake_service

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


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


@router.post("/messages", response_model=WorkItemResponse)
async def process_intake_message(request: IntakeMessageRequest) -> WorkItemResponse:
    """Process an intake message from any channel."""
    try:
        channel = SourceChannel(request.source_channel)
    except ValueError:
        channel = SourceChannel.API

    wi = await intake_service.process_intake(
        message=request.message,
        source_channel=channel,
        requester=request.requester,
        external_id=request.external_id,
        metadata=request.metadata,
    )
    return _wi_to_response(wi)


@router.post("/cli", response_model=WorkItemResponse)
async def process_cli_intake(request: CLIIntakeRequest) -> WorkItemResponse:
    """Process an intake message from the CLI."""
    wi = await intake_service.process_intake(
        message=request.message,
        source_channel=SourceChannel.CLI,
        requester=request.requester,
    )
    return _wi_to_response(wi)
