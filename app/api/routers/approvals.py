"""Approvals API router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api.approvals import ApprovalDecisionRequest, ApprovalResponse
from app.services import approvals as approval_service

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _ar_to_response(ar) -> ApprovalResponse:  # noqa: ANN001
    return ApprovalResponse(
        id=ar.id,
        work_item_id=ar.work_item_id,
        action=ar.action,
        requester=ar.requester,
        approvers=ar.approvers,
        status=ar.status,
        decided_by=ar.decided_by,
        decision_reason=ar.decision_reason,
        created_at=ar.created_at,
        decided_at=ar.decided_at,
    )


@router.get("/pending", response_model=list[ApprovalResponse])
async def get_pending_approvals(approver: str | None = None) -> list[ApprovalResponse]:
    """Get pending approval requests."""
    approvals = await approval_service.get_pending_approvals(approver)
    return [_ar_to_response(a) for a in approvals]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: str, request: ApprovalDecisionRequest
) -> ApprovalResponse:
    """Approve an approval request."""
    ar = await approval_service.approve(approval_id, request.actor, request.reason)
    if ar is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return _ar_to_response(ar)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: str, request: ApprovalDecisionRequest
) -> ApprovalResponse:
    """Reject an approval request."""
    ar = await approval_service.reject(approval_id, request.actor, request.reason)
    if ar is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return _ar_to_response(ar)
