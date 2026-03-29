"""Tests that every YAML config file in config/ validates against its schema."""

import pytest

from app.core.config import (
    get_config_path,
    get_settings,
    load_approvals_config,
    load_config,
    load_linear_config,
    load_notifications_config,
    load_people_config,
    load_prompts_config,
    load_role_bundles_config,
)
from app.schemas.config.app import OmdtAppConfig
from app.schemas.config.approvals import ApprovalPolicyConfig
from app.schemas.config.linear import LinearSchemaConfig
from app.schemas.config.notifications import NotificationConfig
from app.schemas.config.people import PeopleConfig
from app.schemas.config.prompts import PromptRegistryConfig
from app.schemas.config.role_bundles import RoleBundlesConfig


@pytest.mark.unit
class TestAllConfigs:
    """Validate every config file against its Pydantic schema."""

    def test_omdt_yaml(self) -> None:
        """config/omdt.yaml validates against OmdtAppConfig."""
        config = get_settings()
        assert isinstance(config, OmdtAppConfig)

    def test_people_yaml(self) -> None:
        """config/people.yaml validates against PeopleConfig."""
        config = load_people_config()
        assert isinstance(config, PeopleConfig)

    def test_linear_schema_yaml(self) -> None:
        """config/linear.schema.yaml validates against LinearSchemaConfig."""
        config = load_linear_config()
        assert isinstance(config, LinearSchemaConfig)

    def test_notifications_yaml(self) -> None:
        """config/notifications.yaml validates against NotificationConfig."""
        config = load_notifications_config()
        assert isinstance(config, NotificationConfig)

    def test_approvals_yaml(self) -> None:
        """config/approvals.yaml validates against ApprovalPolicyConfig."""
        config = load_approvals_config()
        assert isinstance(config, ApprovalPolicyConfig)

    def test_role_bundles_yaml(self) -> None:
        """config/role_bundles.yaml validates against RoleBundlesConfig."""
        config = load_role_bundles_config()
        assert isinstance(config, RoleBundlesConfig)

    def test_prompts_yaml(self) -> None:
        """config/prompts.yaml validates against PromptRegistryConfig."""
        config = load_prompts_config()
        assert isinstance(config, PromptRegistryConfig)

    def test_prompts_yaml_has_20_entries(self) -> None:
        """config/prompts.yaml should list all 20 prompt files from Appendix E."""
        config = load_prompts_config()
        assert len(config.prompts) == 20

    def test_approvals_yaml_has_all_action_classes(self) -> None:
        """config/approvals.yaml should cover all 7 sensitive action classes."""
        config = load_approvals_config()
        action_classes = {rule.action_class for rule in config.approval_rules}
        expected = {
            "production_deploy",
            "access_grant",
            "secrets_change",
            "vendor_commitment",
            "external_send",
            "destructive_operation",
            "prompt_change",
        }
        assert action_classes == expected

    def test_role_bundles_yaml_has_all_bundles(self) -> None:
        """config/role_bundles.yaml should define all 6 role bundles."""
        config = load_role_bundles_config()
        expected = {
            "analyst_readonly",
            "engineer_transform",
            "architect_metadata_admin",
            "scientist_sandbox",
            "pipeline_operator",
            "admin_breakglass",
        }
        assert set(config.role_bundles.keys()) == expected

    def test_each_config_round_trips(self) -> None:
        """Each config should survive a load -> dump -> load round-trip."""
        configs: list[tuple[str, type]] = [
            ("omdt.yaml", OmdtAppConfig),
            ("people.yaml", PeopleConfig),
            ("linear.schema.yaml", LinearSchemaConfig),
            ("notifications.yaml", NotificationConfig),
            ("approvals.yaml", ApprovalPolicyConfig),
            ("role_bundles.yaml", RoleBundlesConfig),
            ("prompts.yaml", PromptRegistryConfig),
        ]
        for filename, model in configs:
            original = load_config(get_config_path(filename), model)
            roundtripped = model.model_validate(original.model_dump())
            assert original == roundtripped, f"Round-trip failed for {filename}"
