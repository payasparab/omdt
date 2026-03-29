"""Pydantic models for the prompt registry manifest (config/prompts.yaml)."""

from pydantic import BaseModel, ConfigDict


class PromptEntry(BaseModel):
    """A single prompt file entry in the registry."""

    model_config = ConfigDict(strict=True)

    agent_name: str
    file_path: str
    version: str
    description: str


class PromptRegistryConfig(BaseModel):
    """Root config model matching config/prompts.yaml."""

    model_config = ConfigDict(strict=True)

    prompts: list[PromptEntry]
