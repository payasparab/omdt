"""Comms & Publishing Agent — email packages, publish requests, update notes."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EmailPackage(BaseModel):
    """Email package for stakeholder communication."""

    package_id: str = Field(default_factory=generate_id)
    subject: str
    body: str
    recipients: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    priority: str = "normal"  # low | normal | high


class PublishRequest(BaseModel):
    """Request to publish content to a channel."""

    request_id: str = Field(default_factory=generate_id)
    channel: str  # notion | linear | email | slack
    content_type: str = "update"  # update | announcement | report
    title: str = ""
    body: str = ""
    audience: list[str] = Field(default_factory=list)


class UpdateNote(BaseModel):
    """Status update note for stakeholders."""

    note_id: str = Field(default_factory=generate_id)
    milestone: str
    summary: str
    key_changes: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class CommsPublishingInput(BaseModel):
    """Input data for the Comms & Publishing Agent."""

    comms_request: str
    milestone: str = ""
    recipients: list[str] = Field(default_factory=list)
    channel: str = "email"


class CommsPublishingOutput(BaseModel):
    """Output of the Comms & Publishing Agent."""

    email_package: EmailPackage | None = None
    publish_request: PublishRequest | None = None
    update_note: UpdateNote | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CommsPublishingAgent(BaseAgent):
    """Manages communications, email packages, and content publishing."""

    name = "comms_publishing_agent"
    mission = (
        "Draft and send communications, create email packages, publish "
        "content to stakeholders, and manage distribution lists."
    )
    allowed_tools = [
        "draft_email",
        "send_email",
        "publish_to_channel",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["comms_request"]
    output_schema = CommsPublishingOutput
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

        parsed = CommsPublishingInput.model_validate(inputs)
        milestone = parsed.milestone or "project update"

        email_package = EmailPackage(
            subject=f"Update: {milestone}",
            body=f"Dear stakeholders,\n\n{parsed.comms_request}\n\nBest regards,\nData Team",
            recipients=parsed.recipients or ["stakeholders@example.com"],
            priority="normal",
        )

        publish_request = PublishRequest(
            channel=parsed.channel,
            content_type="update",
            title=f"Milestone Update: {milestone}",
            body=parsed.comms_request,
            audience=parsed.recipients or ["all_stakeholders"],
        )

        update_note = UpdateNote(
            milestone=milestone,
            summary=parsed.comms_request,
            key_changes=["Milestone reached", "Deliverables on track"],
            next_steps=["Continue to next phase", "Schedule review meeting"],
            blockers=[],
        )

        output = CommsPublishingOutput(
            email_package=email_package,
            publish_request=publish_request,
            update_note=update_note,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
