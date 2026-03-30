"""Vendor & FinOps Agent — vendor briefs, cost summaries, renewal tasks."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VendorBrief(BaseModel):
    """Vendor evaluation brief."""

    brief_id: str = Field(default_factory=generate_id)
    vendor_name: str
    category: str = ""
    capabilities: list[str] = Field(default_factory=list)
    pricing_model: str = ""
    contract_term: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    recommendation: str = ""


class CostSummary(BaseModel):
    """Cost summary for vendor or tool."""

    summary_id: str = Field(default_factory=generate_id)
    vendor_name: str = ""
    monthly_cost: float = 0.0
    annual_cost: float = 0.0
    cost_trend: str = "stable"  # increasing | decreasing | stable
    optimization_opportunities: list[str] = Field(default_factory=list)


class RenewalTask(BaseModel):
    """Vendor renewal or procurement task."""

    task_id: str = Field(default_factory=generate_id)
    vendor_name: str
    action: str  # renew | evaluate | cancel | negotiate
    due_date: str = ""
    budget_impact: str = ""
    requires_approval: bool = True


class VendorFinOpsInput(BaseModel):
    """Input data for the Vendor & FinOps Agent."""

    vendor_request: str
    vendor_name: str = ""
    budget: float = 0.0


class VendorFinOpsOutput(BaseModel):
    """Output of the Vendor & FinOps Agent."""

    vendor_brief: VendorBrief | None = None
    cost_summary: CostSummary | None = None
    renewal_task: RenewalTask | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class VendorFinOpsAgent(BaseAgent):
    """Manages vendor evaluation, cost optimization, and procurement."""

    name = "vendor_finops_agent"
    mission = (
        "Evaluate vendors, optimize cloud and tool costs, manage "
        "procurement workflows, and produce cost reports."
    )
    allowed_tools = [
        "query_costs",
        "evaluate_vendor",
        "create_procurement_request",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["vendor_request"]
    output_schema = VendorFinOpsOutput
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

        parsed = VendorFinOpsInput.model_validate(inputs)
        vendor_name = parsed.vendor_name or "Unknown Vendor"

        vendor_brief = VendorBrief(
            vendor_name=vendor_name,
            category="data_tooling",
            capabilities=["data processing", "analytics", "visualization"],
            pricing_model="subscription",
            contract_term="annual",
            risk_factors=["vendor_lock_in", "price_escalation"],
            recommendation=f"Evaluate {vendor_name} against alternatives before committing",
        )

        cost_summary = CostSummary(
            vendor_name=vendor_name,
            monthly_cost=parsed.budget / 12 if parsed.budget else 0.0,
            annual_cost=parsed.budget,
            cost_trend="stable",
            optimization_opportunities=[
                "Negotiate volume discount",
                "Review unused licenses",
            ],
        )

        renewal_task = RenewalTask(
            vendor_name=vendor_name,
            action="evaluate",
            budget_impact=f"${parsed.budget:,.2f}/year" if parsed.budget else "TBD",
            requires_approval=True,
        )

        output = VendorFinOpsOutput(
            vendor_brief=vendor_brief,
            cost_summary=cost_summary,
            renewal_task=renewal_task,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
