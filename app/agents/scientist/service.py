"""Data Scientist Agent — stub implementation."""
from __future__ import annotations

from pydantic import BaseModel

from app.agents.base import AgentContext, AgentResult, BaseAgent


class DataScientistOutput(BaseModel):
    """Placeholder output schema for the Data Scientist Agent."""

    message: str = "not yet implemented"


class DataScientistAgent(BaseAgent):
    """Designs experiments, trains models, and evaluates ML approaches.

    Stub — full implementation pending.
    """

    name = "data_scientist"
    mission = (
        "Design experiments, train and evaluate machine learning models, "
        "manage feature engineering, and produce model performance reports."
    )
    allowed_tools = [
        "run_experiment",
        "train_model",
        "evaluate_model",
        "register_model",
        "attach_artifact",
        "request_handoff",
    ]
    required_inputs = ["experiment_request"]
    output_schema = DataScientistOutput
    handoff_targets = ["data_engineer", "data_pm"]

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status="success",
            outputs={"message": "DataScientistAgent not yet implemented"},
        )
