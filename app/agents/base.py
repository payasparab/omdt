"""Base agent class — ABC for all OMDT specialist agents."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.ids import generate_id


# ---------------------------------------------------------------------------
# Agent result & context models
# ---------------------------------------------------------------------------

class AgentResult(BaseModel):
    """Outcome of a single agent execution."""

    agent_name: str
    run_id: str = Field(default_factory=generate_id)
    status: str  # "success" | "failure" | "timeout"
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    prompt_version: str | None = None


class AgentContext(BaseModel):
    """Execution context passed to every agent invocation."""

    correlation_id: str
    work_item_id: str | None = None
    project_id: str | None = None
    actor_type: str = "system"
    actor_id: str = "omdt"
    allowed_tools: list[str] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt directory
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "system"


# ---------------------------------------------------------------------------
# BaseAgent ABC
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """Abstract base class for all OMDT specialist agents.

    Subclasses must implement :meth:`execute` and declare their
    ``name``, ``mission``, ``allowed_tools``, ``required_inputs``,
    and ``output_schema``.
    """

    name: str = ""
    mission: str = ""
    allowed_tools: list[str] = []
    required_inputs: list[str] = []
    output_schema: type[BaseModel] = BaseModel
    handoff_targets: list[str] = []

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the agent logic and return a result."""
        ...

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Return a list of missing required input field names."""
        return [field for field in self.required_inputs if field not in inputs]

    def validate_outputs(self, outputs: dict[str, Any]) -> bool:
        """Return True if *outputs* conform to the agent's output schema."""
        try:
            self.output_schema.model_validate(outputs)
            return True
        except Exception:
            return False

    def get_prompt(self) -> str:
        """Load and return the agent's system prompt from its Markdown file."""
        prompt_file = _PROMPTS_DIR / f"{self.name}.md"
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt file not found for agent '{self.name}': {prompt_file}"
            )
        return prompt_file.read_text(encoding="utf-8")

    def get_prompt_version(self) -> str:
        """Return a SHA-256 hash of the prompt file content as a version."""
        content = self.get_prompt()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def get_handoff_targets(self) -> list[str]:
        """Return agent names this agent can hand off work to."""
        return list(self.handoff_targets)
