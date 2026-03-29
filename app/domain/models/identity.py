"""Identity domain models (§14.4)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Person(BaseModel):
    """A person known to the OMDT system."""

    person_key: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    primary_email: EmailStr
    alternate_emails: list[str] = []
    outlook_upn: str | None = None
    roles: list[str] = []
    preferred_notification_channel: str = "email"
    created_at: datetime
    updated_at: datetime


class ExternalAccount(BaseModel):
    """Links a person to an external system account."""

    person_key: str
    external_system: str
    external_id: str
    external_username: str | None = None
    team_keys: list[str] = []
    created_at: datetime


class DistributionList(BaseModel):
    """A named group of people for notifications."""

    id: str
    name: str = Field(min_length=1)
    member_person_keys: list[str] = []
    channel: str = "email"
    created_at: datetime
    updated_at: datetime
