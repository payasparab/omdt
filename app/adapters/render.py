"""Render adapter — deployment, worker, and cron job management.

Implements PRD section 13.9 actions: deploy_service, restart_worker,
create_cron_job, update_cron_job, get_deploy_logs, get_service_status.

Uses httpx for the Render REST API.
Registers release state in OMDT.
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

RENDER_API_URL = "https://api.render.com/v1"

_MUTATION_ACTIONS = frozenset({
    "deploy_service",
    "restart_worker",
    "create_cron_job",
    "update_cron_job",
})


class RenderAdapter(BaseAdapter):
    """Adapter for the Render hosting platform API."""

    name: str = "render"

    async def validate_config(self) -> None:
        if not self.config.get("api_key"):
            raise AdapterError(
                "Render config missing required field: api_key",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            result = await self._api_request("GET", "/owners")
            owners = result if isinstance(result, list) else result.get("owners", [])
            return {"healthy": True, "owner_count": len(owners)}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.get('api_key', '')}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{RENDER_API_URL}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method, url, json=json_body, headers=self._headers()
            )

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Render API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise AdapterRateLimitError(
                "Render API rate limit exceeded",
                adapter_name=self.name,
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Render API server error: {resp.status_code}",
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
                f"Unknown Render action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- action implementations -----------------------------------------------

    async def _deploy_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        service_id = payload.get("service_id", "")
        if not service_id:
            raise AdapterError(
                "deploy_service requires 'service_id'",
                adapter_name=self.name,
                action="deploy_service",
            )
        body: dict[str, Any] = {}
        if payload.get("clear_cache"):
            body["clearCache"] = "clear"

        result = await self._api_request(
            "POST", f"/services/{service_id}/deploys", json_body=body
        )
        deploy = result.get("deploy", result)
        return {
            "deploy_id": deploy.get("id"),
            "service_id": service_id,
            "status": deploy.get("status", "created"),
            "commit_id": deploy.get("commit", {}).get("id") if isinstance(deploy.get("commit"), dict) else None,
        }

    async def _restart_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        service_id = payload.get("service_id", "")
        if not service_id:
            raise AdapterError(
                "restart_worker requires 'service_id'",
                adapter_name=self.name,
                action="restart_worker",
            )
        await self._api_request("POST", f"/services/{service_id}/restart")
        return {"restarted": True, "service_id": service_id}

    async def _create_cron_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name", "")
        schedule = payload.get("schedule", "")
        command = payload.get("command", "")
        if not name or not schedule or not command:
            raise AdapterError(
                "create_cron_job requires 'name', 'schedule', and 'command'",
                adapter_name=self.name,
                action="create_cron_job",
            )
        body = {
            "type": "cron_job",
            "name": name,
            "schedule": schedule,
            "serviceDetails": {
                "envSpecificDetails": {
                    "dockerCommand": command,
                },
            },
        }
        if payload.get("env_id"):
            body["envId"] = payload["env_id"]

        result = await self._api_request("POST", "/services", json_body=body)
        service = result.get("service", result)
        return {
            "service_id": service.get("id"),
            "name": name,
            "schedule": schedule,
            "created": True,
        }

    async def _update_cron_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        service_id = payload.get("service_id", "")
        if not service_id:
            raise AdapterError(
                "update_cron_job requires 'service_id'",
                adapter_name=self.name,
                action="update_cron_job",
            )
        body: dict[str, Any] = {}
        if payload.get("schedule"):
            body["schedule"] = payload["schedule"]
        if payload.get("command"):
            body["serviceDetails"] = {
                "envSpecificDetails": {"dockerCommand": payload["command"]}
            }

        result = await self._api_request(
            "PATCH", f"/services/{service_id}", json_body=body
        )
        return {
            "service_id": service_id,
            "updated": True,
            "schedule": payload.get("schedule"),
        }

    async def _get_deploy_logs(self, payload: dict[str, Any]) -> dict[str, Any]:
        service_id = payload.get("service_id", "")
        deploy_id = payload.get("deploy_id", "")
        if not service_id or not deploy_id:
            raise AdapterError(
                "get_deploy_logs requires 'service_id' and 'deploy_id'",
                adapter_name=self.name,
                action="get_deploy_logs",
            )
        result = await self._api_request(
            "GET", f"/services/{service_id}/deploys/{deploy_id}/logs"
        )
        logs = result if isinstance(result, list) else result.get("logs", [])
        return {
            "service_id": service_id,
            "deploy_id": deploy_id,
            "logs": logs,
        }

    async def _get_service_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        service_id = payload.get("service_id", "")
        if not service_id:
            raise AdapterError(
                "get_service_status requires 'service_id'",
                adapter_name=self.name,
                action="get_service_status",
            )
        result = await self._api_request("GET", f"/services/{service_id}")
        service = result.get("service", result)
        return {
            "service_id": service_id,
            "name": service.get("name"),
            "type": service.get("type"),
            "status": service.get("serviceDetails", {}).get("status")
            if isinstance(service.get("serviceDetails"), dict)
            else None,
            "url": service.get("serviceDetails", {}).get("url")
            if isinstance(service.get("serviceDetails"), dict)
            else None,
        }

    _actions: dict[str, Any] = {
        "deploy_service": _deploy_service,
        "restart_worker": _restart_worker,
        "create_cron_job": _create_cron_job,
        "update_cron_job": _update_cron_job,
        "get_deploy_logs": _get_deploy_logs,
        "get_service_status": _get_service_status,
    }
