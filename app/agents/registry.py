"""Agent registry — registers, stores, and retrieves agent definitions."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.core.config import load_prompts_config


# ---------------------------------------------------------------------------
# Agent definition model
# ---------------------------------------------------------------------------

class AgentDefinition(BaseModel):
    """Metadata for a registered agent, combining config and runtime info."""

    name: str
    description: str = ""
    prompt_path: str = ""
    prompt_version: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    output_schema: str = "BaseModel"
    escalation_rules: list[str] = Field(default_factory=list)
    approval_boundaries: list[str] = Field(default_factory=list)
    handoff_targets: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Central registry that maps agent names to their class and definition."""

    def __init__(self) -> None:
        self._agents: dict[str, tuple[type[BaseAgent], AgentDefinition]] = {}

    def register(
        self,
        agent_name: str,
        agent_class: type[BaseAgent],
        prompt_path: str = "",
        description: str = "",
    ) -> None:
        """Register an agent class under *agent_name*."""
        agent_instance = agent_class()
        definition = AgentDefinition(
            name=agent_name,
            description=description or agent_instance.mission,
            prompt_path=prompt_path,
            allowed_tools=list(agent_instance.allowed_tools),
            required_inputs=list(agent_instance.required_inputs),
            output_schema=agent_instance.output_schema.__name__,
            handoff_targets=agent_instance.get_handoff_targets(),
        )
        # Compute prompt version if prompt file exists
        try:
            definition.prompt_version = agent_instance.get_prompt_version()
        except FileNotFoundError:
            definition.prompt_version = ""

        self._agents[agent_name] = (agent_class, definition)

    def get(self, agent_name: str) -> AgentDefinition:
        """Return the definition for *agent_name*.

        Raises:
            KeyError: If the agent is not registered.
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' is not registered")
        return self._agents[agent_name][1]

    def get_class(self, agent_name: str) -> type[BaseAgent]:
        """Return the agent class for *agent_name*.

        Raises:
            KeyError: If the agent is not registered.
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' is not registered")
        return self._agents[agent_name][0]

    def list_agents(self) -> list[AgentDefinition]:
        """Return definitions for all registered agents."""
        return [defn for _, defn in self._agents.values()]

    def validate_all(self) -> list[str]:
        """Check all registered agents have valid prompts and configs.

        Returns a list of error messages (empty if all valid).
        """
        errors: list[str] = []
        for agent_name, (agent_class, defn) in self._agents.items():
            # Check prompt file exists
            if defn.prompt_path:
                path = Path(defn.prompt_path)
                if not path.exists():
                    # Try relative to project root
                    root = Path(__file__).resolve().parent.parent.parent
                    if not (root / defn.prompt_path).exists():
                        errors.append(
                            f"Agent '{agent_name}': prompt file "
                            f"'{defn.prompt_path}' not found"
                        )
            # Check agent has a name
            instance = agent_class()
            if not instance.name:
                errors.append(f"Agent '{agent_name}': missing 'name' attribute")
        return errors

    def load_from_config(self) -> list[str]:
        """Load agent manifest from config/prompts.yaml.

        Returns the list of agent names found in config (does not
        register them — that requires the actual agent classes).
        """
        config = load_prompts_config()
        return [entry.agent_name for entry in config.prompts]
