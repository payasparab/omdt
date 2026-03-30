"""Data Engineer Agent — pipeline specs, jobs, transforms."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PipelineSpec(BaseModel):
    """Pipeline specification."""

    spec_id: str = Field(default_factory=generate_id)
    pipeline_name: str
    pipeline_type: str  # sql_transformation | python_batch | data_ingestion
    source_tables: list[str] = Field(default_factory=list)
    target_tables: list[str] = Field(default_factory=list)
    schedule: str = "daily"
    quality_checks: list[str] = Field(default_factory=list)


class JobDefinition(BaseModel):
    """Individual job within a pipeline."""

    job_id: str = Field(default_factory=generate_id)
    job_name: str
    job_type: str  # sql | python | dbt
    dependencies: list[str] = Field(default_factory=list)
    timeout_seconds: int = 3600


class TransformSpec(BaseModel):
    """Data transformation specification."""

    transform_id: str = Field(default_factory=generate_id)
    transform_name: str
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    logic_summary: str = ""


class DataEngineerInput(BaseModel):
    """Input data for the Data Engineer Agent."""

    pipeline_request: str
    source_tables: list[str] = Field(default_factory=list)
    target_tables: list[str] = Field(default_factory=list)
    pipeline_type: str = "sql_transformation"


class DataEngineerOutput(BaseModel):
    """Output of the Data Engineer Agent."""

    pipeline_spec: PipelineSpec | None = None
    jobs: list[JobDefinition] = Field(default_factory=list)
    transforms: list[TransformSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DataEngineerAgent(BaseAgent):
    """Builds and maintains data pipelines, transformations, and ingestion."""

    name = "data_engineer"
    mission = (
        "Build, deploy, and maintain data pipelines, manage ETL/ELT "
        "transformations, ensure data ingestion reliability, and "
        "optimize query performance."
    )
    allowed_tools = [
        "run_dbt",
        "run_sql_query",
        "deploy_pipeline",
        "create_table",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["pipeline_request"]
    output_schema = DataEngineerOutput
    handoff_targets = ["data_architect", "deployment_agent"]

    async def execute(self, context: AgentContext) -> AgentResult:
        inputs = context.input_data
        missing = self.validate_inputs(inputs)
        if missing:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Missing required inputs: {missing}"],
            )

        parsed = DataEngineerInput.model_validate(inputs)

        pipeline_spec = PipelineSpec(
            pipeline_name=f"pipeline_{parsed.pipeline_request[:40].replace(' ', '_').lower()}",
            pipeline_type=parsed.pipeline_type,
            source_tables=parsed.source_tables or ["raw.source_table"],
            target_tables=parsed.target_tables or ["analytics.target_table"],
            schedule="daily",
            quality_checks=["row_count", "null_check", "freshness"],
        )

        jobs = [
            JobDefinition(
                job_name="extract",
                job_type="sql",
                dependencies=[],
                timeout_seconds=1800,
            ),
            JobDefinition(
                job_name="transform",
                job_type="dbt",
                dependencies=["extract"],
                timeout_seconds=3600,
            ),
            JobDefinition(
                job_name="load",
                job_type="sql",
                dependencies=["transform"],
                timeout_seconds=1800,
            ),
        ]

        transforms = [
            TransformSpec(
                transform_name="main_transform",
                input_schema={"source": "raw"},
                output_schema={"target": "analytics"},
                logic_summary=f"Transform for: {parsed.pipeline_request[:60]}",
            ),
        ]

        output = DataEngineerOutput(
            pipeline_spec=pipeline_spec,
            jobs=jobs,
            transforms=transforms,
        )

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
