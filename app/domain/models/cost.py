"""Cost and tool-usage event models."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CostEvent(BaseModel):
    """A cost attribution event for tool or infrastructure usage."""

    id: UUID
    project_id: UUID | None = None
    work_item_id: UUID | None = None
    tool_name: str
    usage_quantity: float
    usage_unit: str
    estimated_cost_usd: float | None = None
    correlation_id: str | None = None
    created_at: datetime


class ToolUsageEvent(BaseModel):
    """Records a single tool invocation for usage tracking."""

    id: UUID
    agent_run_id: UUID | None = None
    tool_name: str
    action: str | None = None
    duration_ms: int | None = None
    success: bool = True
    error_message: str | None = None
    created_at: datetime
