"""Pydantic models for the people config (config/people.yaml) per PRD §14.5."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ExternalGitHubAccount(BaseModel):
    """GitHub account link for a person."""

    model_config = ConfigDict(strict=True)

    username: str
    user_id: int | None = None
    team_slugs: list[str] = Field(default_factory=list)


class ExternalLinearAccount(BaseModel):
    """Linear account link for a person."""

    model_config = ConfigDict(strict=True)

    user_id: str
    display_name: str | None = None
    team_keys: list[str] = Field(default_factory=list)


class PersonConfig(BaseModel):
    """A single person entry in the people config."""

    model_config = ConfigDict(strict=True)

    person_key: str
    display_name: str
    primary_email: EmailStr
    alternate_emails: list[EmailStr] = Field(default_factory=list)
    github: ExternalGitHubAccount | None = None
    linear: ExternalLinearAccount | None = None
    roles: list[str] = Field(default_factory=list)
    preferred_notification_channel: Literal["email", "linear", "notion", "cli"] = "email"


class PeopleConfig(BaseModel):
    """Root config model matching config/people.yaml."""

    model_config = ConfigDict(strict=True)

    people: list[PersonConfig]
