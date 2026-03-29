"""Domain event system — in-process pub/sub with typed events.

Implements the Core Event Taxonomy from Appendix B and provides an
``EventBus`` for registering handlers and emitting events.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field

from app.core.ids import generate_id, get_current_correlation_id


# ---------------------------------------------------------------------------
# Event name constants (Appendix B)
# ---------------------------------------------------------------------------

class DomainEventNames:
    """String constants for every domain event in the core taxonomy."""

    # Intake
    INTAKE_RECEIVED = "intake.received"
    INTAKE_NORMALIZED = "intake.normalized"

    # Triage
    TRIAGE_ROUTE_PROPOSED = "triage.route_proposed"
    TRIAGE_CLARIFICATION_REQUESTED = "triage.clarification_requested"
    TRIAGE_CLARIFICATION_RECEIVED = "triage.clarification_received"

    # PRD
    PRD_CREATED = "prd.created"
    PRD_REVISED = "prd.revised"
    PRD_APPROVAL_REQUESTED = "prd.approval_requested"
    PRD_APPROVED = "prd.approved"

    # Project
    PROJECT_CREATED = "project.created"

    # Work item
    WORK_ITEM_CREATED = "work_item.created"
    WORK_ITEM_STATE_CHANGED = "work_item.state_changed"

    # Linear sync
    LINEAR_SYNC_STARTED = "linear.sync_started"
    LINEAR_SYNC_COMPLETED = "linear.sync_completed"
    LINEAR_SYNC_FAILED = "linear.sync_failed"

    # Notion sync
    NOTION_SYNC_COMPLETED = "notion.sync_completed"

    # Audit
    AUDIT_RECORD_WRITTEN = "audit.record_written"

    # Access
    ACCESS_REQUEST_CREATED = "access.request_created"
    ACCESS_PROVISIONED = "access.provisioned"

    # Pipeline
    PIPELINE_RUN_STARTED = "pipeline.run_started"
    PIPELINE_RUN_COMPLETED = "pipeline.run_completed"

    # Deployment
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_SUCCEEDED = "deployment.succeeded"
    DEPLOYMENT_FAILED = "deployment.failed"

    # Artifact
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_PUBLISHED = "artifact.published"

    # Documentation
    DOCUMENTATION_GENERATED = "documentation.generated"
    DOCUMENTATION_PUBLISHED = "documentation.published"

    # Training
    TRAINING_PLAN_GENERATED = "training.plan_generated"
    TRAINING_MATERIAL_PUBLISHED = "training.material_published"

    # Communication
    COMMUNICATION_SENT = "communication.sent"

    # Agent runtime
    AGENT_RUN_STARTED = "agent.run_started"
    AGENT_RUN_COMPLETED = "agent.run_completed"
    AGENT_RUN_FAILED = "agent.run_failed"

    @classmethod
    def all_names(cls) -> list[str]:
        """Return every event name defined in the taxonomy."""
        return [
            v
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str) and k != "all_names"
        ]


# ---------------------------------------------------------------------------
# Domain event model
# ---------------------------------------------------------------------------

class DomainEvent(BaseModel):
    """Pydantic v2 model for an in-process domain event."""

    event_id: str = Field(default_factory=generate_id)
    event_name: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str | None = Field(
        default_factory=get_current_correlation_id
    )
    actor_type: str  # "human", "agent", "system"
    actor_id: str
    object_type: str
    object_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event handler type
# ---------------------------------------------------------------------------

EventHandler = Callable[[DomainEvent], Awaitable[None] | None]


# ---------------------------------------------------------------------------
# EventBus — in-process pub/sub
# ---------------------------------------------------------------------------

class EventBus:
    """Simple in-process publish/subscribe bus for domain events.

    Supports both sync and async handlers.  Handlers are invoked in
    registration order when ``emit`` (async) or ``emit_sync`` is called.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    # -- registration -------------------------------------------------------

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register *handler* to be called whenever *event_name* is emitted."""
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove *handler* from the subscriber list for *event_name*."""
        self._handlers[event_name] = [
            h for h in self._handlers[event_name] if h is not handler
        ]

    # -- emission -----------------------------------------------------------

    async def emit(self, event: DomainEvent) -> None:
        """Emit *event* to all registered handlers (async-aware)."""
        for handler in self._handlers.get(event.event_name, []):
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result

    def emit_sync(self, event: DomainEvent) -> None:
        """Emit *event* synchronously.  Async handlers are NOT awaited."""
        for handler in self._handlers.get(event.event_name, []):
            result = handler(event)
            if asyncio.iscoroutine(result):
                result.close()  # prevent RuntimeWarning

    # -- convenience --------------------------------------------------------

    def handler_count(self, event_name: str) -> int:
        return len(self._handlers.get(event_name, []))


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def emit_event(
    bus: EventBus,
    name: str,
    *,
    object_type: str,
    object_id: str,
    payload: dict[str, Any] | None = None,
    actor_type: str = "system",
    actor_id: str = "omdt",
    metadata: dict[str, Any] | None = None,
) -> DomainEvent:
    """Build a :class:`DomainEvent`, emit it synchronously on *bus*, and
    return it.
    """
    event = DomainEvent(
        event_name=name,
        actor_type=actor_type,
        actor_id=actor_id,
        object_type=object_type,
        object_id=object_id,
        payload=payload or {},
        metadata=metadata or {},
    )
    bus.emit_sync(event)
    return event


# ---------------------------------------------------------------------------
# Module-level convenience API — simpler interface for services & tests
# ---------------------------------------------------------------------------

_handlers: dict[str, list[Callable]] = defaultdict(list)


def subscribe(event_name: str, handler: Callable) -> None:
    """Register a handler for *event_name* at module level."""
    _handlers[event_name].append(handler)


async def emit(event_name: str, payload: dict[str, Any]) -> None:
    """Emit an event to all module-level handlers.

    Handlers receive the raw payload dict (not a DomainEvent).
    """
    for handler in _handlers.get(event_name, []):
        result = handler(payload)
        if asyncio.iscoroutine(result):
            await result


def clear_handlers() -> None:
    """Remove all module-level handlers (for testing)."""
    _handlers.clear()
