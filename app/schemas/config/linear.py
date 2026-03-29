"""Pydantic models for the Linear schema config (config/linear.schema.yaml) per PRD §12.5."""

from pydantic import BaseModel, ConfigDict, Field


class LinearTeam(BaseModel):
    """A Linear team definition."""

    model_config = ConfigDict(strict=True)

    key: str
    name: str
    default_assignee: str | None = None


class LinearLabel(BaseModel):
    """A label in the Linear label catalog."""

    model_config = ConfigDict(strict=True)

    name: str
    color: str


class LinearSyncRules(BaseModel):
    """Sync rules between OMDT and Linear."""

    model_config = ConfigDict(strict=True)

    direction: str = "bidirectional"
    sync_interval_seconds: int = 60
    conflict_resolution: str = "omdt_wins"
    allowed_bidirectional_fields: list[str] = Field(default_factory=list)


# All canonical states that must be present in state_mappings.
CANONICAL_STATES: frozenset[str] = frozenset(
    {
        "NEW",
        "TRIAGE",
        "NEEDS_CLARIFICATION",
        "PRD_DRAFTING",
        "PRD_REVIEW",
        "APPROVAL_PENDING",
        "APPROVED",
        "READY_FOR_BUILD",
        "IN_PROGRESS",
        "BLOCKED",
        "VALIDATION",
        "DEPLOYMENT_PENDING",
        "DEPLOYED",
        "DONE",
        "ARCHIVED",
    }
)


class LinearSchemaConfig(BaseModel):
    """Root config model matching config/linear.schema.yaml."""

    model_config = ConfigDict(strict=True)

    teams: list[LinearTeam]
    state_mappings: dict[str, str]
    priority_mappings: dict[str, int]
    label_catalog: list[LinearLabel]
    sync_rules: LinearSyncRules
