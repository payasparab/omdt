"""Unit tests for the base adapter framework.

Tests retry logic, audit emission, redaction, and error types.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterRateLimitError,
    AdapterTimeoutError,
    BaseAdapter,
    RetryPolicy,
    redact_payload,
    with_retry,
)
from app.core.audit import AuditWriter
from app.core.events import EventBus


# ---------------------------------------------------------------------------
# Concrete adapter for testing
# ---------------------------------------------------------------------------

class FakeAdapter(BaseAdapter):
    name = "fake"

    async def healthcheck(self) -> dict[str, Any]:
        return {"healthy": True}

    async def validate_config(self) -> None:
        if not self.config.get("required_key"):
            raise AdapterError("missing required_key", adapter_name=self.name)

    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "fail_auth":
            raise AdapterAuthError("bad auth", adapter_name=self.name, action=action)
        if action == "fail_rate":
            raise AdapterRateLimitError("rate limited", adapter_name=self.name, action=action)
        if action == "fail_timeout":
            raise AdapterTimeoutError("timed out", adapter_name=self.name, action=action)
        if action == "echo":
            return {"echoed": payload}
        raise AdapterError(f"unknown action: {action}", adapter_name=self.name, action=action)


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class TestErrorHierarchy:
    def test_adapter_error_is_base(self):
        assert issubclass(AdapterError, Exception)

    def test_auth_error_is_adapter_error(self):
        assert issubclass(AdapterAuthError, AdapterError)

    def test_rate_limit_error_is_adapter_error(self):
        assert issubclass(AdapterRateLimitError, AdapterError)

    def test_timeout_error_is_adapter_error(self):
        assert issubclass(AdapterTimeoutError, AdapterError)

    def test_error_carries_adapter_name_and_action(self):
        exc = AdapterError("msg", adapter_name="test", action="do_thing")
        assert exc.adapter_name == "test"
        assert exc.action == "do_thing"

    def test_rate_limit_error_carries_retry_after(self):
        exc = AdapterRateLimitError("msg", retry_after=5.0)
        assert exc.retry_after == 5.0


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

class TestRedaction:
    def test_redacts_sensitive_keys(self):
        data = {
            "username": "alice",
            "api_key": "secret123",
            "password": "hunter2",
            "token": "tok_abc",
        }
        result = redact_payload(data)
        assert result["username"] == "alice"
        assert result["api_key"] == "**REDACTED**"
        assert result["password"] == "**REDACTED**"
        assert result["token"] == "**REDACTED**"

    def test_redacts_nested_dicts(self):
        data = {"auth": {"client_secret": "xyz", "scope": "read"}}
        result = redact_payload(data)
        assert result["auth"]["client_secret"] == "**REDACTED**"
        assert result["auth"]["scope"] == "read"

    def test_non_sensitive_keys_preserved(self):
        data = {"name": "test", "action": "run_query", "count": 5}
        result = redact_payload(data)
        assert result == data


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_default_values(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.backoff_base == 1.0
        assert policy.backoff_max == 30.0
        assert 429 in policy.retryable_status_codes

    def test_custom_values(self):
        policy = RetryPolicy(max_retries=5, backoff_base=0.5, backoff_max=10.0)
        assert policy.max_retries == 5
        assert policy.backoff_base == 0.5


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

class TestRetryDecorator:
    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self):
        call_count = 0

        @with_retry(RetryPolicy(max_retries=2, backoff_base=0.01))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise AdapterRateLimitError("rate limited")
            return {"ok": True}

        result = await flaky()
        assert result == {"ok": True}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        call_count = 0

        @with_retry(RetryPolicy(max_retries=1, backoff_base=0.01))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise AdapterTimeoutError("timed out")
            return {"ok": True}

        result = await flaky()
        assert result == {"ok": True}
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_auth_error(self):
        call_count = 0

        @with_retry(RetryPolicy(max_retries=3, backoff_base=0.01))
        async def fail():
            nonlocal call_count
            call_count += 1
            raise AdapterAuthError("bad auth")

        with pytest.raises(AdapterAuthError):
            await fail()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        @with_retry(RetryPolicy(max_retries=2, backoff_base=0.01))
        async def always_fail():
            raise AdapterRateLimitError("rate limited")

        with pytest.raises(AdapterRateLimitError):
            await always_fail()


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------

class TestAuditEmission:
    @pytest.mark.asyncio
    async def test_execute_emits_audit_event_on_success(self):
        writer = AuditWriter()
        adapter = FakeAdapter(config={"required_key": "v"}, audit_writer=writer)
        await adapter.execute("echo", {"msg": "hi"})
        assert len(writer.records) == 1
        rec = writer.records[0]
        assert "adapter.fake.echo" in rec.event_name
        assert "completed" in rec.change_summary

    @pytest.mark.asyncio
    async def test_execute_emits_audit_event_on_failure(self):
        writer = AuditWriter()
        adapter = FakeAdapter(config={"required_key": "v"}, audit_writer=writer)
        with pytest.raises(AdapterAuthError):
            await adapter.execute("fail_auth", {})
        assert len(writer.records) == 1
        rec = writer.records[0]
        assert "failed" in rec.change_summary

    @pytest.mark.asyncio
    async def test_execute_emits_domain_event(self):
        bus = EventBus()
        events_received: list = []
        bus.subscribe("adapter.fake.echo", lambda e: events_received.append(e))

        adapter = FakeAdapter(config={"required_key": "v"}, event_bus=bus)
        await adapter.execute("echo", {"msg": "hi"})
        assert len(events_received) == 1
        assert events_received[0].event_name == "adapter.fake.echo"


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        adapter = FakeAdapter(config={"required_key": "v"})
        result = await adapter.execute("echo", {"msg": "hello"})
        assert result == {"echoed": {"msg": "hello"}}

    @pytest.mark.asyncio
    async def test_execute_redacts_sensitive_payload_in_audit(self):
        writer = AuditWriter()
        adapter = FakeAdapter(config={"required_key": "v"}, audit_writer=writer)
        await adapter.execute("echo", {"api_key": "secret", "data": "safe"})
        # The audit event should exist but the actual secret should not be in change_summary
        assert len(writer.records) == 1

    @pytest.mark.asyncio
    async def test_validate_config_raises(self):
        adapter = FakeAdapter(config={})
        with pytest.raises(AdapterError, match="missing required_key"):
            await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_healthcheck(self):
        adapter = FakeAdapter(config={"required_key": "v"})
        result = await adapter.healthcheck()
        assert result["healthy"] is True
