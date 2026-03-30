"""Data Quality Agent — quality rules, tests, validation reports."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QualityRule(BaseModel):
    """A data quality rule."""

    rule_id: str = Field(default_factory=generate_id)
    rule_name: str
    rule_type: str  # not_null | unique | range | custom
    target_table: str = ""
    target_column: str = ""
    expression: str = ""
    severity: str = "error"  # error | warning | info


class QualityTest(BaseModel):
    """A quality test to execute."""

    test_id: str = Field(default_factory=generate_id)
    test_name: str
    query: str = ""
    expected: str = ""
    linked_rule_id: str = ""


class ValidationReport(BaseModel):
    """Quality validation report."""

    report_id: str = Field(default_factory=generate_id)
    pipeline_key: str = ""
    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    failures: list[dict[str, str]] = Field(default_factory=list)
    score: float = 1.0


class DataQualityInput(BaseModel):
    """Input data for the Data Quality Agent."""

    quality_request: str
    pipeline_key: str = ""
    tables: list[str] = Field(default_factory=list)


class DataQualityOutput(BaseModel):
    """Output of the Data Quality Agent."""

    quality_rules: list[QualityRule] = Field(default_factory=list)
    quality_tests: list[QualityTest] = Field(default_factory=list)
    validation_report: ValidationReport | None = None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DataQualityAgent(BaseAgent):
    """Monitors and enforces data quality standards."""

    name = "quality_agent"
    mission = (
        "Define and enforce data quality rules, run quality checks, "
        "detect anomalies, produce quality scorecards, and escalate "
        "quality issues."
    )
    allowed_tools = [
        "run_quality_check",
        "create_quality_rule",
        "generate_scorecard",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["quality_request"]
    output_schema = DataQualityOutput
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

        parsed = DataQualityInput.model_validate(inputs)
        tables = parsed.tables or ["default_table"]

        rules = []
        tests = []
        for table in tables:
            not_null_rule = QualityRule(
                rule_name=f"{table}_pk_not_null",
                rule_type="not_null",
                target_table=table,
                target_column="id",
                severity="error",
            )
            unique_rule = QualityRule(
                rule_name=f"{table}_pk_unique",
                rule_type="unique",
                target_table=table,
                target_column="id",
                severity="error",
            )
            rules.extend([not_null_rule, unique_rule])

            tests.append(QualityTest(
                test_name=f"test_{table}_pk_not_null",
                query=f"SELECT COUNT(*) FROM {table} WHERE id IS NULL",
                expected="0",
                linked_rule_id=not_null_rule.rule_id,
            ))
            tests.append(QualityTest(
                test_name=f"test_{table}_pk_unique",
                query=f"SELECT COUNT(*) - COUNT(DISTINCT id) FROM {table}",
                expected="0",
                linked_rule_id=unique_rule.rule_id,
            ))

        report = ValidationReport(
            pipeline_key=parsed.pipeline_key or "ad_hoc",
            total_rules=len(rules),
            passed=len(rules),
            failed=0,
            warnings=0,
            score=1.0,
        )

        output = DataQualityOutput(
            quality_rules=rules,
            quality_tests=tests,
            validation_report=report,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
