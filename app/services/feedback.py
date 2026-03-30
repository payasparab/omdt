"""Feedback routing service — manages feedback requests and responses.

Implements FeedbackRoutingDecision per §11.8 and channel selection
rules per §11.5: reply defaults to source channel, with fallbacks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import SourceChannel
from app.domain.models.conversation import FeedbackRequest, FeedbackResponse
from app.domain.models.routing import FeedbackRoutingDecision

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_request_store: dict[str, FeedbackRequest] = {}  # keyed by request id
_response_store: dict[str, list[FeedbackResponse]] = {}  # keyed by request id


def get_request_store() -> dict[str, FeedbackRequest]:
    return _request_store


def get_response_store() -> dict[str, list[FeedbackResponse]]:
    return _response_store


def clear_stores() -> None:
    _request_store.clear()
    _response_store.clear()


# ---------------------------------------------------------------------------
# Channel selection (§11.5)
# ---------------------------------------------------------------------------

_CHANNEL_FALLBACK_ORDER: list[SourceChannel] = [
    SourceChannel.OUTLOOK,
    SourceChannel.EMAIL,
    SourceChannel.LINEAR,
    SourceChannel.NOTION,
    SourceChannel.API,
]


def select_reply_channel(
    source_channel: SourceChannel | None,
    available_channels: list[SourceChannel] | None = None,
) -> SourceChannel:
    """Select the best reply channel.

    Rule: reply defaults to source channel, with fallbacks.
    """
    if source_channel is not None:
        if available_channels is None or source_channel in available_channels:
            return source_channel

    # Fallback through priority order
    if available_channels:
        for ch in _CHANNEL_FALLBACK_ORDER:
            if ch in available_channels:
                return ch

    return source_channel or SourceChannel.EMAIL


# ---------------------------------------------------------------------------
# Feedback routing decision (§11.8)
# ---------------------------------------------------------------------------

def build_routing_decision(
    work_item_id: str,
    source_channel: SourceChannel,
    participants: list[str],
    *,
    thread_id: str = "",
    requires_human_approval: bool = False,
) -> FeedbackRoutingDecision:
    """Build a FeedbackRoutingDecision for a feedback request."""
    reply_channel = select_reply_channel(source_channel)
    return FeedbackRoutingDecision(
        thread_id=thread_id,
        work_item_id=work_item_id,
        source_channel=source_channel,
        preferred_reply_channel=reply_channel,
        participants=participants,
        requires_human_approval=requires_human_approval,
        reason=f"Reply via {reply_channel.value}, {len(participants)} participant(s)",
    )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def create_feedback_request(
    work_item_id: str,
    prd_id: str | None = None,
    participants: list[str] | None = None,
    source_channel: SourceChannel = SourceChannel.API,
) -> FeedbackRequest:
    """Create a new feedback request for a PRD or work item."""
    request_id = uuid4()
    now = datetime.now(timezone.utc)

    fb = FeedbackRequest(
        id=request_id,
        prd_revision_id=UUID(prd_id) if prd_id else None,
        work_item_id=UUID(work_item_id),
        requested_from=participants or [],
        requested_channels=[source_channel],
        status="pending",
        created_at=now,
    )
    key = str(request_id)
    _request_store[key] = fb
    _response_store[key] = []

    corr_id = generate_correlation_id()
    await emit("feedback.request_created", {
        "feedback_request_id": key,
        "work_item_id": work_item_id,
        "prd_id": prd_id,
        "participants": participants or [],
        "correlation_id": corr_id,
    })

    record_audit_event(
        event_name="feedback.request_created",
        actor_type="system",
        actor_id="feedback_service",
        object_type="feedback_request",
        object_id=key,
        change_summary=f"Feedback requested for work item {work_item_id}",
        correlation_id=corr_id,
    )

    return fb


async def record_feedback_response(
    feedback_request_id: str,
    responder: str,
    content: str,
    channel: SourceChannel | None = None,
) -> FeedbackResponse:
    """Record a feedback response against a feedback request."""
    fb = _request_store.get(feedback_request_id)
    if fb is None:
        raise ValueError(f"Feedback request not found: {feedback_request_id}")

    response = FeedbackResponse(
        id=uuid4(),
        feedback_request_id=UUID(feedback_request_id),
        respondent_person_key=responder,
        response_channel=channel,
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    _response_store.setdefault(feedback_request_id, []).append(response)

    # Check if all participants have responded
    responded = {r.respondent_person_key for r in _response_store[feedback_request_id]}
    requested = set(fb.requested_from)
    if requested and responded >= requested:
        fb.status = "resolved"

    corr_id = generate_correlation_id()
    await emit("feedback.response_received", {
        "feedback_request_id": feedback_request_id,
        "responder": responder,
        "work_item_id": str(fb.work_item_id),
        "all_responded": fb.status == "resolved",
        "correlation_id": corr_id,
    })

    record_audit_event(
        event_name="feedback.response_received",
        actor_type="human",
        actor_id=responder,
        object_type="feedback_response",
        object_id=str(response.id),
        change_summary=f"Feedback from {responder} on request {feedback_request_id}",
        correlation_id=corr_id,
    )

    return response


async def get_feedback_status(prd_id: str) -> dict[str, Any]:
    """Get a summary of all feedback for a given PRD."""
    try:
        prd_uuid = UUID(prd_id)
    except ValueError:
        return {
            "prd_id": prd_id,
            "total_requests": 0,
            "pending": 0,
            "resolved": 0,
            "requests": [],
        }
    matching = [
        fb for fb in _request_store.values()
        if fb.prd_revision_id == prd_uuid
    ]

    summaries: list[dict[str, Any]] = []
    total_pending = 0
    total_resolved = 0

    for fb in matching:
        fb_key = str(fb.id)
        responses = _response_store.get(fb_key, [])
        responded_by = [r.respondent_person_key for r in responses]
        pending = [p for p in fb.requested_from if p not in responded_by]

        if fb.status == "resolved":
            total_resolved += 1
        else:
            total_pending += 1

        summaries.append({
            "feedback_request_id": fb_key,
            "status": fb.status,
            "requested_from": fb.requested_from,
            "responded_by": responded_by,
            "pending_from": pending,
            "response_count": len(responses),
        })

    return {
        "prd_id": prd_id,
        "total_requests": len(matching),
        "pending": total_pending,
        "resolved": total_resolved,
        "requests": summaries,
    }
