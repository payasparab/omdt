"""Notion adapter — PRD pages, templates, and artifact linking.

Implements PRD section 13.4 actions: create_page, update_page,
get_page, sync_prd.

Uses httpx for the Notion REST API.
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

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"


class NotionAdapter(BaseAdapter):
    """Adapter for the Notion REST API."""

    name: str = "notion"

    async def validate_config(self) -> None:
        if not self.config.get("api_key"):
            raise AdapterError(
                "Notion config missing required field: api_key",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            result = await self._api_request("GET", "/users/me")
            return {"healthy": True, "bot": result.get("name")}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    @with_retry()
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._actions.get(action)
        if handler is None:
            raise AdapterError(
                f"Unknown Notion action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- HTTP transport -------------------------------------------------------

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_key = self.config.get("api_key", "")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }
        url = f"{NOTION_API_URL}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, json=json_body, headers=headers)

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Notion API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise AdapterRateLimitError(
                "Notion API rate limit exceeded",
                adapter_name=self.name,
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Notion API server error: {resp.status_code}",
                adapter_name=self.name,
            )
        resp.raise_for_status()
        return resp.json()

    # -- action implementations -----------------------------------------------

    async def _create_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        parent_id = payload.get("parent_id", "")
        title = payload.get("title", "")
        if not parent_id or not title:
            raise AdapterError(
                "create_page requires 'parent_id' and 'title'",
                adapter_name=self.name,
                action="create_page",
            )
        body: dict[str, Any] = {
            "parent": {"database_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title}}]
                },
            },
        }
        if payload.get("properties"):
            body["properties"].update(payload["properties"])
        if payload.get("children"):
            body["children"] = payload["children"]

        result = await self._api_request("POST", "/pages", json_body=body)
        return {
            "page_id": result.get("id"),
            "url": result.get("url"),
            "created": True,
        }

    async def _update_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        page_id = payload.get("page_id", "")
        if not page_id:
            raise AdapterError(
                "update_page requires 'page_id'",
                adapter_name=self.name,
                action="update_page",
            )
        body: dict[str, Any] = {}
        if payload.get("properties"):
            body["properties"] = payload["properties"]
        if payload.get("archived") is not None:
            body["archived"] = payload["archived"]

        result = await self._api_request(
            "PATCH", f"/pages/{page_id}", json_body=body
        )
        return {
            "page_id": result.get("id"),
            "url": result.get("url"),
            "updated": True,
        }

    async def _get_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        page_id = payload.get("page_id", "")
        if not page_id:
            raise AdapterError(
                "get_page requires 'page_id'",
                adapter_name=self.name,
                action="get_page",
            )
        result = await self._api_request("GET", f"/pages/{page_id}")
        return {
            "page_id": result.get("id"),
            "url": result.get("url"),
            "properties": result.get("properties", {}),
            "created_time": result.get("created_time"),
            "last_edited_time": result.get("last_edited_time"),
        }

    async def _sync_prd(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Idempotent PRD sync: create or update a Notion page for a PRD."""
        page_id = payload.get("page_id")
        parent_id = payload.get("parent_id", "")
        title = payload.get("title", "")
        work_item_id = payload.get("work_item_id", "")

        if page_id:
            # Update existing PRD page
            return await self._update_page({
                "page_id": page_id,
                "properties": payload.get("properties", {}),
            })
        else:
            # Create new PRD page
            if not parent_id:
                raise AdapterError(
                    "sync_prd requires 'parent_id' when creating a new page",
                    adapter_name=self.name,
                    action="sync_prd",
                )
            properties = payload.get("properties", {})
            if work_item_id:
                properties["WorkItemID"] = {
                    "rich_text": [{"text": {"content": work_item_id}}]
                }
            return await self._create_page({
                "parent_id": parent_id,
                "title": title or "Untitled PRD",
                "properties": properties,
                "children": payload.get("children", []),
            })

    _actions: dict[str, Any] = {
        "create_page": _create_page,
        "update_page": _update_page,
        "get_page": _get_page,
        "sync_prd": _sync_prd,
    }
