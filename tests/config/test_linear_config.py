"""Tests for the Linear schema config (config/linear.schema.yaml)."""

import pytest

from app.core.config import load_linear_config
from app.schemas.config.linear import CANONICAL_STATES, LinearSchemaConfig


@pytest.mark.unit
class TestLinearConfig:
    """Tests for LinearSchemaConfig loading and validation."""

    def test_linear_yaml_loads_and_validates(self) -> None:
        """config/linear.schema.yaml should load and produce a valid LinearSchemaConfig."""
        config = load_linear_config()
        assert isinstance(config, LinearSchemaConfig)

    def test_state_mapping_completeness(self) -> None:
        """All canonical states must be present in state_mappings."""
        config = load_linear_config()
        mapped_states = set(config.state_mappings.keys())
        missing = CANONICAL_STATES - mapped_states
        assert not missing, f"Missing canonical state mappings: {missing}"

    def test_at_least_one_team(self) -> None:
        """There should be at least one team configured."""
        config = load_linear_config()
        assert len(config.teams) > 0

    def test_priority_mappings_present(self) -> None:
        """Priority mappings should be non-empty."""
        config = load_linear_config()
        assert len(config.priority_mappings) > 0

    def test_sync_rules_defaults(self) -> None:
        """Sync rules should have expected defaults."""
        config = load_linear_config()
        assert config.sync_rules.direction == "bidirectional"
        assert config.sync_rules.conflict_resolution == "omdt_wins"
        assert config.sync_rules.sync_interval_seconds > 0

    def test_label_catalog_has_entries(self) -> None:
        """Label catalog should contain at least one label."""
        config = load_linear_config()
        assert len(config.label_catalog) > 0
        for label in config.label_catalog:
            assert label.name
            assert label.color.startswith("#")
