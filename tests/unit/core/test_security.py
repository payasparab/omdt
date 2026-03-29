"""Tests for app.core.security — hashing, redaction, approval validation."""

from __future__ import annotations

from app.core.security import (
    SensitiveActionClass,
    hash_value,
    redact_secret,
    validate_approval_required,
)


class TestHashValue:
    def test_returns_hex_sha256(self) -> None:
        h = hash_value("hello")
        assert len(h) == 64

    def test_deterministic(self) -> None:
        assert hash_value("abc") == hash_value("abc")

    def test_different_inputs_differ(self) -> None:
        assert hash_value("a") != hash_value("b")


class TestRedactSecret:
    def test_long_value_shows_last_four(self) -> None:
        result = redact_secret("sk-proj-abcdefghij1234")
        assert result == "****1234"

    def test_short_value_fully_masked(self) -> None:
        assert redact_secret("abc") == "****"
        assert redact_secret("abcd") == "****"

    def test_exactly_five_chars(self) -> None:
        assert redact_secret("12345") == "****2345"


class TestValidateApprovalRequired:
    def test_present_in_policy_true(self) -> None:
        policy = {"production_deploy": True}
        assert validate_approval_required("production_deploy", policy) is True

    def test_present_in_policy_false(self) -> None:
        policy = {"production_deploy": False}
        assert validate_approval_required("production_deploy", policy) is False

    def test_missing_from_policy_defaults_true(self) -> None:
        assert validate_approval_required("unknown_action", {}) is True


class TestSensitiveActionClass:
    def test_all_values_are_strings(self) -> None:
        for member in SensitiveActionClass:
            assert isinstance(member.value, str)

    def test_expected_members_exist(self) -> None:
        names = {m.value for m in SensitiveActionClass}
        assert "production_deploy" in names
        assert "production_access_grant" in names
        assert "secrets_backend_change" in names
        assert "destructive_data_operation" in names
        assert "prompt_policy_change" in names
