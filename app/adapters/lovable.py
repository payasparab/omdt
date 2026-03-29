"""Lovable adapter — status dashboard data push.

Implements PRD section 13.7 actions: push_project_status,
update_health_view, push_work_item_status.

Exposes data for the Lovable-hosted status dashboard.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import (
    BaseAdapter,
    AdapterAuthError,
    AdapterError,
    AdapterRateLimitError,
    with_retry,
)


class LovableAdapter(BaseAdapter):
    """Adapter for pushing data to the Lovable status dashboard."""

    name: str = "lovable"

    async def validate_config(self) -> None:
        if not self.config.get("base_url"):
            raise AdapterError(
                "Lovable config missing required field: base_url",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            base_url = self.config.get("base_url", "")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base_url}/health",
                    headers=self._headers(),
                )
            return {"healthy": resp.status_code == 200}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.config.get("api_key"):
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
        return headers

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_url = self.config.get("base_url", "")
        url = f"{base_url}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method, url, json=json_body, headers=self._headers()
            )

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Lovable API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            raise AdapterRateLimitError(
                "Lovable API rate limit exceeded",
                adapter_name=self.name,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Lovable API server error: {resp.status_code}",
                adapter_name=self.name,
            )
        resp.raise_for_status()
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()

    @with_retry()
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._actions.get(action)
        if handler is None:
            raise AdapterError(
                f"Unknown Lovable action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- action implementations -----------------------------------------------

    async def _push_project_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = payload.get("project_id", "")
        if not project_id:
            raise AdapterError(
                "push_project_status requires 'project_id'",
                adapter_name=self.name,
                action="push_project_status",
            )
        body = {
            "project_id": project_id,
            "name": payload.get("name", ""),
            "state": payload.get("state", ""),
            "owner": payload.get("owner", ""),
            "priority": payload.get("priority", ""),
            "work_item_count": payload.get("work_item_count", 0),
            "updated_at": payload.get("updated_at", ""),
        }
        result = await self._api_request(
            "PUT", f"/api/projects/{project_id}/status", json_body=body
        )
        return {"pushed": True, "project_id": project_id, **result}

    async def _update_health_view(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "adapters": payload.get("adapters", {}),
            "pipelines": payload.get("pipelines", {}),
            "deployments": payload.get("deployments", {}),
            "timestamp": payload.get("timestamp", ""),
        }
        result = await self._api_request(
            "PUT", "/api/health", json_body=body
        )
        return {"updated": True, **result}

    async def _push_work_item_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        work_item_id = payload.get("work_item_id", "")
        if not work_item_id:
            raise AdapterError(
                "push_work_item_status requires 'work_item_id'",
                adapter_name=self.name,
                action="push_work_item_status",
            )
        body = {
            "work_item_id": work_item_id,
            "title": payload.get("title", ""),
            "state": payload.get("state", ""),
            "priority": payload.get("priority", ""),
            "owner": payload.get("owner", ""),
            "project_id": payload.get("project_id", ""),
            "updated_at": payload.get("updated_at", ""),
        }
        result = await self._api_request(
            "PUT", f"/api/work-items/{work_item_id}/status", json_body=body
        )
        return {"pushed": True, "work_item_id": work_item_id, **result}

    _actions: dict[str, Any] = {
        "push_project_status": _push_project_status,
        "update_health_view": _update_health_view,
        "push_work_item_status": _push_work_item_status,
    }
