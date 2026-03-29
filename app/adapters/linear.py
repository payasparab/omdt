"""Linear adapter — project and issue management via GraphQL.

Implements PRD section 13.3 actions: create_issue, update_issue,
create_project, comment_on_issue, search_issue, sync_work_item,
receive_webhook.

Uses httpx for HTTP calls to the Linear GraphQL API.
All mutations emit audit events. Sync operations are idempotent.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import (
    BaseAdapter,
    AdapterAuthError,
    AdapterError,
    AdapterRateLimitError,
    AdapterTimeoutError,
    with_retry,
)

LINEAR_API_URL = "https://api.linear.app/graphql"

_MUTATION_ACTIONS = frozenset({
    "create_issue",
    "update_issue",
    "create_project",
    "comment_on_issue",
    "sync_work_item",
})


class LinearAdapter(BaseAdapter):
    """Adapter for the Linear GraphQL API."""

    name: str = "linear"

    async def validate_config(self) -> None:
        if not self.config.get("api_key"):
            raise AdapterError(
                "Linear config missing required field: api_key",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            result = await self._graphql_request(
                query="{ viewer { id name } }",
            )
            return {"healthy": True, "viewer": result.get("data", {}).get("viewer")}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    @with_retry()
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._actions.get(action)
        if handler is None:
            raise AdapterError(
                f"Unknown Linear action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- GraphQL transport ----------------------------------------------------

    async def _graphql_request(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a GraphQL request to Linear and return the JSON response."""
        api_key = self.config.get("api_key", "")
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(LINEAR_API_URL, json=body, headers=headers)

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Linear API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise AdapterRateLimitError(
                "Linear API rate limit exceeded",
                adapter_name=self.name,
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Linear API server error: {resp.status_code}",
                adapter_name=self.name,
            )
        resp.raise_for_status()
        return resp.json()

    # -- action implementations -----------------------------------------------

    async def _create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = payload.get("title", "")
        team_id = payload.get("team_id", "")
        if not title or not team_id:
            raise AdapterError(
                "create_issue requires 'title' and 'team_id'",
                adapter_name=self.name,
                action="create_issue",
            )
        query = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue { id identifier title state { name } }
            }
        }
        """
        variables = {
            "input": {
                "title": title,
                "teamId": team_id,
                "description": payload.get("description", ""),
                "priority": payload.get("priority", 0),
            }
        }
        if payload.get("assignee_id"):
            variables["input"]["assigneeId"] = payload["assignee_id"]
        if payload.get("label_ids"):
            variables["input"]["labelIds"] = payload["label_ids"]

        result = await self._graphql_request(query, variables)
        data = result.get("data", {}).get("issueCreate", {})
        return {
            "success": data.get("success", False),
            "issue": data.get("issue"),
        }

    async def _update_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        issue_id = payload.get("issue_id", "")
        if not issue_id:
            raise AdapterError(
                "update_issue requires 'issue_id'",
                adapter_name=self.name,
                action="update_issue",
            )
        query = """
        mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue { id identifier title state { name } }
            }
        }
        """
        update_input: dict[str, Any] = {}
        for field in ("title", "description", "priority", "stateId", "assigneeId"):
            snake = field.replace("Id", "_id").replace("S", "_s") if field != "title" and field != "description" and field != "priority" else field
            if field in payload:
                update_input[field] = payload[field]
            # also check snake_case versions
            snake_key = _camel_to_snake(field)
            if snake_key in payload and field not in update_input:
                update_input[field] = payload[snake_key]

        variables = {"id": issue_id, "input": update_input}
        result = await self._graphql_request(query, variables)
        data = result.get("data", {}).get("issueUpdate", {})
        return {
            "success": data.get("success", False),
            "issue": data.get("issue"),
        }

    async def _create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name", "")
        team_ids = payload.get("team_ids", [])
        if not name or not team_ids:
            raise AdapterError(
                "create_project requires 'name' and 'team_ids'",
                adapter_name=self.name,
                action="create_project",
            )
        query = """
        mutation ProjectCreate($input: ProjectCreateInput!) {
            projectCreate(input: $input) {
                success
                project { id name }
            }
        }
        """
        variables = {
            "input": {
                "name": name,
                "teamIds": team_ids,
                "description": payload.get("description", ""),
            }
        }
        result = await self._graphql_request(query, variables)
        data = result.get("data", {}).get("projectCreate", {})
        return {
            "success": data.get("success", False),
            "project": data.get("project"),
        }

    async def _comment_on_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        issue_id = payload.get("issue_id", "")
        body = payload.get("body", "")
        if not issue_id or not body:
            raise AdapterError(
                "comment_on_issue requires 'issue_id' and 'body'",
                adapter_name=self.name,
                action="comment_on_issue",
            )
        query = """
        mutation CommentCreate($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
                comment { id body }
            }
        }
        """
        variables = {"input": {"issueId": issue_id, "body": body}}
        result = await self._graphql_request(query, variables)
        data = result.get("data", {}).get("commentCreate", {})
        return {
            "success": data.get("success", False),
            "comment": data.get("comment"),
        }

    async def _search_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        term = payload.get("query", "")
        if not term:
            raise AdapterError(
                "search_issue requires 'query'",
                adapter_name=self.name,
                action="search_issue",
            )
        query = """
        query IssueSearch($term: String!) {
            issueSearch(query: $term, first: 20) {
                nodes { id identifier title state { name } }
            }
        }
        """
        result = await self._graphql_request(query, {"term": term})
        nodes = (
            result.get("data", {}).get("issueSearch", {}).get("nodes", [])
        )
        return {"issues": nodes, "count": len(nodes)}

    async def _sync_work_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Idempotent sync: upserts a Linear issue from OMDT work item state."""
        work_item_id = payload.get("work_item_id", "")
        linear_issue_id = payload.get("linear_issue_id")
        if not work_item_id:
            raise AdapterError(
                "sync_work_item requires 'work_item_id'",
                adapter_name=self.name,
                action="sync_work_item",
            )
        # If linear_issue_id exists, update; otherwise create.
        if linear_issue_id:
            return await self._update_issue({
                "issue_id": linear_issue_id,
                **{k: v for k, v in payload.items()
                   if k not in ("work_item_id", "linear_issue_id")},
            })
        else:
            return await self._create_issue(payload)

    async def _receive_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse and normalize an incoming Linear webhook payload."""
        action = payload.get("action", "")
        webhook_type = payload.get("type", "")
        data = payload.get("data", {})
        return {
            "webhook_type": webhook_type,
            "action": action,
            "linear_id": data.get("id"),
            "identifier": data.get("identifier"),
            "title": data.get("title"),
            "state": data.get("state", {}).get("name") if isinstance(data.get("state"), dict) else data.get("state"),
            "raw": data,
        }

    _actions: dict[str, Any] = {
        "create_issue": _create_issue,
        "update_issue": _update_issue,
        "create_project": _create_project,
        "comment_on_issue": _comment_on_issue,
        "search_issue": _search_issue,
        "sync_work_item": _sync_work_item,
        "receive_webhook": _receive_webhook,
    }


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
