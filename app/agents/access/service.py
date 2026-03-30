"""Access & Security Agent — access packages, provisioning steps."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AccessPackage(BaseModel):
    """Access package describing what access is being granted."""

    package_id: str = Field(default_factory=generate_id)
    role_bundle: str
    resources: list[str] = Field(default_factory=list)
    justification: str = ""
    risk_assessment: str = "low"
    expiration_policy: str = ""
    requires_approval: bool = True


class ProvisioningStep(BaseModel):
    """A single provisioning step."""

    step_id: str = Field(default_factory=generate_id)
    order: int
    action: str
    target_system: str = "snowflake"
    parameters: dict[str, str] = Field(default_factory=dict)
    reversible: bool = True


class AccessSecurityInput(BaseModel):
    """Input data for the Access Security Agent."""

    access_request: str
    requester: str = ""
    role_bundle: str = ""
    resources: list[str] = Field(default_factory=list)


class AccessSecurityOutput(BaseModel):
    """Output of the Access Security Agent."""

    access_package: AccessPackage | None = None
    provisioning_steps: list[ProvisioningStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class AccessSecurityAgent(BaseAgent):
    """Manages access provisioning, policy checks, and security reviews."""

    name = "access_security_agent"
    mission = (
        "Process access requests, enforce security policies, provision "
        "roles and permissions, and audit access compliance."
    )
    allowed_tools = [
        "provision_role",
        "check_policy",
        "audit_access",
        "revoke_access",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["access_request"]
    output_schema = AccessSecurityOutput
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

        parsed = AccessSecurityInput.model_validate(inputs)

        access_package = AccessPackage(
            role_bundle=parsed.role_bundle or "analyst_read",
            resources=parsed.resources or ["warehouse.analytics"],
            justification=parsed.access_request,
            risk_assessment="low" if "read" in (parsed.role_bundle or "read").lower() else "medium",
            expiration_policy="90_days",
            requires_approval=True,
        )

        provisioning_steps = [
            ProvisioningStep(
                order=1,
                action="validate_policy",
                target_system="policy_engine",
                parameters={"role": access_package.role_bundle},
            ),
            ProvisioningStep(
                order=2,
                action="create_user_if_needed",
                target_system="snowflake",
                parameters={"username": parsed.requester or "unknown"},
            ),
            ProvisioningStep(
                order=3,
                action="grant_role",
                target_system="snowflake",
                parameters={"role": access_package.role_bundle, "username": parsed.requester or "unknown"},
            ),
            ProvisioningStep(
                order=4,
                action="verify_access",
                target_system="snowflake",
                parameters={"username": parsed.requester or "unknown"},
            ),
        ]

        output = AccessSecurityOutput(
            access_package=access_package,
            provisioning_steps=provisioning_steps,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
