"""Tests for the people config (config/people.yaml)."""

import pytest
from pydantic import ValidationError

from app.core.config import load_people_config
from app.schemas.config.people import PeopleConfig, PersonConfig


@pytest.mark.unit
class TestPeopleConfig:
    """Tests for PeopleConfig loading and validation."""

    def test_people_yaml_loads_and_validates(self) -> None:
        """config/people.yaml should load and produce a valid PeopleConfig."""
        config = load_people_config()
        assert isinstance(config, PeopleConfig)
        assert len(config.people) > 0

    def test_person_has_required_fields(self) -> None:
        """Each person entry should have person_key, display_name, primary_email."""
        config = load_people_config()
        for person in config.people:
            assert person.person_key
            assert person.display_name
            assert person.primary_email

    def test_invalid_email_rejected(self) -> None:
        """An invalid email format should fail validation."""
        with pytest.raises(ValidationError):
            PersonConfig.model_validate(
                {
                    "person_key": "test.user",
                    "display_name": "Test User",
                    "primary_email": "not-an-email",
                }
            )

    def test_valid_notification_channels(self) -> None:
        """preferred_notification_channel must be a valid choice."""
        with pytest.raises(ValidationError):
            PersonConfig.model_validate(
                {
                    "person_key": "test.user",
                    "display_name": "Test User",
                    "primary_email": "test@example.com",
                    "preferred_notification_channel": "carrier_pigeon",
                }
            )

    def test_defaults_work(self) -> None:
        """Optional fields should have sensible defaults."""
        person = PersonConfig.model_validate(
            {
                "person_key": "minimal.user",
                "display_name": "Minimal User",
                "primary_email": "minimal@example.com",
            }
        )
        assert person.alternate_emails == []
        assert person.github is None
        assert person.linear is None
        assert person.roles == []
        assert person.preferred_notification_channel == "email"
