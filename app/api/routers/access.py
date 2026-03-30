"""Access requests API router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.enums import AccessRequestState
from app.schemas.api.access import (
    AccessRequestResponse,
    ApproveAccessRequest,
    CreateAccessRequest,
    RejectAccessRequest,
)
from app.services import access as access_service

router = APIRouter(prefix="/api/v1/access", tags=["access"])


def _access_to_response(r) -> AccessRequestResponse:  # noqa: ANN001
    return AccessRequestResponse(
        id=str(r.id),
        requester_person_key=r.requester_person_key,
        requested_role_bundle=r.requested_role_bundle,
        state=r.state.value if hasattr(r.state, "value") else r.state,
        policy_evaluated_at=r.policy_evaluated_at,
        approval_id=str(r.approval_id) if r.approval_id else None,
        approved_at=r.approved_at,
        provisioning_started_at=r.provisioning_started_at,
        provisioned_at=r.provisioned_at,
        verified_at=r.verified_at,
        closed_at=r.closed_at,
        linear_issue_id=r.linear_issue_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.post("/requests", response_model=AccessRequestResponse, status_code=201)
async def create_access_request(request: CreateAccessRequest) -> AccessRequestResponse:
    """Create a new access request."""
    r = await access_service.create_access_request(
        requester_person_key=request.requester_person_key,
        requested_role_bundle=request.requested_role_bundle,
        justification=request.justification,
        resources=request.resources,
        linear_issue_id=request.linear_issue_id,
    )
    return _access_to_response(r)


@router.post("/requests/{request_id}/approve", response_model=AccessRequestResponse)
async def approve_access(
    request_id: str, request: ApproveAccessRequest
) -> AccessRequestResponse:
    """Approve an access request."""
    r = await access_service.approve_access(request_id, request.approver)
    if r is None:
        raise HTTPException(status_code=404, detail="Access request not found")
    return _access_to_response(r)


@router.post("/requests/{request_id}/reject", response_model=AccessRequestResponse)
async def reject_access(
    request_id: str, request: RejectAccessRequest
) -> AccessRequestResponse:
    """Reject an access request."""
    r = await access_service.reject_access(request_id, request.approver, request.reason)
    if r is None:
        raise HTTPException(status_code=404, detail="Access request not found")
    return _access_to_response(r)


@router.post("/requests/{request_id}/provision", response_model=AccessRequestResponse)
async def provision_access(request_id: str) -> AccessRequestResponse:
    """Trigger provisioning for an approved access request."""
    r = await access_service.provision_access(request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Access request not found")
    return _access_to_response(r)


@router.get("/requests", response_model=list[AccessRequestResponse])
async def list_access_requests(
    state: str | None = None,
    requester: str | None = None,
    role_bundle: str | None = None,
) -> list[AccessRequestResponse]:
    """List access requests."""
    s = AccessRequestState(state) if state else None
    items = await access_service.list_access_requests(
        state=s,
        requester=requester,
        role_bundle=role_bundle,
    )
    return [_access_to_response(r) for r in items]
