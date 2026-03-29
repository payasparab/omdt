"""Agent-run domain model (Appendix F)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentRun(BaseModel):
    """Records a single invocation of a specialist agent."""

    id: UUID
    work_item_id: UUID | None = None
    agent_name: str
    prompt_version: str | None = None
    status: str
    correlation_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
