"""Tests for the main OMDT application config (config/omdt.yaml)."""

import pytest
from pydantic import ValidationError

from app.core.config import get_settings, load_config, get_config_path
from app.schemas.config.app import OmdtAppConfig


@pytest.mark.unit
class TestAppConfig:
    """Tests for OmdtAppConfig loading and validation."""

    def test_omdt_yaml_loads_and_validates(self) -> None:
        """config/omdt.yaml should load and produce a valid OmdtAppConfig."""
        config = get_settings()
        assert isinstance(config, OmdtAppConfig)
        assert config.app.name == "omdt"
        assert config.app.version == "0.1.0"

    def test_app_environment_valid_values(self) -> None:
        """environment must be one of development/staging/production."""
        config = get_settings()
        assert config.app.environment in ("development", "staging", "production")

    def test_secret_manager_type(self) -> None:
        """secret_manager.type must be a supported backend."""
        config = get_settings()
        assert config.secret_manager.type in ("env", "vault", "aws_secrets_manager")

    def test_adapters_enabled_is_list(self) -> None:
        """adapters.enabled should be a non-empty list."""
        config = get_settings()
        assert isinstance(config.adapters.enabled, list)
        assert len(config.adapters.enabled) > 0

    def test_invalid_environment_rejected(self) -> None:
        """An invalid environment value should fail validation."""
        with pytest.raises(ValidationError):
            OmdtAppConfig.model_validate(
                {
                    "app": {
                        "name": "omdt",
                        "version": "0.1.0",
                        "environment": "invalid_env",
                        "debug": False,
                        "default_timezone": "UTC",
                    },
                    "database": {"url": "postgresql://localhost/omdt"},
                    "redis": {"url": "redis://localhost:6379/0"},
                    "secret_manager": {"type": "env"},
                    "adapters": {"enabled": ["linear"]},
                }
            )

    def test_missing_required_field_rejected(self) -> None:
        """Missing a required section should fail validation."""
        with pytest.raises(ValidationError):
            OmdtAppConfig.model_validate(
                {
                    "app": {
                        "name": "omdt",
                        "version": "0.1.0",
                        "environment": "development",
                    },
                    # missing database, redis, secret_manager, adapters
                }
            )
