"""Gamma adapter — deck/briefing generation job lifecycle.

Implements PRD section 13.6 actions: submit_generation_job,
poll_job_status, retrieve_output, register_artifact.

Async job lifecycle: submit -> poll -> retrieve.
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


class GammaAdapter(BaseAdapter):
    """Adapter for the Gamma presentation generation API."""

    name: str = "gamma"

    async def validate_config(self) -> None:
        if not self.config.get("api_key"):
            raise AdapterError(
                "Gamma config missing required field: api_key",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            base_url = self.config.get("base_url", "https://api.gamma.app")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base_url}/health",
                    headers=self._headers(),
                )
            return {"healthy": resp.status_code == 200}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.get('api_key', '')}",
            "Content-Type": "application/json",
        }

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_url = self.config.get("base_url", "https://api.gamma.app")
        url = f"{base_url}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method, url, json=json_body, headers=self._headers()
            )

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Gamma API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise AdapterRateLimitError(
                "Gamma API rate limit exceeded",
                adapter_name=self.name,
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Gamma API server error: {resp.status_code}",
                adapter_name=self.name,
            )
        resp.raise_for_status()
        return resp.json()

    @with_retry()
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._actions.get(action)
        if handler is None:
            raise AdapterError(
                f"Unknown Gamma action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- action implementations -----------------------------------------------

    async def _submit_generation_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        template = payload.get("template", "")
        content = payload.get("content", {})
        if not template:
            raise AdapterError(
                "submit_generation_job requires 'template'",
                adapter_name=self.name,
                action="submit_generation_job",
            )
        body = {
            "template": template,
            "content": content,
            "options": payload.get("options", {}),
        }
        result = await self._api_request("POST", "/v1/jobs", json_body=body)
        return {
            "job_id": result.get("id"),
            "status": result.get("status", "submitted"),
        }

    async def _poll_job_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", "")
        if not job_id:
            raise AdapterError(
                "poll_job_status requires 'job_id'",
                adapter_name=self.name,
                action="poll_job_status",
            )
        result = await self._api_request("GET", f"/v1/jobs/{job_id}")
        return {
            "job_id": job_id,
            "status": result.get("status", "unknown"),
            "progress": result.get("progress"),
            "error": result.get("error"),
        }

    async def _retrieve_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = payload.get("job_id", "")
        if not job_id:
            raise AdapterError(
                "retrieve_output requires 'job_id'",
                adapter_name=self.name,
                action="retrieve_output",
            )
        result = await self._api_request("GET", f"/v1/jobs/{job_id}/output")
        return {
            "job_id": job_id,
            "output_url": result.get("url"),
            "format": result.get("format"),
            "metadata": result.get("metadata", {}),
        }

    async def _register_artifact(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Register a Gamma output as an OMDT artifact (local operation)."""
        job_id = payload.get("job_id", "")
        output_url = payload.get("output_url", "")
        artifact_type = payload.get("artifact_type", "PRESENTATION")
        return {
            "registered": True,
            "job_id": job_id,
            "output_url": output_url,
            "artifact_type": artifact_type,
        }

    _actions: dict[str, Any] = {
        "submit_generation_job": _submit_generation_job,
        "poll_job_status": _poll_job_status,
        "retrieve_output": _retrieve_output,
        "register_artifact": _register_artifact,
    }
