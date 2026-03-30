"""Data Architect Agent — schema design, DBML, architecture diagrams, data contracts."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DBMLSpec(BaseModel):
    """DBML schema specification."""

    spec_id: str = Field(default_factory=generate_id)
    tables: list[dict[str, object]] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
    dbml_content: str = ""


class ArchitectureDiagram(BaseModel):
    """Architecture diagram specification."""

    diagram_id: str = Field(default_factory=generate_id)
    diagram_type: str = "data_flow"  # data_flow | entity_relationship | system
    components: list[str] = Field(default_factory=list)
    connections: list[dict[str, str]] = Field(default_factory=list)
    mermaid_content: str = ""


class DataContract(BaseModel):
    """Data contract specification."""

    contract_id: str = Field(default_factory=generate_id)
    owner: str = ""
    consumers: list[str] = Field(default_factory=list)
    schema_definition: dict[str, object] = Field(default_factory=dict)
    sla: dict[str, str] = Field(default_factory=dict)
    quality_expectations: list[str] = Field(default_factory=list)


class DataArchitectInput(BaseModel):
    """Input data for the Data Architect Agent."""

    model_request: str
    tables: list[str] = Field(default_factory=list)
    output_format: str = "full"  # dbml | diagram | contract | full


class DataArchitectOutput(BaseModel):
    """Output of the Data Architect Agent."""

    dbml: DBMLSpec | None = None
    architecture_diagram: ArchitectureDiagram | None = None
    data_contracts: list[DataContract] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_VALID_FORMATS = {"dbml", "diagram", "contract", "full"}


class DataArchitectAgent(BaseAgent):
    """Designs data models, schemas, and architectural patterns."""

    name = "data_architect"
    mission = (
        "Design data models, define schema standards, produce ERDs and "
        "DBML, evaluate architectural trade-offs, and ensure data "
        "modeling best practices."
    )
    allowed_tools = [
        "generate_dbml",
        "generate_erd",
        "validate_schema",
        "create_migration",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["model_request"]
    output_schema = DataArchitectOutput
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

        parsed = DataArchitectInput.model_validate(inputs)

        if parsed.output_format not in _VALID_FORMATS:
            return AgentResult(
                agent_name=self.name,
                status="failure",
                errors=[f"Unknown output_format: {parsed.output_format}. Valid: {sorted(_VALID_FORMATS)}"],
            )

        output = DataArchitectOutput()

        if parsed.output_format in ("dbml", "full"):
            tables = parsed.tables or ["users", "orders"]
            table_defs = [{"name": t, "columns": [{"name": "id", "type": "uuid"}]} for t in tables]
            output.dbml = DBMLSpec(
                tables=table_defs,
                relationships=[{"from": tables[0], "to": tables[-1], "type": "one_to_many"}] if len(tables) > 1 else [],
                dbml_content="\n".join(f"Table {t} {{\n  id uuid [pk]\n}}" for t in tables),
            )

        if parsed.output_format in ("diagram", "full"):
            output.architecture_diagram = ArchitectureDiagram(
                diagram_type="data_flow",
                components=parsed.tables or ["source", "staging", "analytics"],
                connections=[{"from": "source", "to": "staging"}, {"from": "staging", "to": "analytics"}],
                mermaid_content=f"graph LR\n  A[Source] --> B[Staging] --> C[Analytics]",
            )

        if parsed.output_format in ("contract", "full"):
            output.data_contracts = [
                DataContract(
                    owner="data_team",
                    consumers=["analytics", "reporting"],
                    schema_definition={"version": "1.0", "tables": parsed.tables or []},
                    sla={"freshness": "24h", "availability": "99.9%"},
                    quality_expectations=["no_nulls_in_pk", "referential_integrity"],
                ),
            ]

        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs=output.model_dump(),
        )
