"""Approval service — manages approval requests and decisions.

All actions emit domain events and audit records.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import ApprovalStatus
from app.domain.models.approval import ApprovalRequest

# In-memory store.
_store: dict[str, ApprovalRequest] = {}


def get_store() -> dict[str, ApprovalRequest]:
    return _store


def clear_store() -> None:
    _store.clear()


async def create_approval_request(
    *,
    work_item_id: str,
    action: str,
    requester: str,
    approvers: list[str],
) -> ApprovalRequest:
    """Create a new approval request."""
    ar = ApprovalRequest(
        work_item_id=work_item_id,
        action=action,
        requester=requester,
        approvers=approvers,
    )
    _store[ar.id] = ar
    corr_id = generate_correlation_id()

    await emit(
        "approval.requested",
        {
            "approval_id": ar.id,
            "work_item_id": work_item_id,
            "action": action,
            "approvers": approvers,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="approval.requested",
        actor_type="human",
        actor_id=requester,
        object_type="approval",
        object_id=ar.id,
        change_summary=f"Approval requested for {action} on work item {work_item_id}",
        correlation_id=corr_id,
    )

    return ar


async def approve(
    approval_id: str,
    approver: str,
    reason: str = "",
) -> ApprovalRequest | None:
    """Approve an approval request."""
    ar = _store.get(approval_id)
    if ar is None:
        return None
    if ar.status != ApprovalStatus.PENDING:
        return ar

    ar.status = ApprovalStatus.APPROVED
    ar.decided_by = approver
    ar.decision_reason = reason
    ar.decided_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()

    await emit(
        "approval.approved",
        {
            "approval_id": ar.id,
            "work_item_id": ar.work_item_id,
            "approver": approver,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="approval.approved",
        actor_type="human",
        actor_id=approver,
        object_type="approval",
        object_id=ar.id,
        change_summary=f"Approved by {approver}. {reason}".strip(),
        correlation_id=corr_id,
        approval_id=ar.id,
    )

    return ar


async def reject(
    approval_id: str,
    approver: str,
    reason: str = "",
) -> ApprovalRequest | None:
    """Reject an approval request."""
    ar = _store.get(approval_id)
    if ar is None:
        return None
    if ar.status != ApprovalStatus.PENDING:
        return ar

    ar.status = ApprovalStatus.REJECTED
    ar.decided_by = approver
    ar.decision_reason = reason
    ar.decided_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()

    await emit(
        "approval.rejected",
        {
            "approval_id": ar.id,
            "work_item_id": ar.work_item_id,
            "approver": approver,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="approval.rejected",
        actor_type="human",
        actor_id=approver,
        object_type="approval",
        object_id=ar.id,
        change_summary=f"Rejected by {approver}. {reason}".strip(),
        correlation_id=corr_id,
        approval_id=ar.id,
    )

    return ar


async def get_pending_approvals(approver: str | None = None) -> list[ApprovalRequest]:
    """Get pending approval requests, optionally filtered by approver."""
    results = [a for a in _store.values() if a.status == ApprovalStatus.PENDING]
    if approver:
        results = [a for a in results if approver in a.approvers]
    return results
