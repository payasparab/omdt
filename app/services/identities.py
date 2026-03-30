"""Identity resolution service.

Loads people from config/people.yaml and provides cross-reference
lookups across email, GitHub username, and Linear user ID.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pydantic import BaseModel


class Person(BaseModel):
    """Resolved identity for a person in the system."""

    person_key: str
    display_name: str
    primary_email: str
    alternate_emails: list[str] = []
    github_username: str | None = None
    github_user_id: str | None = None
    linear_user_id: str | None = None
    linear_display_name: str | None = None
    roles: list[str] = []
    preferred_notification_channel: str | None = None


# In-memory cache
_people: dict[str, Person] | None = None


def _load_people() -> dict[str, Person]:
    """Load people from config/people.yaml."""
    global _people
    if _people is not None:
        return _people

    config_path = Path(__file__).resolve().parents[2] / "config" / "people.yaml"
    if not config_path.exists():
        _people = {}
        return _people

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    people: dict[str, Person] = {}
    for entry in data.get("people", []):
        github = entry.get("github", {})
        linear = entry.get("linear", {})
        person = Person(
            person_key=entry["person_key"],
            display_name=entry.get("display_name", entry["person_key"]),
            primary_email=entry.get("primary_email", ""),
            alternate_emails=entry.get("alternate_emails", []),
            github_username=github.get("username") if github else None,
            github_user_id=github.get("user_id") if github else None,
            linear_user_id=linear.get("user_id") if linear else None,
            linear_display_name=linear.get("display_name") if linear else None,
            roles=entry.get("roles", []),
            preferred_notification_channel=entry.get("preferred_notification_channel"),
        )
        people[person.person_key] = person

    _people = people
    return _people


def reload_people() -> None:
    """Force reload of people config (for testing)."""
    global _people
    _people = None


async def get_person(person_key: str) -> Person | None:
    """Retrieve a person by their person_key."""
    people = _load_people()
    return people.get(person_key)


async def list_people() -> list[Person]:
    """List all people."""
    people = _load_people()
    return list(people.values())


async def resolve_identity(identifier: str) -> Person | None:
    """Resolve a person by email, GitHub username, or Linear user ID.

    Tries matching against primary_email, alternate_emails,
    github_username, and linear_user_id.
    """
    people = _load_people()

    for person in people.values():
        if person.primary_email == identifier:
            return person
        if identifier in person.alternate_emails:
            return person
        if person.github_username == identifier:
            return person
        if person.linear_user_id == identifier:
            return person
        if person.person_key == identifier:
            return person

    return None


async def get_person_roles(person_key: str) -> list[str]:
    """Get the roles assigned to a person."""
    person = await get_person(person_key)
    if person is None:
        return []
    return list(person.roles)
