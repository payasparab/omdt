"""Tests for app.core.logging — structured logging, redaction, context."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import structlog

from app.core.logging import (
    RedactionProcessor,
    ContextInjector,
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)


class TestRedactionProcessor:
    def setup_method(self) -> None:
        self.processor = RedactionProcessor()

    def test_redacts_secret_field(self) -> None:
        event = {"event": "test", "api_secret": "super-secret-value"}
        result = self.processor(None, "info", event)
        assert result["api_secret"] == "**REDACTED**"

    def test_redacts_token_field(self) -> None:
        event = {"event": "test", "oauth_token": "tok_abc123"}
        result = self.processor(None, "info", event)
        assert result["oauth_token"] == "**REDACTED**"

    def test_redacts_password_field(self) -> None:
        event = {"event": "test", "password": "hunter2"}
        result = self.processor(None, "info", event)
        assert result["password"] == "**REDACTED**"

    def test_redacts_private_key(self) -> None:
        event = {"event": "test", "private_key": "-----BEGIN RSA-----"}
        result = self.processor(None, "info", event)
        assert result["private_key"] == "**REDACTED**"

    def test_redacts_credential_field(self) -> None:
        event = {"event": "test", "db_credential": "pass123"}
        result = self.processor(None, "info", event)
        assert result["db_credential"] == "**REDACTED**"

    def test_redacts_apikey_field(self) -> None:
        event = {"event": "test", "apikey": "key123"}
        result = self.processor(None, "info", event)
        assert result["apikey"] == "**REDACTED**"

    def test_does_not_redact_safe_fields(self) -> None:
        event = {"event": "test", "user_id": "u-42", "action": "login"}
        result = self.processor(None, "info", event)
        assert result["user_id"] == "u-42"
        assert result["action"] == "login"

    def test_case_insensitive(self) -> None:
        event = {"event": "test", "API_KEY": "xyz"}
        result = self.processor(None, "info", event)
        assert result["API_KEY"] == "**REDACTED**"


class TestContextInjector:
    def test_injects_service_and_environment(self) -> None:
        injector = ContextInjector(service="omdt", environment="test")
        event: dict = {"event": "hello"}
        result = injector(None, "info", event)
        assert result["service"] == "omdt"
        assert result["environment"] == "test"

    def test_does_not_overwrite_existing(self) -> None:
        injector = ContextInjector(service="omdt", environment="test")
        event: dict = {"event": "hello", "service": "custom"}
        result = injector(None, "info", event)
        assert result["service"] == "custom"


class TestConfigureLogging:
    def test_configure_does_not_raise(self) -> None:
        configure_logging(service="omdt-test", environment="test")
        # Verify we can get a logger afterwards
        log = get_logger()
        assert log is not None

    def test_json_output(self) -> None:
        configure_logging(service="omdt-test", environment="test")
        buf = StringIO()
        with patch("structlog._config._Configuration.default_wrapper_class") as _:
            # Just verify the renderer is JSON by checking config
            cfg = structlog.get_config()
            processor_types = [type(p).__name__ for p in cfg["processors"]]
            assert "JSONRenderer" in processor_types


class TestBindContext:
    def setup_method(self) -> None:
        clear_context()

    def teardown_method(self) -> None:
        clear_context()

    def test_bind_and_clear(self) -> None:
        bind_context(correlation_id="corr-1", actor_type="human")
        ctx = structlog.contextvars.get_contextvars()
        assert ctx["correlation_id"] == "corr-1"
        assert ctx["actor_type"] == "human"

        clear_context()
        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx
