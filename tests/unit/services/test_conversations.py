"""Tests for the conversation thread service."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import ActorType, SourceChannel
from app.services import conversations as conv_service
from app.services import work_items as wi_service


@pytest.fixture(autouse=True)
def _clean():
    wi_service.clear_store()
    conv_service.clear_stores()
    clear_audit_log()
    clear_handlers()
    yield
    wi_service.clear_store()
    conv_service.clear_stores()
    clear_audit_log()
    clear_handlers()


class TestCreateThread:
    @pytest.mark.asyncio
    async def test_create_thread(self):
        wi = await wi_service.create_work_item(title="Thread test")
        thread = await conv_service.create_thread(
            work_item_id=wi.id,
            source_channel=SourceChannel.OUTLOOK,
            external_id="msg-123",
        )
        assert thread.status == "open"
        assert str(thread.work_item_id) == wi.id

    @pytest.mark.asyncio
    async def test_create_thread_emits_event(self):
        events = []
        subscribe("conversation.thread_created", lambda e: events.append(e))

        wi = await wi_service.create_work_item(title="Event test")
        await conv_service.create_thread(work_item_id=wi.id)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_create_thread_writes_audit(self):
        wi = await wi_service.create_work_item(title="Audit test")
        await conv_service.create_thread(work_item_id=wi.id)
        log = get_audit_log()
        assert any(r["event_name"] == "conversation.thread_created" for r in log)


class TestAddMessage:
    @pytest.mark.asyncio
    async def test_add_message(self):
        wi = await wi_service.create_work_item(title="Msg test")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        thread_id = str(thread.id)

        msg = await conv_service.add_message(
            thread_id=thread_id,
            sender="alice",
            content="Hello, can you clarify?",
            channel=SourceChannel.OUTLOOK,
        )
        assert msg.actor_id == "alice"
        assert msg.content == "Hello, can you clarify?"
        assert msg.message_hash is not None

    @pytest.mark.asyncio
    async def test_multi_message_thread(self):
        wi = await wi_service.create_work_item(title="Multi msg")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        thread_id = str(thread.id)

        await conv_service.add_message(thread_id, "alice", "Question?")
        await conv_service.add_message(thread_id, "bob", "Answer.")
        await conv_service.add_message(thread_id, "alice", "Thanks!")

        data = await conv_service.get_thread_with_messages(thread_id)
        assert len(data["messages"]) == 3

    @pytest.mark.asyncio
    async def test_cross_channel_messages(self):
        wi = await wi_service.create_work_item(title="Cross channel")
        thread = await conv_service.create_thread(
            work_item_id=wi.id, source_channel=SourceChannel.OUTLOOK,
        )
        thread_id = str(thread.id)

        m1 = await conv_service.add_message(
            thread_id, "alice", "Via email", channel=SourceChannel.OUTLOOK,
        )
        m2 = await conv_service.add_message(
            thread_id, "bob", "Via Linear", channel=SourceChannel.LINEAR,
        )
        assert m1.source_channel == SourceChannel.OUTLOOK
        assert m2.source_channel == SourceChannel.LINEAR

    @pytest.mark.asyncio
    async def test_add_message_missing_thread(self):
        with pytest.raises(ValueError, match="Thread not found"):
            await conv_service.add_message("nonexistent", "alice", "Hello")

    @pytest.mark.asyncio
    async def test_add_message_updates_thread_timestamp(self):
        wi = await wi_service.create_work_item(title="Timestamp test")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        thread_id = str(thread.id)
        original_updated = thread.updated_at

        await conv_service.add_message(thread_id, "alice", "Message")
        updated_thread = await conv_service.get_thread(thread_id)
        assert updated_thread.updated_at >= original_updated


class TestGetThread:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        wi = await wi_service.create_work_item(title="Get test")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        found = await conv_service.get_thread(str(thread.id))
        assert found is not None
        assert found.id == thread.id

    @pytest.mark.asyncio
    async def test_get_missing(self):
        found = await conv_service.get_thread("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_with_messages(self):
        wi = await wi_service.create_work_item(title="Get msgs")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        thread_id = str(thread.id)
        await conv_service.add_message(thread_id, "alice", "Hello")

        data = await conv_service.get_thread_with_messages(thread_id)
        assert data is not None
        assert data["thread"].id == thread.id
        assert len(data["messages"]) == 1


class TestListThreads:
    @pytest.mark.asyncio
    async def test_list_by_work_item(self):
        wi = await wi_service.create_work_item(title="List test")
        await conv_service.create_thread(work_item_id=wi.id)
        await conv_service.create_thread(work_item_id=wi.id)

        threads = await conv_service.list_threads(wi.id)
        assert len(threads) == 2

    @pytest.mark.asyncio
    async def test_list_empty(self):
        wi = await wi_service.create_work_item(title="Empty")
        threads = await conv_service.list_threads(wi.id)
        assert len(threads) == 0


class TestResolveThread:
    @pytest.mark.asyncio
    async def test_resolve(self):
        wi = await wi_service.create_work_item(title="Resolve")
        thread = await conv_service.create_thread(work_item_id=wi.id)
        resolved = await conv_service.resolve_thread(str(thread.id))
        assert resolved.status == "resolved"

    @pytest.mark.asyncio
    async def test_resolve_missing(self):
        result = await conv_service.resolve_thread("nonexistent")
        assert result is None
