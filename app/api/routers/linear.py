"""Linear sync API router."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api.linear import (
    LinearSyncResponse,
    LinearSyncStatusResponse,
    LinearWebhookPayload,
    LinearWebhookResponse,
)

router = APIRouter(prefix="/api/v1/linear", tags=["linear"])

# The LinearSyncService is lazy-initialized. In production it would be
# injected via FastAPI dependency injection.  For now we provide a factory.
_sync_service = None


def _get_sync_service():
    """Get or create the LinearSyncService singleton."""
    global _sync_service
    if _sync_service is not None:
        return _sync_service
    # Attempt to construct with a real adapter; fall back to None
    try:
        from app.adapters.linear import LinearAdapter
        from app.jobs.linear_sync import LinearSyncService

        adapter = LinearAdapter()
        _sync_service = LinearSyncService(adapter)
        return _sync_service
    except Exception:
        return None


def set_sync_service(service) -> None:  # noqa: ANN001
    """Override the sync service (for testing)."""
    global _sync_service
    _sync_service = service


@router.post("/sync/{work_item_id}", response_model=LinearSyncResponse)
async def trigger_sync(work_item_id: str) -> LinearSyncResponse:
    """Trigger a Linear sync for a specific work item."""
    svc = _get_sync_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="Linear sync service not available")

    result = await svc.sync_work_item(work_item_id)
    return LinearSyncResponse(**result)


@router.post("/webhook", response_model=LinearWebhookResponse)
async def receive_webhook(payload: LinearWebhookPayload) -> LinearWebhookResponse:
    """Receive and process an inbound Linear webhook."""
    svc = _get_sync_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="Linear sync service not available")

    result = await svc.receive_webhook(payload.model_dump())
    return LinearWebhookResponse(**result)


@router.get("/status/{work_item_id}", response_model=LinearSyncStatusResponse)
async def get_sync_status(work_item_id: str) -> LinearSyncStatusResponse:
    """Get the current sync status for a work item."""
    svc = _get_sync_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="Linear sync service not available")

    status = svc.get_sync_status(work_item_id)
    return LinearSyncStatusResponse(**status)
