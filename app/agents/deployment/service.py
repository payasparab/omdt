"""Deployment Agent — release plans, deploy records, rollback plans."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReleasePlan(BaseModel):
    """Release plan for a deployment."""

    plan_id: str = Field(default_factory=generate_id)
    release_name: str
    environment: str = "staging"
    steps: list[str] = Field(default_factory=list)
    pre_deploy_checks: list[str] = Field(default_factory=list)
    post_deploy_checks: list[str] = Field(default_factory=list)
    rollback_trigger: str = ""
    requires_approval: bool = True


class DeployRecord(BaseModel):
    """Record of a deployment execution."""

    record_id: str = Field(default_factory=generate_id)
    git_sha: str = ""
    environment: str = ""
    status: str = "planned"  # planned | in_progress | succeeded | failed
    smoke_test_result: str = ""
    notes: str = ""


class RollbackPlan(BaseModel):
    """Rollback plan in case of deployment failure."""

    plan_id: str = Field(default_factory=generate_id)
    rollback_steps: list[str] = Field(default_factory=list)
    rollback_sha: str = ""
    data_migration_rollback: str = ""
    estimated_downtime: str = ""


class DeploymentAgentInput(BaseModel):
    """Input data for the Deployment Agent."""

    deployment_request: str
    git_sha: str = ""
    environment: str = "staging"
    linked_work_item_ids: list[str] = Field(default_factory=list)


class DeploymentAgentOutput(BaseModel):
    """Output of the Deployment Agent."""

    release_plan: ReleasePlan | None = None
    deploy_record: DeployRecord | None = None
    rollback_plan: RollbackPlan | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DeploymentAgent(BaseAgent):
    """Manages deployment lifecycle, rollbacks, and release orchestration."""

    name = "deployment_agent"
    mission = (
        "Orchestrate deployments, manage rollback procedures, verify "
        "deployment health, and coordinate release processes."
    )
    allowed_tools = [
        "deploy_artifact",
        "rollback_deployment",
        "verify_health",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["deployment_request"]
    output_schema = DeploymentAgentOutput
    handoff_targets = ["data_engineer", "data_pm"]

    async def execute(self, context: AgentContext) -> AgentResult:
        inputs = context.input_data
        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        parsed = DeploymentAgentInput.model_validate(inputs)

        release_plan = ReleasePlan(
            release_name=f"release_{parsed.deployment_request[:40].replace(' ', '_').lower()}",
            environment=parsed.environment,
            steps=[
                "Run pre-deploy checks",
                "Apply database migrations",
                "Deploy application",
                "Run smoke tests",
                "Verify health endpoints",
            ],
            pre_deploy_checks=["database_backup", "config_validation", "dependency_check"],
            post_deploy_checks=["smoke_test", "health_check", "metric_baseline"],
            rollback_trigger="smoke_test_failure OR health_check_failure",
            requires_approval=parsed.environment == "production",
        )

        deploy_record = DeployRecord(
            git_sha=parsed.git_sha or "pending",
            environment=parsed.environment,
            status="planned",
            notes=f"Deployment for: {parsed.deployment_request[:60]}",
        )

        rollback_plan = RollbackPlan(
            rollback_steps=[
                "Revert to previous deployment",
                "Rollback database migrations",
                "Verify rollback health",
                "Notify stakeholders",
            ],
            rollback_sha="previous_known_good",
            data_migration_rollback="Run reverse migration script",
            estimated_downtime="5-10 minutes",
        )

        output = DeploymentAgentOutput(
            release_plan=release_plan,
            deploy_record=deploy_record,
            rollback_plan=rollback_plan,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
