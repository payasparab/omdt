"""Sync orchestrator — coordinates sync timing across Linear, Notion, and notifications.

Subscribes to domain events from the EventBus and triggers appropriate
sync actions. Supports debounce and batch coordination.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.audit import record_audit_event
from app.core.events import DomainEvent, DomainEventNames, EventBus
from app.core.ids import generate_correlation_id

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class SyncOrchestrator:
    """Coordinates sync timing between Linear, Notion, and notifications.

    Subscribes to work_item.state_changed, prd.*, and feedback.* events
    and dispatches to the appropriate sync services.
    """

    def __init__(
        self,
        event_bus: EventBus,
        *,
        linear_sync_service: Any = None,
        notion_sync_service: Any = None,
        notification_dispatch: Any = None,
        debounce_seconds: float = 0.0,
    ) -> None:
        self._bus = event_bus
        self._linear = linear_sync_service
        self._notion = notion_sync_service
        self._notifications = notification_dispatch
        self._debounce = debounce_seconds
        self._pending: dict[str, asyncio.Task[Any]] = {}
        self._sync_log: list[dict[str, Any]] = []
        # Store bound method refs so subscribe/unsubscribe use the same object
        self._wi_handler = self._on_work_item_change
        self._prd_handler = self._on_prd_change

    # -- subscription wiring --------------------------------------------------

    def subscribe_all(self) -> None:
        """Register handlers on the event bus."""
        self._bus.subscribe(DomainEventNames.WORK_ITEM_STATE_CHANGED, self._wi_handler)
        self._bus.subscribe(DomainEventNames.WORK_ITEM_CREATED, self._wi_handler)
        self._bus.subscribe(DomainEventNames.PRD_CREATED, self._prd_handler)
        self._bus.subscribe(DomainEventNames.PRD_REVISED, self._prd_handler)
        self._bus.subscribe(DomainEventNames.PRD_APPROVED, self._prd_handler)

    def unsubscribe_all(self) -> None:
        """Remove handlers from the event bus."""
        self._bus.unsubscribe(DomainEventNames.WORK_ITEM_STATE_CHANGED, self._wi_handler)
        self._bus.unsubscribe(DomainEventNames.WORK_ITEM_CREATED, self._wi_handler)
        self._bus.unsubscribe(DomainEventNames.PRD_CREATED, self._prd_handler)
        self._bus.unsubscribe(DomainEventNames.PRD_REVISED, self._prd_handler)
        self._bus.unsubscribe(DomainEventNames.PRD_APPROVED, self._prd_handler)

    # -- event handlers -------------------------------------------------------

    async def _on_work_item_change(self, event: DomainEvent) -> None:
        """Handle work item changes: trigger Linear sync + Notion if PRD exists."""
        payload = event.payload
        work_item_id = payload.get("work_item_id", "")
        if not work_item_id:
            return

        await self.on_work_item_change(work_item_id)

    async def _on_prd_change(self, event: DomainEvent) -> None:
        """Handle PRD changes: trigger Notion sync."""
        payload = event.payload
        prd_id = payload.get("prd_id", "")
        if not prd_id:
            return

        await self.on_prd_change(prd_id)

    # -- public coordination methods ------------------------------------------

    async def on_work_item_change(self, work_item_id: str) -> dict[str, Any]:
        """Trigger Linear sync for a work item. Also sync Notion if a PRD exists."""
        result: dict[str, Any] = {"work_item_id": work_item_id, "actions": []}

        if self._linear:
            try:
                linear_result = await self._linear.sync_work_item(work_item_id)
                result["actions"].append({"type": "linear_sync", **linear_result})
            except Exception as exc:
                result["actions"].append({"type": "linear_sync", "error": str(exc)})

        # Check if work item has a PRD to sync to Notion
        if self._notion:
            try:
                from app.services import work_items as wi_service
                wi = await wi_service.get_work_item(work_item_id)
                if wi and wi.latest_prd_revision_id:
                    notion_result = await self._notion.sync_prd(wi.latest_prd_revision_id)
                    result["actions"].append({"type": "notion_sync", **notion_result})
            except Exception as exc:
                result["actions"].append({"type": "notion_sync", "error": str(exc)})

        self._sync_log.append(result)
        return result

    async def on_prd_change(self, prd_id: str) -> dict[str, Any]:
        """Trigger Notion sync for a PRD."""
        result: dict[str, Any] = {"prd_id": prd_id, "actions": []}

        if self._notion:
            try:
                notion_result = await self._notion.sync_prd(prd_id)
                result["actions"].append({"type": "notion_sync", **notion_result})
            except Exception as exc:
                result["actions"].append({"type": "notion_sync", "error": str(exc)})

        self._sync_log.append(result)
        return result

    async def on_feedback_received(self, feedback_id: str) -> dict[str, Any]:
        """Trigger notification to participants when feedback is received."""
        result: dict[str, Any] = {"feedback_id": feedback_id, "actions": []}

        if self._notifications:
            try:
                from app.services import feedback as fb_service
                fb = fb_service.get_request_store().get(feedback_id)
                if fb:
                    for participant in fb.requested_from:
                        await self._notifications(
                            recipient=participant,
                            channel="email",
                            subject="Feedback requested",
                            body=f"Feedback has been requested for work item {fb.work_item_id}",
                        )
                    result["actions"].append({
                        "type": "notification",
                        "notified": fb.requested_from,
                    })
            except Exception as exc:
                result["actions"].append({"type": "notification", "error": str(exc)})

        self._sync_log.append(result)
        return result

    # -- introspection --------------------------------------------------------

    @property
    def sync_log(self) -> list[dict[str, Any]]:
        return list(self._sync_log)

    def clear_log(self) -> None:
        self._sync_log.clear()
