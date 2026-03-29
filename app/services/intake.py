"""Intake service — normalizes incoming messages into work items.

Records source_channel, requester, external IDs.
Emits intake.received and intake.normalized events.
Sets initial state to NEW, then transitions to TRIAGE.
"""
from __future__ import annotations

from typing import Any

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import CanonicalState, SourceChannel, WorkItemType
from app.domain.models.work_item import WorkItem
from app.services.work_items import create_work_item, transition_work_item


async def process_intake(
    *,
    message: str,
    source_channel: SourceChannel = SourceChannel.API,
    requester: str | None = None,
    external_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkItem:
    """Process an incoming intake message.

    1. Emit intake.received event
    2. Normalize into a work item (state=NEW)
    3. Emit intake.normalized event
    4. Transition to TRIAGE
    """
    corr_id = generate_correlation_id()

    # 1. Emit intake.received
    await emit(
        "intake.received",
        {
            "source_channel": source_channel.value if isinstance(source_channel, SourceChannel) else source_channel,
            "requester": requester,
            "external_id": external_id,
            "correlation_id": corr_id,
        },
    )

    # 2. Normalize — extract title from first line, rest is description
    lines = message.strip().splitlines()
    title = lines[0][:200] if lines else "Untitled intake"
    description = "\n".join(lines[1:]).strip() if len(lines) > 1 else message

    wi = await create_work_item(
        title=title,
        description=description,
        work_type=WorkItemType.TASK,
        source_channel=source_channel,
        source_external_id=external_id,
        requester_person_key=requester,
        metadata=metadata or {},
    )

    # 3. Emit intake.normalized
    await emit(
        "intake.normalized",
        {
            "work_item_id": wi.id,
            "title": wi.title,
            "source_channel": source_channel.value if isinstance(source_channel, SourceChannel) else source_channel,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="intake.normalized",
        actor_type="system",
        actor_id="intake_service",
        object_type="work_item",
        object_id=wi.id,
        change_summary=f"Normalized intake from {source_channel.value if isinstance(source_channel, SourceChannel) else source_channel}: {title}",
        correlation_id=corr_id,
    )

    # 4. Transition to TRIAGE
    await transition_work_item(wi.id, CanonicalState.TRIAGE, actor="intake_service")

    return wi
