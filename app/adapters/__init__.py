"""Adapter framework — external tool integrations for OMDT.

Public API:
    BaseAdapter, error types, RetryPolicy, AdapterRegistry
"""

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
from app.adapters.registry import AdapterRegistry, build_registry_from_config

__all__ = [
    "AdapterAuthError",
    "AdapterError",
    "AdapterRateLimitError",
    "AdapterTimeoutError",
    "AdapterRegistry",
    "BaseAdapter",
    "RetryPolicy",
    "build_registry_from_config",
    "redact_payload",
    "with_retry",
]
