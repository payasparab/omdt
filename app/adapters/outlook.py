"""Outlook adapter — email intake and outbound via Microsoft Graph API.

Implements PRD section 13.5 actions: ingest_messages, reply_in_thread,
send_outbound, list_inbox.

Uses httpx for the Microsoft Graph REST API.
Preserves thread IDs for conversation continuity.
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

GRAPH_API_URL = "https://graph.microsoft.com/v1.0"

_MUTATION_ACTIONS = frozenset({"reply_in_thread", "send_outbound"})


class OutlookAdapter(BaseAdapter):
    """Adapter for Microsoft Outlook via the Graph API."""

    name: str = "outlook"

    async def validate_config(self) -> None:
        required = ("tenant_id", "client_id", "client_secret")
        missing = [k for k in required if not self.config.get(k)]
        if missing:
            raise AdapterError(
                f"Outlook config missing required fields: {missing}",
                adapter_name=self.name,
            )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            token = await self._get_access_token()
            return {"healthy": True, "token_acquired": bool(token)}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    @with_retry()
    async def _execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._actions.get(action)
        if handler is None:
            raise AdapterError(
                f"Unknown Outlook action: {action}",
                adapter_name=self.name,
                action=action,
            )
        return await handler(self, payload)

    # -- auth -----------------------------------------------------------------

    async def _get_access_token(self) -> str:
        """Obtain an OAuth2 access token via client credentials flow."""
        tenant_id = self.config.get("tenant_id", "")
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")

        url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)

        if resp.status_code != 200:
            raise AdapterAuthError(
                f"Failed to acquire Outlook access token: {resp.status_code}",
                adapter_name=self.name,
            )
        return resp.json().get("access_token", "")

    async def _graph_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{GRAPH_API_URL}{path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, json=json_body, headers=headers)

        if resp.status_code == 401:
            raise AdapterAuthError(
                "Graph API authentication failed",
                adapter_name=self.name,
            )
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            raise AdapterRateLimitError(
                "Graph API rate limit exceeded",
                adapter_name=self.name,
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 500:
            raise AdapterError(
                f"Graph API server error: {resp.status_code}",
                adapter_name=self.name,
            )
        resp.raise_for_status()
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()

    # -- action implementations -----------------------------------------------

    async def _ingest_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        mailbox = payload.get("mailbox", self.config.get("shared_mailbox", "me"))
        folder = payload.get("folder", "inbox")
        top = payload.get("top", 25)
        filter_expr = payload.get("filter", "isRead eq false")

        path = f"/users/{mailbox}/mailFolders/{folder}/messages"
        params = f"?$top={top}&$filter={filter_expr}&$orderby=receivedDateTime desc"

        result = await self._graph_request("GET", f"{path}{params}")
        messages = result.get("value", [])

        normalized = []
        for msg in messages:
            normalized.append({
                "id": msg.get("id"),
                "conversation_id": msg.get("conversationId"),
                "internet_message_id": msg.get("internetMessageId"),
                "subject": msg.get("subject"),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                "received_at": msg.get("receivedDateTime"),
                "body_preview": msg.get("bodyPreview"),
                "has_attachments": msg.get("hasAttachments", False),
            })

        return {"messages": normalized, "count": len(normalized)}

    async def _reply_in_thread(self, payload: dict[str, Any]) -> dict[str, Any]:
        message_id = payload.get("message_id", "")
        body = payload.get("body", "")
        mailbox = payload.get("mailbox", self.config.get("shared_mailbox", "me"))
        if not message_id or not body:
            raise AdapterError(
                "reply_in_thread requires 'message_id' and 'body'",
                adapter_name=self.name,
                action="reply_in_thread",
            )

        path = f"/users/{mailbox}/messages/{message_id}/reply"
        reply_body = {
            "message": {
                "body": {"contentType": "HTML", "content": body},
            },
        }
        if payload.get("cc"):
            reply_body["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in payload["cc"]
            ]

        await self._graph_request("POST", path, json_body=reply_body)
        return {"replied": True, "message_id": message_id}

    async def _send_outbound(self, payload: dict[str, Any]) -> dict[str, Any]:
        to = payload.get("to", [])
        subject = payload.get("subject", "")
        body = payload.get("body", "")
        mailbox = payload.get("mailbox", self.config.get("shared_mailbox", "me"))
        if not to or not subject or not body:
            raise AdapterError(
                "send_outbound requires 'to', 'subject', and 'body'",
                adapter_name=self.name,
                action="send_outbound",
            )

        path = f"/users/{mailbox}/sendMail"
        mail_body = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to
                ],
            },
            "saveToSentItems": True,
        }
        if payload.get("cc"):
            mail_body["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in payload["cc"]
            ]

        await self._graph_request("POST", path, json_body=mail_body)
        return {"sent": True, "to": to, "subject": subject}

    async def _list_inbox(self, payload: dict[str, Any]) -> dict[str, Any]:
        mailbox = payload.get("mailbox", self.config.get("shared_mailbox", "me"))
        top = payload.get("top", 25)

        path = f"/users/{mailbox}/mailFolders/inbox/messages?$top={top}&$orderby=receivedDateTime desc"
        result = await self._graph_request("GET", path)
        messages = result.get("value", [])

        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject"),
                    "from": m.get("from", {}).get("emailAddress", {}).get("address"),
                    "received_at": m.get("receivedDateTime"),
                    "is_read": m.get("isRead", False),
                }
                for m in messages
            ],
            "count": len(messages),
        }

    _actions: dict[str, Any] = {
        "ingest_messages": _ingest_messages,
        "reply_in_thread": _reply_in_thread,
        "send_outbound": _send_outbound,
        "list_inbox": _list_inbox,
    }
