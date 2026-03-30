"""Data PMO Agent — RAID log, status digest, follow-up queue."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RAIDItem(BaseModel):
    """A single RAID log entry."""

    item_id: str = Field(default_factory=generate_id)
    category: str  # risk | assumption | issue | dependency
    description: str
    owner: str = ""
    status: str = "open"
    priority: str = "medium"


class RAIDLog(BaseModel):
    """RAID log for a project or portfolio."""

    log_id: str = Field(default_factory=generate_id)
    project_id: str = ""
    items: list[RAIDItem] = Field(default_factory=list)
    summary: str = ""


class StatusDigest(BaseModel):
    """Status digest / standup summary."""

    digest_id: str = Field(default_factory=generate_id)
    period: str = ""
    completed: list[str] = Field(default_factory=list)
    in_progress: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    upcoming: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class FollowUpItem(BaseModel):
    """A follow-up action item."""

    item_id: str = Field(default_factory=generate_id)
    description: str
    assignee: str = ""
    due_date: str = ""
    priority: str = "medium"


class DataPMOInput(BaseModel):
    """Input data for the Data PMO Agent."""

    report_request: str
    project_id: str = ""
    period: str = "this_week"


class DataPMOOutput(BaseModel):
    """Output of the Data PMO Agent."""

    raid_log: RAIDLog | None = None
    status_digest: StatusDigest | None = None
    follow_up_queue: list[FollowUpItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DataPMOAgent(BaseAgent):
    """Manages project status, reporting, and portfolio oversight."""

    name = "data_pmo"
    mission = (
        "Track project status, generate standup summaries, produce "
        "portfolio reports, manage timelines, and escalate blockers."
    )
    allowed_tools = [
        "query_work_items",
        "generate_status_report",
        "update_timeline",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["report_request"]
    output_schema = DataPMOOutput
    handoff_targets = ["data_pm", "head_of_data"]

    async def execute(self, context: AgentContext) -> AgentResult:
        inputs = context.input_data
        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        parsed = DataPMOInput.model_validate(inputs)

        raid_log = RAIDLog(
            project_id=parsed.project_id or context.project_id or "",
            items=[
                RAIDItem(category="risk", description="Timeline pressure on deliverables", priority="high"),
                RAIDItem(category="assumption", description="Data sources remain stable"),
                RAIDItem(category="issue", description="Pending access approval blocking development", status="open"),
                RAIDItem(category="dependency", description="Upstream pipeline must complete first"),
            ],
            summary=f"RAID log for: {parsed.report_request[:60]}",
        )

        status_digest = StatusDigest(
            period=parsed.period,
            completed=["Initial data profiling", "Schema design review"],
            in_progress=["Pipeline development", "Dashboard wireframes"],
            blocked=["Access provisioning for production"],
            upcoming=["UAT testing", "Deployment planning"],
            highlights=["On track for milestone delivery"],
        )

        follow_ups = [
            FollowUpItem(description="Follow up on access request", assignee="admin", priority="high"),
            FollowUpItem(description="Review pipeline test results", assignee="engineer", priority="medium"),
        ]

        output = DataPMOOutput(
            raid_log=raid_log,
            status_digest=status_digest,
            follow_up_queue=follow_ups,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
