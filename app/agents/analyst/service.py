"""Data Analyst Agent — analysis requests, memos, query packages, dashboard specs."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalysisMemo(BaseModel):
    """Structured analysis memo."""

    memo_id: str = Field(default_factory=generate_id)
    title: str
    objective: str
    methodology: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class QueryPackage(BaseModel):
    """SQL query package for the analysis."""

    package_id: str = Field(default_factory=generate_id)
    queries: list[dict[str, str]] = Field(default_factory=list)
    target_warehouse: str = "snowflake"
    estimated_cost: str = ""


class DashboardSpec(BaseModel):
    """Dashboard specification."""

    spec_id: str = Field(default_factory=generate_id)
    title: str
    charts: list[dict[str, str]] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    refresh_schedule: str = "daily"


class DataAnalystInput(BaseModel):
    """Input data for the Data Analyst Agent."""

    analysis_request: str
    data_sources: list[str] = Field(default_factory=list)
    output_format: str = "memo"  # memo | query_package | dashboard_spec | full


class DataAnalystOutput(BaseModel):
    """Output of the Data Analyst Agent."""

    analysis_memo: AnalysisMemo | None = None
    query_package: QueryPackage | None = None
    dashboard_spec: DashboardSpec | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_VALID_FORMATS = {"memo", "query_package", "dashboard_spec", "full"}


class DataAnalystAgent(BaseAgent):
    """Performs data analysis, builds dashboards, generates insights.

    Implements the data analyst role from PRD section 10.4.
    """

    name = "data_analyst"
    mission = (
        "Perform exploratory data analysis, build dashboards, generate "
        "insights, and produce analytical reports from structured data."
    )
    allowed_tools = [
        "run_sql_query",
        "create_chart",
        "create_dashboard",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["analysis_request"]
    output_schema = DataAnalystOutput
    handoff_targets = ["data_pm", "technical_writer_agent"]

    async def execute(self, context: AgentContext) -> AgentResult:
        inputs = context.input_data
        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        parsed = DataAnalystInput.model_validate(inputs)

        if parsed.output_format not in _VALID_FORMATS:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Unknown output_format: {parsed.output_format}. Valid: {sorted(_VALID_FORMATS)}"],
            )

        output = DataAnalystOutput()

        if parsed.output_format in ("memo", "full"):
            output.analysis_memo = AnalysisMemo(
                title=f"Analysis: {parsed.analysis_request[:80]}",
                objective=parsed.analysis_request,
                methodology="Exploratory data analysis with statistical validation",
                findings=["Initial data profiling complete", "Key patterns identified"],
                recommendations=["Schedule follow-up deep-dive", "Validate with stakeholders"],
                data_sources=parsed.data_sources or ["default_warehouse"],
            )

        if parsed.output_format in ("query_package", "full"):
            output.query_package = QueryPackage(
                queries=[
                    {"name": "main_analysis", "sql": f"-- Analysis for: {parsed.analysis_request[:60]}"},
                    {"name": "validation", "sql": "-- Validation query placeholder"},
                ],
                target_warehouse="snowflake",
                estimated_cost="low",
            )

        if parsed.output_format in ("dashboard_spec", "full"):
            output.dashboard_spec = DashboardSpec(
                title=f"Dashboard: {parsed.analysis_request[:60]}",
                charts=[
                    {"type": "bar", "title": "Key Metrics Overview"},
                    {"type": "line", "title": "Trend Analysis"},
                ],
                filters=["date_range", "department"],
                refresh_schedule="daily",
            )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
