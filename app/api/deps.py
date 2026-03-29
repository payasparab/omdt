"""Shared FastAPI dependencies for OMDT."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

from fastapi import Request


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[None, None]:
    """Yield an async DB session.

    TODO (Wave 2): replace with real AsyncSession from app.db.session once the
    database chat delivers that module.
    """
    yield None


# ---------------------------------------------------------------------------
# Correlation ID
# ---------------------------------------------------------------------------

def get_correlation_id(request: Request) -> str:
    """Extract the correlation ID set by CorrelationIDMiddleware."""
    return getattr(request.state, "correlation_id", None) or str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Actor context
# ---------------------------------------------------------------------------

async def get_current_actor(request: Request) -> str | None:
    """Extract the current actor from the request.

    TODO (Wave 2): implement real actor extraction from JWT / API-key header
    once the auth layer is available.
    """
    return request.headers.get("X-Actor")
