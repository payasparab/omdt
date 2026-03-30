"""Costing and tool usage tracking service.

Records cost events, tool usage, and provides aggregation/attribution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.models.cost import CostEvent, ToolUsageEvent

# In-memory stores.
_cost_store: dict[str, CostEvent] = {}
_usage_store: dict[str, ToolUsageEvent] = {}


def get_cost_store() -> dict[str, CostEvent]:
    return _cost_store


def get_usage_store() -> dict[str, ToolUsageEvent]:
    return _usage_store


def clear_store() -> None:
    _cost_store.clear()
    _usage_store.clear()


async def record_cost_event(
    *,
    tool_name: str,
    usage_quantity: float,
    usage_unit: str,
    estimated_cost_usd: float | None = None,
    project_id: UUID | None = None,
    work_item_id: UUID | None = None,
) -> CostEvent:
    """Record a cost attribution event."""
    now = datetime.now(timezone.utc)
    corr_id = generate_correlation_id()
    event = CostEvent(
        id=uuid4(),
        tool_name=tool_name,
        usage_quantity=usage_quantity,
        usage_unit=usage_unit,
        estimated_cost_usd=estimated_cost_usd,
        project_id=project_id,
        work_item_id=work_item_id,
        correlation_id=corr_id,
        created_at=now,
    )
    _cost_store[str(event.id)] = event

    await emit(
        "cost.recorded",
        {
            "cost_event_id": str(event.id),
            "tool_name": tool_name,
            "amount": estimated_cost_usd,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="cost.recorded",
        actor_type="system",
        actor_id="costing",
        object_type="cost_event",
        object_id=str(event.id),
        change_summary=f"Cost recorded: {tool_name} {usage_quantity} {usage_unit}",
        correlation_id=corr_id,
    )
    return event


async def record_tool_usage(
    *,
    tool_name: str,
    action: str | None = None,
    duration_ms: int | None = None,
    success: bool = True,
    error_message: str | None = None,
    agent_run_id: UUID | None = None,
) -> ToolUsageEvent:
    """Record a tool usage event."""
    now = datetime.now(timezone.utc)
    event = ToolUsageEvent(
        id=uuid4(),
        tool_name=tool_name,
        action=action,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
        agent_run_id=agent_run_id,
        created_at=now,
    )
    _usage_store[str(event.id)] = event
    return event


async def get_project_costs(project_id: str) -> dict[str, Any]:
    """Get cost summary for a project."""
    pid = UUID(project_id)
    events = [e for e in _cost_store.values() if e.project_id == pid]
    total = sum(e.estimated_cost_usd or 0.0 for e in events)
    by_tool: dict[str, float] = {}
    for e in events:
        by_tool[e.tool_name] = by_tool.get(e.tool_name, 0.0) + (e.estimated_cost_usd or 0.0)

    return {
        "project_id": project_id,
        "total_cost_usd": total,
        "event_count": len(events),
        "by_tool": by_tool,
    }


async def get_tool_costs(
    tool_name: str,
    *,
    after: datetime | None = None,
    before: datetime | None = None,
) -> dict[str, Any]:
    """Get cost summary for a specific tool within a time period."""
    events = [e for e in _cost_store.values() if e.tool_name == tool_name]
    if after:
        events = [e for e in events if e.created_at >= after]
    if before:
        events = [e for e in events if e.created_at <= before]

    total = sum(e.estimated_cost_usd or 0.0 for e in events)
    total_quantity = sum(e.usage_quantity for e in events)

    return {
        "tool_name": tool_name,
        "total_cost_usd": total,
        "total_quantity": total_quantity,
        "event_count": len(events),
    }


async def attribute_cost(
    cost_event_id: str,
    project_id: str,
) -> CostEvent | None:
    """Attribute a cost event to a project."""
    event = _cost_store.get(cost_event_id)
    if event is None:
        return None

    event.project_id = UUID(project_id)
    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="cost.attributed",
        actor_type="system",
        actor_id="costing",
        object_type="cost_event",
        object_id=cost_event_id,
        change_summary=f"Cost attributed to project {project_id}",
        correlation_id=corr_id,
    )
    return event
