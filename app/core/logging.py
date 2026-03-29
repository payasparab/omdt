"""Structured logging setup using *structlog*.

Provides JSON-formatted logs with mandatory context fields per §15.3,
a redaction processor that scrubs secrets per §15.7, and helpers for
binding correlation / request context to the logger.
"""

from __future__ import annotations

import re
import time
from typing import Any

import structlog

from app.core.ids import get_current_correlation_id

# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Patterns that indicate a field value should be scrubbed.
_SENSITIVE_FIELD_PATTERNS: re.Pattern[str] = re.compile(
    r"(secret|token|password|passwd|api_key|apikey|private_key|"
    r"authorization|credential|ssn|social_security)",
    re.IGNORECASE,
)

_REDACTED = "**REDACTED**"


class RedactionProcessor:
    """structlog processor that replaces sensitive field values with a
    redacted placeholder.  Never logs secret values, raw OAuth tokens,
    passwords, private keys, or sensitive PII (§15.7).
    """

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        for key in list(event_dict.keys()):
            if _SENSITIVE_FIELD_PATTERNS.search(key):
                event_dict[key] = _REDACTED
        return event_dict


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------

class ContextInjector:
    """Injects mandatory context fields into every log line."""

    def __init__(
        self,
        service: str = "omdt",
        environment: str = "development",
    ) -> None:
        self.service = service
        self.environment = environment

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict.setdefault("service", self.service)
        event_dict.setdefault("environment", self.environment)
        event_dict.setdefault("correlation_id", get_current_correlation_id())
        return event_dict


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure_logging(
    service: str = "omdt",
    environment: str = "development",
    log_level: str = "INFO",
) -> None:
    """Configure *structlog* with JSON rendering, redaction, and context
    injection.  Should be called once at application startup.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            ContextInjector(service=service, environment=environment),
            RedactionProcessor(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.stdlib.NAME_TO_LEVEL.get(log_level.lower(), 20),
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_logger(**initial_bindings: Any) -> structlog.stdlib.BoundLogger:
    """Return a *structlog* bound logger, optionally pre-bound with extra
    context fields.
    """
    return structlog.get_logger(**initial_bindings)


def bind_context(
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
    work_item_id: str | None = None,
    project_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    agent_name: str | None = None,
    prompt_version: str | None = None,
    adapter_name: str | None = None,
) -> None:
    """Bind correlation / request / actor context into structlog's
    context-vars so that every subsequent log line in the same async
    context inherits these values.
    """
    ctx: dict[str, Any] = {}
    if correlation_id is not None:
        ctx["correlation_id"] = correlation_id
    if request_id is not None:
        ctx["request_id"] = request_id
    if work_item_id is not None:
        ctx["work_item_id"] = work_item_id
    if project_id is not None:
        ctx["project_id"] = project_id
    if actor_type is not None:
        ctx["actor_type"] = actor_type
    if actor_id is not None:
        ctx["actor_id"] = actor_id
    if agent_name is not None:
        ctx["agent_name"] = agent_name
    if prompt_version is not None:
        ctx["prompt_version"] = prompt_version
    if adapter_name is not None:
        ctx["adapter_name"] = adapter_name
    if ctx:
        structlog.contextvars.bind_contextvars(**ctx)


def clear_context() -> None:
    """Remove all context-var bindings (e.g. at end of request)."""
    structlog.contextvars.clear_contextvars()
