"""Health and readiness endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter

from app.schemas.api.common import HealthResponse, ReadinessCheck, ReadinessResponse

router = APIRouter(prefix="/api/v1/health", tags=["health"])

_VERSION = "0.1.0"


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic liveness probe — returns service metadata and status."""
    return HealthResponse(
        version=_VERSION,
        environment=os.getenv("OMDT_ENV", "development"),
        status="ok",
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe — verifies critical dependencies are available."""
    checks: list[ReadinessCheck] = []

    # TODO (Wave 2): real DB ping via app.db.session
    checks.append(ReadinessCheck(name="database", status="ok", message="placeholder — not yet connected"))

    # TODO (Wave 2): real Redis ping
    checks.append(ReadinessCheck(name="redis", status="ok", message="placeholder — not yet connected"))

    overall = "ok" if all(c.status == "ok" for c in checks) else "degraded"

    return ReadinessResponse(
        version=_VERSION,
        status=overall,
        checks=checks,
    )
