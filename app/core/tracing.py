"""OpenTelemetry tracing skeleton.

Provides a thin wrapper around the OTLP tracer that works even when no
collector is configured (graceful no-op).
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Lazy imports — OpenTelemetry may not be installed
# ---------------------------------------------------------------------------

_tracer_provider: Any = None
_OTEL_AVAILABLE: bool = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_tracing(
    service_name: str = "omdt",
    environment: str = "development",
) -> None:
    """Set up the OTLP tracer provider.

    If OpenTelemetry is not installed, this is a safe no-op.
    """
    global _tracer_provider

    if not _OTEL_AVAILABLE:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
        }
    )
    _tracer_provider = TracerProvider(resource=resource)

    # Default to console exporter; swap to OTLPSpanExporter when a
    # collector endpoint is configured.
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )
    trace.set_tracer_provider(_tracer_provider)


# ---------------------------------------------------------------------------
# Tracer access
# ---------------------------------------------------------------------------

def get_tracer(name: str = "omdt") -> Any:
    """Return a tracer instance.  Falls back to a no-op tracer if
    OpenTelemetry is unavailable.
    """
    if _OTEL_AVAILABLE:
        return trace.get_tracer(name)
    return _NoOpTracer()


# ---------------------------------------------------------------------------
# @traced decorator
# ---------------------------------------------------------------------------

def traced(operation_name: str | None = None) -> Callable[[F], F]:
    """Decorator that wraps a function in a trace span.

    Works as a no-op when OpenTelemetry is not installed.
    """

    def decorator(fn: F) -> F:
        span_name = operation_name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            if _OTEL_AVAILABLE:
                with tracer.start_as_current_span(span_name):
                    return fn(*args, **kwargs)
            return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            if _OTEL_AVAILABLE:
                with tracer.start_as_current_span(span_name):
                    return await fn(*args, **kwargs)
            return await fn(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# No-op fallback
# ---------------------------------------------------------------------------

class _NoOpSpan:
    """Minimal span stand-in when OTel is missing."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        pass


class _NoOpTracer:
    """Minimal tracer stand-in when OTel is missing."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoOpSpan:  # noqa: ARG002
        return _NoOpSpan()
