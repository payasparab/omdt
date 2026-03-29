"""FastAPI application entry point for OMDT."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.schemas.api.common import ErrorResponse

# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    TODO (Wave 2): initialise DB connection pool, Redis, scheduler, etc.
    """
    # --- startup ---
    print("OMDT starting up …")
    yield
    # --- shutdown ---
    print("OMDT shutting down …")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OMDT",
    description=(
        "One Man Data Team — an open-source, Python-first operating framework "
        "that behaves like an in-house data team."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

# TODO (Wave 2): load allowed origins from config/omdt.yaml
_CORS_ORIGINS: list[str] = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request-ID / Correlation-ID middleware
# ---------------------------------------------------------------------------

_CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Inject a correlation_id into every request and echo it in the response."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        correlation_id = request.headers.get(_CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[_CORRELATION_HEADER] = correlation_id
        return response


app.add_middleware(CorrelationIDMiddleware)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    errors = [
        {"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    body = ErrorResponse(
        error="validation_error",
        detail="Request validation failed",
        errors=errors,  # type: ignore[arg-type]
        correlation_id=correlation_id,
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    body = ErrorResponse(
        error="not_found",
        detail="The requested resource was not found",
        correlation_id=correlation_id,
    )
    return JSONResponse(status_code=404, content=body.model_dump(mode="json"))


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    body = ErrorResponse(
        error="unauthorized",
        detail="Authentication required",
        correlation_id=correlation_id,
    )
    return JSONResponse(status_code=401, content=body.model_dump(mode="json"))


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    body = ErrorResponse(
        error="internal_server_error",
        detail="An unexpected error occurred",
        correlation_id=correlation_id,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Router registry
# ---------------------------------------------------------------------------

from app.api.routers.health import router as health_router  # noqa: E402

app.include_router(health_router)

# Routers created by other parallel chats — guarded so the app boots even if
# those modules aren't available yet.
try:
    from app.api.routers.intake import router as intake_router

    app.include_router(intake_router)
except (ImportError, ModuleNotFoundError):
    pass

try:
    from app.api.routers.work_items import router as work_items_router

    app.include_router(work_items_router)
except (ImportError, ModuleNotFoundError):
    pass

try:
    from app.api.routers.prds import router as prds_router

    app.include_router(prds_router)
except (ImportError, ModuleNotFoundError):
    pass

try:
    from app.api.routers.approvals import router as approvals_router

    app.include_router(approvals_router)
except (ImportError, ModuleNotFoundError):
    pass
