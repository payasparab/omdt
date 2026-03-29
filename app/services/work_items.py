"""Work item CRUD service.

All mutations emit domain events and audit records.
State transitions are delegated to the WorkflowEngine.
"""
from __future__ import annotations

from typing import Any

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import CanonicalState, Priority, SourceChannel, WorkItemType
from app.domain.models.work_item import WorkItem
from app.workflows.engine import TransitionResult, WorkflowEngine

# In-memory store. Will be backed by SQLAlchemy + Postgres in a future wave.
_store: dict[str, WorkItem] = {}


def get_store() -> dict[str, WorkItem]:
    """Return the in-memory store (for testing)."""
    return _store


def clear_store() -> None:
    """Clear the in-memory store (testing only)."""
    _store.clear()


async def create_work_item(
    *,
    title: str,
    description: str = "",
    work_type: WorkItemType = WorkItemType.TASK,
    priority: Priority = Priority.MEDIUM,
    source_channel: SourceChannel | None = None,
    source_external_id: str | None = None,
    requester_person_key: str | None = None,
    owner_person_key: str | None = None,
    project_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkItem:
    """Create a new work item, persist, and emit events."""
    wi = WorkItem(
        title=title,
        description=description,
        work_type=work_type,
        priority=priority,
        source_channel=source_channel,
        source_external_id=source_external_id,
        requester_person_key=requester_person_key,
        owner_person_key=owner_person_key,
        project_id=project_id,
        metadata=metadata or {},
    )
    _store[wi.id] = wi

    corr_id = generate_correlation_id()

    await emit(
        "work_item.created",
        {
            "work_item_id": wi.id,
            "title": wi.title,
            "work_type": wi.work_type.value,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="work_item.created",
        actor_type="system",
        actor_id=requester_person_key or "system",
        object_type="work_item",
        object_id=wi.id,
        change_summary=f"Created work item: {title}",
        correlation_id=corr_id,
    )

    return wi


async def get_work_item(work_item_id: str) -> WorkItem | None:
    """Retrieve a work item by ID."""
    return _store.get(work_item_id)


async def list_work_items(
    *,
    state: CanonicalState | None = None,
    work_type: WorkItemType | None = None,
    owner: str | None = None,
    project_id: str | None = None,
) -> list[WorkItem]:
    """List work items with optional filters."""
    results = list(_store.values())
    if state is not None:
        results = [w for w in results if w.canonical_state == state]
    if work_type is not None:
        results = [w for w in results if w.work_type == work_type]
    if owner is not None:
        results = [w for w in results if w.owner_person_key == owner]
    if project_id is not None:
        results = [w for w in results if w.project_id == project_id]
    return results


async def update_work_item(
    work_item_id: str,
    *,
    actor: str = "system",
    **updates: Any,
) -> WorkItem | None:
    """Update fields on a work item (not state — use transition for that)."""
    wi = _store.get(work_item_id)
    if wi is None:
        return None

    changed: list[str] = []
    for key, value in updates.items():
        if hasattr(wi, key) and key != "canonical_state":
            setattr(wi, key, value)
            changed.append(key)

    if changed:
        wi.touch()
        corr_id = generate_correlation_id()

        await emit(
            "work_item.updated",
            {
                "work_item_id": wi.id,
                "fields_changed": changed,
                "correlation_id": corr_id,
            },
        )

        record_audit_event(
            event_name="work_item.updated",
            actor_type="human",
            actor_id=actor,
            object_type="work_item",
            object_id=wi.id,
            change_summary=f"Updated fields: {', '.join(changed)}",
            correlation_id=corr_id,
        )

    return wi


async def transition_work_item(
    work_item_id: str,
    to_state: CanonicalState,
    actor: str,
    reason: str = "",
    engine: WorkflowEngine | None = None,
) -> TransitionResult:
    """Transition a work item's state via the workflow engine."""
    wi = _store.get(work_item_id)
    if wi is None:
        return TransitionResult(
            success=False,
            from_state=CanonicalState.NEW,
            to_state=to_state,
            work_item_id=work_item_id,
            error="Work item not found",
        )

    eng = engine or WorkflowEngine()
    return await eng.transition(wi, to_state, actor, reason)
