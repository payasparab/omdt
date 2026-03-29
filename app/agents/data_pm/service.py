"""Data PM Agent — drafts PRDs from structured context."""
from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.data_pm.schemas import (
    AcceptanceCriterion,
    DataPMInput,
    Milestone,
    PRDDraftOutput,
    Risk,
)
from app.core.ids import generate_id


class DataPMAgent(BaseAgent):
    """Drafts PRDs, generates acceptance criteria, milestones, and risks.

    Implements the Data PM role from PRD section 10 and 11.6.
    """

    name = "data_pm"
    mission = (
        "Draft product requirements documents from structured context, "
        "generate acceptance criteria, milestones, and risks, and manage "
        "PRD review and feedback incorporation."
    )
    allowed_tools = [
        "create_prd_revision",
        "update_prd_revision",
        "create_conversation_thread",
        "request_feedback",
        "create_linear_issue",
        "update_linear_issue",
        "attach_artifact",
        "request_technical_writer_handoff",
    ]
    required_inputs = ["work_item_id", "title", "description"]
    output_schema = PRDDraftOutput
    handoff_targets = ["technical_writer_agent", "head_of_data"]

    async def execute(self, context: AgentContext) -> AgentResult:
        """Generate a PRD draft from the provided context."""
        inputs = context.input_data

        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        pm_input = DataPMInput.model_validate(inputs)

        # Generate acceptance criteria from description
        acceptance_criteria = _generate_acceptance_criteria(pm_input)

        # Generate milestones
        milestones = _generate_milestones(pm_input)

        # Identify risks
        risks = _identify_risks(pm_input)

        # Build assumptions
        assumptions = _build_assumptions(pm_input)

        # Determine required agents based on route
        required_agents = _determine_agents(pm_input.route_key)

        prd = PRDDraftOutput(
            work_item_id=pm_input.work_item_id,
            prd_title=f"PRD: {pm_input.title}",
            executive_summary=(
                f"This document defines the requirements for: {pm_input.title}. "
                f"{pm_input.description}"
            ),
            business_goal=pm_input.business_goal or "To be confirmed with stakeholders.",
            scope=pm_input.description,
            out_of_scope="Items not explicitly listed in scope.",
            acceptance_criteria=acceptance_criteria,
            milestones=milestones,
            risks=risks,
            assumptions=assumptions,
            stakeholders=[pm_input.requester] if pm_input.requester else [],
            required_agents=required_agents,
            handoff_to="technical_writer_agent",
            revision_number=1,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=prd.model_dump(),
        )


def _generate_acceptance_criteria(pm_input: DataPMInput) -> list[AcceptanceCriterion]:
    """Generate acceptance criteria from the input context."""
    criteria = [
        AcceptanceCriterion(
            criterion_id=generate_id(),
            description=f"Deliverable matches the stated requirement: {pm_input.title}",
            verification_method="Manual review by requester",
        ),
        AcceptanceCriterion(
            criterion_id=generate_id(),
            description="All outputs pass data quality checks",
            verification_method="Automated quality validation",
        ),
        AcceptanceCriterion(
            criterion_id=generate_id(),
            description="Documentation is complete and published",
            verification_method="Technical writer sign-off",
        ),
    ]
    if pm_input.source_data:
        criteria.append(AcceptanceCriterion(
            criterion_id=generate_id(),
            description=f"Source data from '{pm_input.source_data}' is validated",
            verification_method="Data quality agent check",
        ))
    return criteria


def _generate_milestones(pm_input: DataPMInput) -> list[Milestone]:
    """Generate standard project milestones."""
    return [
        Milestone(name="Requirements Finalized", description="PRD approved by stakeholders"),
        Milestone(name="Implementation Complete", description="Core deliverable built and tested"),
        Milestone(name="Review & QA", description="Quality checks and stakeholder review"),
        Milestone(name="Deployment & Handoff", description="Deployed and handed off to operations"),
    ]


def _identify_risks(pm_input: DataPMInput) -> list[Risk]:
    """Identify project risks from context."""
    risks = [
        Risk(
            description="Requirements may change during implementation",
            likelihood="medium",
            impact="medium",
            mitigation="Iterative PRD review with stakeholders",
        ),
    ]
    if not pm_input.source_data:
        risks.append(Risk(
            description="Source data not yet identified",
            likelihood="high",
            impact="high",
            mitigation="Clarification needed before implementation begins",
        ))
    if pm_input.priority == "critical":
        risks.append(Risk(
            description="Critical priority may compress quality assurance time",
            likelihood="medium",
            impact="high",
            mitigation="Prioritize automated testing and incremental delivery",
        ))
    return risks


def _build_assumptions(pm_input: DataPMInput) -> list[str]:
    """Build project assumptions."""
    assumptions = [
        "Requester will be available for clarification during PRD review.",
        "Required system access is available or can be provisioned.",
    ]
    if pm_input.source_data:
        assumptions.append(
            f"Source data '{pm_input.source_data}' is accessible and documented."
        )
    return assumptions


def _determine_agents(route_key: str) -> list[str]:
    """Determine which specialist agents are needed."""
    from app.agents.routing import ROUTE_TO_AGENT

    agent = ROUTE_TO_AGENT.get(route_key)
    agents = []
    if agent and agent not in ("triage_agent", "data_pm"):
        agents.append(agent)
    return agents
