"""Notification dispatch job — routes notifications to the correct adapter.

Routes to: Outlook for email, Linear for comments, Notion for page updates.
Loads routing config from config/notifications.yaml.
Emits audit events for external sends.
"""
from __future__ import annotations

from typing import Any

from app.core.audit import record_audit_event
from app.core.config import load_notifications_config
from app.core.events import emit
from app.core.ids import generate_correlation_id

# ---------------------------------------------------------------------------
# Adapter registry type (injected at init)
# ---------------------------------------------------------------------------

AdapterLookup = dict[str, Any]  # channel_name -> adapter instance

# ---------------------------------------------------------------------------
# Channel-to-adapter mapping
# ---------------------------------------------------------------------------

_CHANNEL_ADAPTER_MAP = {
    "email": "outlook",
    "outlook": "outlook",
    "linear": "linear",
    "notion": "notion",
}

# ---------------------------------------------------------------------------
# Notification log (in-memory, for testing/audit)
# ---------------------------------------------------------------------------

_sent_log: list[dict[str, Any]] = []


def get_sent_log() -> list[dict[str, Any]]:
    return list(_sent_log)


def clear_sent_log() -> None:
    _sent_log.clear()


# ---------------------------------------------------------------------------
# Dispatch function
# ---------------------------------------------------------------------------

async def dispatch_notification(
    *,
    recipient: str,
    channel: str,
    subject: str,
    body: str,
    context: dict[str, Any] | None = None,
    adapters: AdapterLookup | None = None,
) -> dict[str, Any]:
    """Dispatch a notification to the correct adapter based on channel.

    Parameters
    ----------
    recipient : str
        Email address, Linear user ID, or person_key depending on channel.
    channel : str
        The notification channel (email, linear, notion).
    subject : str
        Notification subject / title.
    body : str
        Notification body content.
    context : dict
        Additional context (work_item_id, prd_id, etc.).
    adapters : dict
        Map of adapter_name -> adapter instance. If None, notification is
        logged but not actually sent (dry-run / test mode).
    """
    corr_id = generate_correlation_id()
    ctx = context or {}

    adapter_name = _CHANNEL_ADAPTER_MAP.get(channel, channel)

    record = {
        "recipient": recipient,
        "channel": channel,
        "adapter": adapter_name,
        "subject": subject,
        "body_preview": body[:200],
        "context": ctx,
        "sent": False,
    }

    try:
        if adapters and adapter_name in adapters:
            adapter = adapters[adapter_name]

            if adapter_name == "outlook":
                await adapter.execute("send_outbound", {
                    "to": [recipient],
                    "subject": subject,
                    "body": body,
                })
                record["sent"] = True

            elif adapter_name == "linear":
                issue_id = ctx.get("linear_issue_id", "")
                if issue_id:
                    await adapter.execute("comment_on_issue", {
                        "issue_id": issue_id,
                        "body": f"**{subject}**\n\n{body}",
                    })
                    record["sent"] = True

            elif adapter_name == "notion":
                page_id = ctx.get("notion_page_id", "")
                if page_id:
                    await adapter.execute("update_page", {
                        "page_id": page_id,
                        "properties": {
                            "LastNotification": {
                                "rich_text": [{"text": {"content": f"{subject}: {body[:100]}"}}],
                            },
                        },
                    })
                    record["sent"] = True
        else:
            # No adapter available — log-only mode
            record["dry_run"] = True

        _sent_log.append(record)

        await emit("communication.sent", {
            "recipient": recipient,
            "channel": channel,
            "subject": subject,
            "sent": record["sent"],
            "correlation_id": corr_id,
        })

        record_audit_event(
            event_name="notification.dispatched",
            actor_type="system",
            actor_id="notification_dispatch",
            object_type="notification",
            object_id=f"{channel}:{recipient}",
            change_summary=f"Notification sent via {channel} to {recipient}: {subject}",
            correlation_id=corr_id,
        )

        return {"success": True, **record}

    except Exception as exc:
        record["error"] = str(exc)
        _sent_log.append(record)

        record_audit_event(
            event_name="notification.failed",
            actor_type="system",
            actor_id="notification_dispatch",
            object_type="notification",
            object_id=f"{channel}:{recipient}",
            change_summary=f"Notification failed via {channel} to {recipient}: {exc}",
            correlation_id=corr_id,
        )

        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Batch dispatch
# ---------------------------------------------------------------------------

async def dispatch_to_group(
    *,
    recipients: list[str],
    channel: str,
    subject: str,
    body: str,
    context: dict[str, Any] | None = None,
    adapters: AdapterLookup | None = None,
) -> list[dict[str, Any]]:
    """Dispatch the same notification to multiple recipients."""
    results = []
    for recipient in recipients:
        result = await dispatch_notification(
            recipient=recipient,
            channel=channel,
            subject=subject,
            body=body,
            context=context,
            adapters=adapters,
        )
        results.append(result)
    return results
