"""PRD service — manages PRD drafting, review, feedback, and approval.

Approved PRDs are immutable artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import PRDStatus
from app.domain.models.prd import FeedbackRequest, PRDRevision

# In-memory stores.
_prd_store: dict[str, PRDRevision] = {}
_feedback_store: dict[str, FeedbackRequest] = {}


def get_prd_store() -> dict[str, PRDRevision]:
    return _prd_store


def get_feedback_store() -> dict[str, FeedbackRequest]:
    return _feedback_store


def clear_stores() -> None:
    _prd_store.clear()
    _feedback_store.clear()


async def create_prd_draft(
    *,
    work_item_id: str,
    content: str,
    author: str,
) -> PRDRevision:
    """Create a new PRD draft revision."""
    # Determine revision number
    existing = [p for p in _prd_store.values() if p.work_item_id == work_item_id]
    revision_number = len(existing) + 1

    prd = PRDRevision(
        work_item_id=work_item_id,
        revision_number=revision_number,
        content=content,
        author=author,
        status=PRDStatus.DRAFT,
    )
    _prd_store[prd.id] = prd
    corr_id = generate_correlation_id()

    await emit(
        "prd.created",
        {
            "prd_id": prd.id,
            "work_item_id": work_item_id,
            "revision_number": revision_number,
            "author": author,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="prd.created",
        actor_type="human",
        actor_id=author,
        object_type="prd_revision",
        object_id=prd.id,
        change_summary=f"PRD draft v{revision_number} created for work item {work_item_id}",
        correlation_id=corr_id,
    )

    return prd


async def get_prd(prd_id: str) -> PRDRevision | None:
    """Get a PRD revision by ID."""
    return _prd_store.get(prd_id)


async def submit_for_review(prd_id: str) -> FeedbackRequest | None:
    """Submit a PRD draft for review."""
    prd = _prd_store.get(prd_id)
    if prd is None:
        return None
    if prd.is_frozen:
        return None

    prd.status = PRDStatus.IN_REVIEW
    corr_id = generate_correlation_id()

    fb = FeedbackRequest(
        prd_revision_id=prd.id,
        work_item_id=prd.work_item_id,
        requested_by=prd.author,
    )
    _feedback_store[fb.id] = fb

    await emit(
        "prd.approval_requested",
        {
            "prd_id": prd.id,
            "feedback_request_id": fb.id,
            "work_item_id": prd.work_item_id,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="prd.submitted_for_review",
        actor_type="human",
        actor_id=prd.author,
        object_type="prd_revision",
        object_id=prd.id,
        change_summary=f"PRD v{prd.revision_number} submitted for review",
        correlation_id=corr_id,
    )

    return fb


async def incorporate_feedback(
    prd_id: str,
    feedback: str,
) -> PRDRevision | None:
    """Incorporate feedback by creating a new revision."""
    original = _prd_store.get(prd_id)
    if original is None:
        return None
    if original.is_frozen:
        return None

    # Create new revision with feedback incorporated
    new_prd = PRDRevision(
        work_item_id=original.work_item_id,
        revision_number=original.revision_number + 1,
        content=f"{original.content}\n\n---\nFeedback incorporated:\n{feedback}",
        author=original.author,
        status=PRDStatus.DRAFT,
    )
    _prd_store[new_prd.id] = new_prd
    corr_id = generate_correlation_id()

    await emit(
        "prd.revised",
        {
            "prd_id": new_prd.id,
            "original_prd_id": prd_id,
            "work_item_id": original.work_item_id,
            "revision_number": new_prd.revision_number,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="prd.revised",
        actor_type="human",
        actor_id=original.author,
        object_type="prd_revision",
        object_id=new_prd.id,
        change_summary=f"PRD revised to v{new_prd.revision_number} with feedback",
        correlation_id=corr_id,
    )

    return new_prd


async def approve_prd(prd_id: str, approver: str) -> PRDRevision | None:
    """Approve a PRD, making it immutable."""
    prd = _prd_store.get(prd_id)
    if prd is None:
        return None
    if prd.is_frozen:
        return prd  # Already approved

    prd.status = PRDStatus.APPROVED
    prd.frozen_at = datetime.now(timezone.utc)
    corr_id = generate_correlation_id()

    await emit(
        "prd.approved",
        {
            "prd_id": prd.id,
            "work_item_id": prd.work_item_id,
            "approver": approver,
            "revision_number": prd.revision_number,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="prd.approved",
        actor_type="human",
        actor_id=approver,
        object_type="prd_revision",
        object_id=prd.id,
        change_summary=f"PRD v{prd.revision_number} approved by {approver} (now frozen)",
        correlation_id=corr_id,
        approval_id=prd.id,
    )

    return prd
