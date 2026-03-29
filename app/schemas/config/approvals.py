"""Pydantic models for the approval policy config (config/approvals.yaml) per PRD §23.2."""

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRule(BaseModel):
    """A single approval rule for a sensitive action class."""

    model_config = ConfigDict(strict=True)

    action_class: str
    require_approval: bool = True
    min_approvers: int = 1
    allowed_approvers: list[str] = Field(default_factory=list)
    auto_approve_if: str | None = None


class ApprovalPolicyConfig(BaseModel):
    """Root config model matching config/approvals.yaml."""

    model_config = ConfigDict(strict=True)

    approval_rules: list[ApprovalRule]
