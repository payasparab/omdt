"""Tests for Project domain model."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import CanonicalState
from app.domain.models.project import Project


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestProjectCreation:
    def test_minimal_valid(self) -> None:
        p = Project(
            id=uuid4(),
            key="proj-alpha",
            name="Alpha Project",
            created_at=_now(),
            updated_at=_now(),
        )
        assert p.state == CanonicalState.NEW
        assert p.owner_person_key is None

    def test_key_required(self) -> None:
        with pytest.raises(ValidationError):
            Project(
                id=uuid4(),
                key="",
                name="Bad",
                created_at=_now(),
                updated_at=_now(),
            )

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Project(
                id=uuid4(),
                key="ok-key",
                name="",
                created_at=_now(),
                updated_at=_now(),
            )

    def test_custom_state(self) -> None:
        p = Project(
            id=uuid4(),
            key="proj-beta",
            name="Beta",
            state=CanonicalState.IN_PROGRESS,
            created_at=_now(),
            updated_at=_now(),
        )
        assert p.state == CanonicalState.IN_PROGRESS
