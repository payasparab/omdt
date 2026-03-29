"""Base adapter framework for external tool integrations.

Implements the adapter design standard from PRD section 13.1:
- BaseAdapter ABC with healthcheck, validate_config, execute
- Structured error hierarchy
- Configurable retry policy with exponential backoff
- Audit context injection for every execute() call
- Redaction mixin to prevent secrets in logs
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.audit import AuditEvent, AuditWriter
from app.core.events import DomainEvent, EventBus
from app.core.ids import generate_correlation_id, get_current_correlation_id
from app.core.logging import get_logger


# ---------------------------------------------------------------------------
# Adapter exceptions
# ---------------------------------------------------------------------------

class AdapterError(Exception):
    """Base exception for all adapter errors."""

    def __init__(self, message: str, adapter_name: str = "", action: str = "") -> None:
        self.adapter_name = adapter_name
        self.action = action
        super().__init__(message)


class AdapterAuthError(AdapterError):
    """Raised when authentication or authorization fails."""


class AdapterRateLimitError(AdapterError):
    """Raised when the external service returns a rate-limit response."""

    def __init__(
        self,
        message: str,
        adapter_name: str = "",
        action: str = "",
        retry_after: float | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, adapter_name=adapter_name, action=action)


class AdapterTimeoutError(AdapterError):
    """Raised when the external call exceeds the allowed timeout."""


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

@dataclass
class RetryPolicy:
    """Configurable retry parameters for adapter calls."""

    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    retryable_status_codes: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def with_retry(policy: RetryPolicy | None = None):
    """Decorator that applies exponential backoff retry to an async function.

    Retries on ``AdapterRateLimitError`` and ``AdapterTimeoutError``.
    Other ``AdapterError`` subclasses are raised immediately.
    """
    _policy = policy or RetryPolicy()

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(_policy.max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except AdapterRateLimitError as exc:
                    last_exc = exc
                    if attempt == _policy.max_retries:
                        raise
                    wait = exc.retry_after or min(
                        _policy.backoff_base * (2 ** attempt) + random.uniform(0, 1),
                        _policy.backoff_max,
                    )
                    await asyncio.sleep(wait)
                except AdapterTimeoutError as exc:
                    last_exc = exc
                    if attempt == _policy.max_retries:
                        raise
                    wait = min(
                        _policy.backoff_base * (2 ** attempt) + random.uniform(0, 1),
                        _policy.backoff_max,
                    )
                    await asyncio.sleep(wait)
                except AdapterError:
                    raise
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------

import re

_SENSITIVE_PATTERNS = re.compile(
    r"(secret|token|password|passwd|api_key|apikey|private_key|"
    r"authorization|credential|access_key|refresh_token|client_secret)",
    re.IGNORECASE,
)


def redact_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *data* with sensitive values replaced."""
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_PATTERNS.search(key):
            redacted[key] = "**REDACTED**"
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        else:
            redacted[key] = value
    return redacted


# ---------------------------------------------------------------------------
# BaseAdapter ABC
# ---------------------------------------------------------------------------

class BaseAdapter(ABC):
    """Abstract base class for all external tool adapters.

    Provides:
    - Audit context injection on every ``execute()`` call
    - Automatic log redaction of sensitive fields
    - Configurable retry policy
    """

    name: str = "base"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        audit_writer: AuditWriter | None = None,
        event_bus: EventBus | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.config = config or {}
        self._audit_writer = audit_writer
        self._event_bus = event_bus
        self.retry_policy = retry_policy or RetryPolicy()
        self._logger = get_logger(adapter_name=self.name)

    # -- abstract interface ---------------------------------------------------

    @abstractmethod
    async def healthcheck(self) -> dict[str, Any]:
        """Check connectivity to the external service."""
        ...

    @abstractmethod
    async def validate_config(self) -> None:
        """Validate that the adapter's configuration is complete and correct.

        Raises ``AdapterError`` on invalid config.
        """
        ...

    @abstractmethod
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Internal implementation of a named action.

        Subclasses implement this; the public ``execute()`` wraps it with
        audit context injection, logging, and redaction.
        """
        ...

    # -- public entry point ---------------------------------------------------

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a named *action* with audit context, logging, and redaction.

        Every call emits an audit event recording the adapter name, action,
        and correlation ID. Sensitive payload fields are never logged.
        """
        correlation_id = get_current_correlation_id() or generate_correlation_id()
        safe_payload = redact_payload(payload)

        self._logger.info(
            "adapter.execute.start",
            adapter=self.name,
            action=action,
            correlation_id=correlation_id,
            payload_keys=list(safe_payload.keys()),
        )

        start = time.monotonic()
        try:
            result = await self._execute(action, payload)
            elapsed = time.monotonic() - start

            self._logger.info(
                "adapter.execute.success",
                adapter=self.name,
                action=action,
                correlation_id=correlation_id,
                duration_ms=round(elapsed * 1000, 2),
            )

            self._emit_audit_event(
                action=action,
                correlation_id=correlation_id,
                change_summary=f"{self.name}.{action} completed",
                payload=safe_payload,
            )

            return result

        except Exception as exc:
            elapsed = time.monotonic() - start
            self._logger.error(
                "adapter.execute.error",
                adapter=self.name,
                action=action,
                correlation_id=correlation_id,
                duration_ms=round(elapsed * 1000, 2),
                error=str(exc),
                error_type=type(exc).__name__,
            )

            self._emit_audit_event(
                action=action,
                correlation_id=correlation_id,
                change_summary=f"{self.name}.{action} failed: {type(exc).__name__}",
                payload=safe_payload,
            )

            raise

    # -- audit helpers --------------------------------------------------------

    def _emit_audit_event(
        self,
        *,
        action: str,
        correlation_id: str,
        change_summary: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Write an audit record and optionally emit a domain event."""
        if self._audit_writer is not None:
            event = AuditEvent(
                sequence_number=0,  # assigned by writer
                event_name=f"adapter.{self.name}.{action}",
                actor_type="system",
                actor_id=f"adapter:{self.name}",
                object_type="adapter_call",
                object_id=f"{self.name}.{action}",
                correlation_id=correlation_id,
                change_summary=change_summary,
                tool_name=self.name,
            )
            self._audit_writer.append(event)

        if self._event_bus is not None:
            domain_event = DomainEvent(
                event_name=f"adapter.{self.name}.{action}",
                actor_type="system",
                actor_id=f"adapter:{self.name}",
                object_type="adapter_call",
                object_id=f"{self.name}.{action}",
                correlation_id=correlation_id,
                payload=payload or {},
            )
            self._event_bus.emit_sync(domain_event)
