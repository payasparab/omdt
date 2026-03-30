"""Conversation thread service — manages multi-message clarification threads.

A conversation thread can span multiple messages across channels,
enabling asynchronous clarification workflows attached to work items.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import ActorType, SourceChannel
from app.domain.models.conversation import ConversationMessage, ConversationThread

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_thread_store: dict[str, ConversationThread] = {}  # keyed by thread.id (str)
_message_store: dict[str, list[ConversationMessage]] = {}  # keyed by thread.id


def get_thread_store() -> dict[str, ConversationThread]:
    return _thread_store


def get_message_store() -> dict[str, list[ConversationMessage]]:
    return _message_store


def clear_stores() -> None:
    _thread_store.clear()
    _message_store.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_message_hash(content: str) -> str:
    """SHA-256 hash of message content for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

async def create_thread(
    work_item_id: str,
    source_channel: SourceChannel | None = None,
    external_id: str | None = None,
) -> ConversationThread:
    """Create a new conversation thread attached to a work item."""
    now = datetime.now(timezone.utc)
    thread_id = uuid4()
    thread = ConversationThread(
        id=thread_id,
        work_item_id=UUID(work_item_id) if isinstance(work_item_id, str) else work_item_id,
        source_channel=source_channel,
        source_external_id=external_id,
        status="open",
        created_at=now,
        updated_at=now,
    )
    key = str(thread_id)
    _thread_store[key] = thread
    _message_store[key] = []

    corr_id = generate_correlation_id()
    await emit("conversation.thread_created", {
        "thread_id": key,
        "work_item_id": work_item_id,
        "source_channel": source_channel.value if source_channel else None,
        "correlation_id": corr_id,
    })

    record_audit_event(
        event_name="conversation.thread_created",
        actor_type="system",
        actor_id="conversation_service",
        object_type="conversation_thread",
        object_id=key,
        change_summary=f"Thread created for work item {work_item_id}",
        correlation_id=corr_id,
    )

    return thread


async def add_message(
    thread_id: str,
    sender: str,
    content: str,
    channel: SourceChannel | None = None,
    actor_type: ActorType = ActorType.HUMAN,
) -> ConversationMessage:
    """Add a message to an existing conversation thread."""
    thread = _thread_store.get(thread_id)
    if thread is None:
        raise ValueError(f"Thread not found: {thread_id}")

    msg = ConversationMessage(
        id=uuid4(),
        conversation_thread_id=UUID(thread_id),
        actor_id=sender,
        actor_type=actor_type,
        content=content,
        source_channel=channel,
        message_hash=_compute_message_hash(content),
        created_at=datetime.now(timezone.utc),
    )
    _message_store.setdefault(thread_id, []).append(msg)

    # Update thread timestamp
    thread.updated_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()
    await emit("conversation.message_added", {
        "thread_id": thread_id,
        "message_id": str(msg.id),
        "sender": sender,
        "channel": channel.value if channel else None,
        "correlation_id": corr_id,
    })

    record_audit_event(
        event_name="conversation.message_added",
        actor_type=actor_type.value,
        actor_id=sender,
        object_type="conversation_message",
        object_id=str(msg.id),
        change_summary=f"Message added to thread {thread_id}",
        correlation_id=corr_id,
    )

    return msg


async def get_thread(thread_id: str) -> ConversationThread | None:
    """Return a conversation thread by ID, or None if not found."""
    return _thread_store.get(thread_id)


async def get_thread_with_messages(
    thread_id: str,
) -> dict[str, Any] | None:
    """Return a thread with all its messages."""
    thread = _thread_store.get(thread_id)
    if thread is None:
        return None
    messages = _message_store.get(thread_id, [])
    return {
        "thread": thread,
        "messages": messages,
    }


async def list_threads(work_item_id: str) -> list[ConversationThread]:
    """List all conversation threads for a work item."""
    wi_uuid = UUID(work_item_id) if isinstance(work_item_id, str) else work_item_id
    return [
        t for t in _thread_store.values()
        if t.work_item_id == wi_uuid
    ]


async def resolve_thread(thread_id: str) -> ConversationThread | None:
    """Mark a thread as resolved."""
    thread = _thread_store.get(thread_id)
    if thread is None:
        return None
    thread.status = "resolved"
    thread.updated_at = datetime.now(timezone.utc)
    return thread
