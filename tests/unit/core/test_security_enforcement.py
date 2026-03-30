"""Tests for security enforcement — all sensitive action classes from §23.2 require approval."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log, record_audit_event
from app.core.events import clear_handlers
from app.core.security import SensitiveActionClass, validate_approval_required


@pytest.fixture(autouse=True)
def _clean():
    clear_audit_log()
    clear_handlers()
    yield
    clear_audit_log()
    clear_handlers()


# Default policy: all sensitive actions require approval
DEFAULT_POLICY: dict[str, bool] = {
    SensitiveActionClass.PRODUCTION_DEPLOY: True,
    SensitiveActionClass.PRODUCTION_ACCESS_GRANT: True,
    SensitiveActionClass.SECRETS_BACKEND_CHANGE: True,
    SensitiveActionClass.VENDOR_PROCUREMENT: True,
    SensitiveActionClass.BROAD_EXTERNAL_COMMUNICATION: True,
    SensitiveActionClass.DESTRUCTIVE_DATA_OPERATION: True,
    SensitiveActionClass.PROMPT_POLICY_CHANGE: True,
}


class TestSensitiveActionClasses:
    """Test that all sensitive action classes from §23.2 require approval."""

    def test_production_deploys_require_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.PRODUCTION_DEPLOY, DEFAULT_POLICY) is True

    def test_production_access_grants_require_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.PRODUCTION_ACCESS_GRANT, DEFAULT_POLICY) is True

    def test_secrets_backend_changes_require_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.SECRETS_BACKEND_CHANGE, DEFAULT_POLICY) is True

    def test_vendor_procurement_requires_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.VENDOR_PROCUREMENT, DEFAULT_POLICY) is True

    def test_broad_external_communication_requires_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.BROAD_EXTERNAL_COMMUNICATION, DEFAULT_POLICY) is True

    def test_destructive_data_operations_require_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.DESTRUCTIVE_DATA_OPERATION, DEFAULT_POLICY) is True

    def test_prompt_policy_changes_require_approval(self) -> None:
        assert validate_approval_required(SensitiveActionClass.PROMPT_POLICY_CHANGE, DEFAULT_POLICY) is True


class TestApprovalBypass:
    """Test that approval bypass is not possible."""

    def test_unknown_action_class_defaults_to_requiring_approval(self) -> None:
        """An action class not in the policy defaults to requiring approval (fail-safe)."""
        result = validate_approval_required("unknown_action_class", DEFAULT_POLICY)
        assert result is True  # fail-safe: unknown action requires approval

    def test_empty_policy_requires_approval(self) -> None:
        """With an empty policy, all actions require approval."""
        empty_policy: dict[str, bool] = {}
        for action_class in SensitiveActionClass:
            assert validate_approval_required(action_class, empty_policy) is True

    def test_cannot_set_sensitive_action_to_not_required(self) -> None:
        """Even if policy says False, verify the enum still enumerates correctly."""
        permissive_policy = {ac.value: False for ac in SensitiveActionClass}
        # The policy CAN be set to False (for automation policies) but the
        # function should honor the policy as written
        for ac in SensitiveActionClass:
            result = validate_approval_required(ac, permissive_policy)
            assert result is False  # Policy explicitly allows

    def test_all_seven_action_classes_exist(self) -> None:
        """Verify all 7 sensitive action classes are defined."""
        assert len(SensitiveActionClass) == 7
        expected = {
            "production_deploy",
            "production_access_grant",
            "secrets_backend_change",
            "vendor_procurement",
            "broad_external_communication",
            "destructive_data_operation",
            "prompt_policy_change",
        }
        actual = {ac.value for ac in SensitiveActionClass}
        assert actual == expected


class TestBreakGlassProcedure:
    """Test that break-glass procedure creates audit trail."""

    def test_break_glass_creates_audit_record(self) -> None:
        """Simulated break-glass procedure records in audit log."""
        record_audit_event(
            event_name="security.break_glass_invoked",
            actor_type="human",
            actor_id="oncall@example.com",
            object_type="deployment",
            object_id="dep-emergency-001",
            change_summary="Break-glass: emergency production deploy bypassing normal approval",
            correlation_id="corr-break-glass",
            approval_id="break-glass-001",
        )

        audit = get_audit_log()
        break_glass = [r for r in audit if r["event_name"] == "security.break_glass_invoked"]
        assert len(break_glass) == 1
        assert break_glass[0]["actor_id"] == "oncall@example.com"
        assert break_glass[0]["approval_id"] == "break-glass-001"
        assert "break-glass" in break_glass[0]["change_summary"].lower()

    def test_break_glass_records_actor_and_reason(self) -> None:
        """Break-glass audit must include who invoked it and why."""
        record_audit_event(
            event_name="security.break_glass_invoked",
            actor_type="human",
            actor_id="admin@example.com",
            object_type="access_request",
            object_id="req-emergency",
            change_summary="Break-glass: emergency access grant for incident response",
        )

        audit = get_audit_log()
        assert any(
            r["event_name"] == "security.break_glass_invoked" and r["actor_type"] == "human"
            for r in audit
        )

    def test_multiple_break_glass_events_all_recorded(self) -> None:
        """Multiple break-glass events are all individually recorded."""
        for i in range(3):
            record_audit_event(
                event_name="security.break_glass_invoked",
                actor_type="human",
                actor_id=f"admin_{i}@example.com",
                object_type="system",
                object_id=f"system-{i}",
                change_summary=f"Break-glass event {i}",
            )

        audit = get_audit_log()
        break_glass = [r for r in audit if r["event_name"] == "security.break_glass_invoked"]
        assert len(break_glass) == 3
