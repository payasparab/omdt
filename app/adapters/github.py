"""GitHub adapter — issues, PRs, and workflow management.

Implements PRD section 13.8 actions: create_issue, update_issue,
get_pr_status, get_workflow_status, trigger_workflow, link_commit.

Uses httpx for the GitHub REST API.
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

GITHUB_API_URL = "https://api.github.com"

_MUTATION_ACTIONS = frozenset({
    "create_issue",
    "update_issue",
    "trigger_workflow",
})


class GitHubAdapter(BaseAdapter):
    """Adapter for the GitHub REST API."""

    name: str = "github"

    async def validate_config(self) -> None:
        required = ("token", "owner", "repo")
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            raise AdapterError(
                f"GitHub config missing required fields: {missing}",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            result = await self._api_request("GET", "/rate_limit")
            return {
                "healthy": True,
                "rate_limit": result.get("rate", {}).get("remaining"),
            }
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.get('token', '')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _repo_path(self) -> str:
        owner = self.config.get("owner", "")
        repo = self.config.get("repo", "")
        return f"/repos/{owner}/{repo}"

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{GITHUB_API_URL}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method, url, json=json_body, headers=self._headers()
            )

        if resp.status_code == 401:
            raise AdapterAuthError(
                "GitHub API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 403:
            remaining = resp.headers.get("x-ratelimit-remaining", "")
            if remaining == "0":
                raise AdapterRateLimitError(
                    "GitHub API rate limit exceeded",
                    adapter_name=self.name,
                )
            raise AdapterAuthError(
                "GitHub API forbidden",
                adapter_name=self.name,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"GitHub API server error: {resp.status_code}",
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
                f"Unknown GitHub action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- action implementations -----------------------------------------------

    async def _create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = payload.get("title", "")
        if not title:
            raise AdapterError(
                "create_issue requires 'title'",
                adapter_name=self.name,
                action="create_issue",
            )
        body: dict[str, Any] = {"title": title}
        if payload.get("body"):
            body["body"] = payload["body"]
        if payload.get("labels"):
            body["labels"] = payload["labels"]
        if payload.get("assignees"):
            body["assignees"] = payload["assignees"]

        result = await self._api_request(
            "POST", f"{self._repo_path()}/issues", json_body=body
        )
        return {
            "issue_number": result.get("number"),
            "url": result.get("html_url"),
            "state": result.get("state"),
            "created": True,
        }

    async def _update_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        issue_number = payload.get("issue_number")
        if not issue_number:
            raise AdapterError(
                "update_issue requires 'issue_number'",
                adapter_name=self.name,
                action="update_issue",
            )
        body: dict[str, Any] = {}
        for field in ("title", "body", "state", "labels", "assignees"):
            if payload.get(field) is not None:
                body[field] = payload[field]

        result = await self._api_request(
            "PATCH",
            f"{self._repo_path()}/issues/{issue_number}",
            json_body=body,
        )
        return {
            "issue_number": result.get("number"),
            "url": result.get("html_url"),
            "state": result.get("state"),
            "updated": True,
        }

    async def _get_pr_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        pr_number = payload.get("pr_number")
        if not pr_number:
            raise AdapterError(
                "get_pr_status requires 'pr_number'",
                adapter_name=self.name,
                action="get_pr_status",
            )
        result = await self._api_request(
            "GET", f"{self._repo_path()}/pulls/{pr_number}"
        )
        return {
            "pr_number": result.get("number"),
            "state": result.get("state"),
            "merged": result.get("merged", False),
            "mergeable": result.get("mergeable"),
            "title": result.get("title"),
            "url": result.get("html_url"),
            "head_sha": result.get("head", {}).get("sha"),
        }

    async def _get_workflow_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = payload.get("run_id")
        if not run_id:
            raise AdapterError(
                "get_workflow_status requires 'run_id'",
                adapter_name=self.name,
                action="get_workflow_status",
            )
        result = await self._api_request(
            "GET", f"{self._repo_path()}/actions/runs/{run_id}"
        )
        return {
            "run_id": result.get("id"),
            "status": result.get("status"),
            "conclusion": result.get("conclusion"),
            "workflow_name": result.get("name"),
            "url": result.get("html_url"),
            "head_sha": result.get("head_sha"),
        }

    async def _trigger_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = payload.get("workflow_id", "")
        ref = payload.get("ref", "main")
        if not workflow_id:
            raise AdapterError(
                "trigger_workflow requires 'workflow_id'",
                adapter_name=self.name,
                action="trigger_workflow",
            )
        body: dict[str, Any] = {"ref": ref}
        if payload.get("inputs"):
            body["inputs"] = payload["inputs"]

        await self._api_request(
            "POST",
            f"{self._repo_path()}/actions/workflows/{workflow_id}/dispatches",
            json_body=body,
        )
        return {"triggered": True, "workflow_id": workflow_id, "ref": ref}

    async def _link_commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        sha = payload.get("sha", "")
        if not sha:
            raise AdapterError(
                "link_commit requires 'sha'",
                adapter_name=self.name,
                action="link_commit",
            )
        result = await self._api_request(
            "GET", f"{self._repo_path()}/commits/{sha}"
        )
        return {
            "sha": result.get("sha"),
            "message": result.get("commit", {}).get("message"),
            "author": result.get("commit", {}).get("author", {}).get("name"),
            "url": result.get("html_url"),
        }

    _actions: dict[str, Any] = {
        "create_issue": _create_issue,
        "update_issue": _update_issue,
        "get_pr_status": _get_pr_status,
        "get_workflow_status": _get_workflow_status,
        "trigger_workflow": _trigger_workflow,
        "link_commit": _link_commit,
    }
