"""Pydantic models for the notification config (config/notifications.yaml)."""

from pydantic import BaseModel, ConfigDict, Field


class RoutingGroup(BaseModel):
    """A notification routing group."""

    model_config = ConfigDict(strict=True)

    members: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)


class NotificationDefaults(BaseModel):
    """Default notification settings."""

    model_config = ConfigDict(strict=True)

    channel: str = "email"
    urgent_channel: str = "email"
    batch_interval_minutes: int = 15


class EscalationRule(BaseModel):
    """A single escalation rule."""

    model_config = ConfigDict(strict=True)

    trigger: str
    timeout_minutes: int | None = None
    escalate_to: str
    channel: str


class NotificationConfig(BaseModel):
    """Root config model matching config/notifications.yaml."""

    model_config = ConfigDict(strict=True)

    routing_groups: dict[str, RoutingGroup]
    defaults: NotificationDefaults
    escalation_rules: list[EscalationRule]
