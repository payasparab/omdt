"""Tests for identity domain models."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.models.identity import DistributionList, ExternalAccount, Person


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestPersonCreation:
    def test_minimal_valid(self) -> None:
        p = Person(
            person_key="alice",
            display_name="Alice Smith",
            primary_email="alice@example.com",
            created_at=_now(),
            updated_at=_now(),
        )
        assert p.preferred_notification_channel == "email"
        assert p.roles == []

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Person(
                person_key="bad",
                display_name="Bad Email",
                primary_email="not-an-email",
                created_at=_now(),
                updated_at=_now(),
            )

    def test_person_key_required(self) -> None:
        with pytest.raises(ValidationError):
            Person(
                person_key="",
                display_name="No Key",
                primary_email="ok@example.com",
                created_at=_now(),
                updated_at=_now(),
            )

    def test_display_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Person(
                person_key="bob",
                display_name="",
                primary_email="bob@example.com",
                created_at=_now(),
                updated_at=_now(),
            )


class TestExternalAccount:
    def test_valid(self) -> None:
        ea = ExternalAccount(
            person_key="alice",
            external_system="github",
            external_id="12345",
            external_username="alice-gh",
            team_keys=["data-eng"],
            created_at=_now(),
        )
        assert ea.external_username == "alice-gh"


class TestDistributionList:
    def test_valid(self) -> None:
        dl = DistributionList(
            id="dl-data-team",
            name="Data Team",
            member_person_keys=["alice", "bob"],
            created_at=_now(),
            updated_at=_now(),
        )
        assert dl.channel == "email"
        assert len(dl.member_person_keys) == 2
