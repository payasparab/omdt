"""Correlation ID and identifier utilities.

Provides UUID-based ID generation and context-variable-backed
correlation tracking for request-scoped observability.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

# ---------------------------------------------------------------------------
# Context variable for the current correlation ID
# ---------------------------------------------------------------------------
_correlation_id_var: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)


# ---------------------------------------------------------------------------
# ID generators
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """Return a new UUID v4 string."""
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """Return a prefixed correlation ID, e.g. ``corr-<uuid>``."""
    return f"corr-{uuid.uuid4()}"


def generate_audit_id() -> str:
    """Return a prefixed audit ID, e.g. ``aud-<uuid>``."""
    return f"aud-{uuid.uuid4()}"


def generate_request_id() -> str:
    """Return a prefixed request ID, e.g. ``req-<uuid>``."""
    return f"req-{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# Correlation-ID context helpers
# ---------------------------------------------------------------------------

def get_current_correlation_id() -> str | None:
    """Return the correlation ID bound to the current async/thread context."""
    return _correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Bind *correlation_id* to the current async/thread context."""
    _correlation_id_var.set(correlation_id)


def reset_correlation_id() -> None:
    """Clear the correlation ID from the current context."""
    _correlation_id_var.set(None)
