"""PRD API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api.prds import (
    PRDApproveRequest,
    PRDDraftRequest,
    PRDFeedbackRequest,
    PRDRevisionResponse,
)
from app.services import prd as prd_service

router = APIRouter(tags=["prds"])


def _prd_to_response(prd) -> PRDRevisionResponse:  # noqa: ANN001
    return PRDRevisionResponse(
        id=prd.id,
        work_item_id=prd.work_item_id,
        revision_number=prd.revision_number,
        content=prd.content,
        author=prd.author,
        status=prd.status,
        artifact_id=prd.artifact_id,
        created_at=prd.created_at,
        frozen_at=prd.frozen_at,
    )


@router.post(
    "/api/v1/work-items/{work_item_id}/prd/draft",
    response_model=PRDRevisionResponse,
)
async def create_prd_draft(
    work_item_id: str, request: PRDDraftRequest
) -> PRDRevisionResponse:
    """Create a PRD draft for a work item."""
    prd = await prd_service.create_prd_draft(
        work_item_id=work_item_id,
        content=request.content,
        author=request.author,
    )
    return _prd_to_response(prd)


@router.post("/api/v1/prds/{prd_id}/feedback", response_model=PRDRevisionResponse)
async def submit_prd_feedback(
    prd_id: str, request: PRDFeedbackRequest
) -> PRDRevisionResponse:
    """Submit feedback on a PRD, creating a new revision."""
    # First submit for review if not already
    await prd_service.submit_for_review(prd_id)

    new_prd = await prd_service.incorporate_feedback(prd_id, request.feedback)
    if new_prd is None:
        raise HTTPException(status_code=404, detail="PRD not found or already frozen")
    return _prd_to_response(new_prd)


@router.post("/api/v1/prds/{prd_id}/approve", response_model=PRDRevisionResponse)
async def approve_prd(prd_id: str, request: PRDApproveRequest) -> PRDRevisionResponse:
    """Approve a PRD, making it immutable."""
    prd = await prd_service.approve_prd(prd_id, request.approver)
    if prd is None:
        raise HTTPException(status_code=404, detail="PRD not found")
    return _prd_to_response(prd)


@router.get("/api/v1/prds/{prd_id}", response_model=PRDRevisionResponse)
async def get_prd(prd_id: str) -> PRDRevisionResponse:
    """Get a PRD revision by ID."""
    prd = await prd_service.get_prd(prd_id)
    if prd is None:
        raise HTTPException(status_code=404, detail="PRD not found")
    return _prd_to_response(prd)
