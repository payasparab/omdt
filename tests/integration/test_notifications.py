"""Integration test: notification routing per channel selection rules."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log
from app.core.events import clear_handlers
from app.domain.enums import SourceChannel
from tests.conftest import FakeAdapter


@pytest.fixture(autouse=True)
def _clean():
    clear_audit_log()
    clear_handlers()
    yield
    clear_audit_log()
    clear_handlers()


class NotificationRouter:
    """Test helper that routes notifications based on source channel.

    Implements §11.5 channel selection rules:
    - Outlook source -> reply via Outlook
    - Linear source -> reply via Linear comment
    - Fallback -> use default channel
    """

    def __init__(
        self,
        outlook_adapter: FakeAdapter,
        linear_adapter: FakeAdapter,
        default_adapter: FakeAdapter,
    ) -> None:
        self._adapters = {
            SourceChannel.OUTLOOK: ("send_email", outlook_adapter),
            SourceChannel.EMAIL: ("send_email", outlook_adapter),
            SourceChannel.LINEAR: ("add_comment", linear_adapter),
        }
        self._default = ("send_notification", default_adapter)

    async def route(
        self,
        source_channel: SourceChannel,
        message: str,
        recipient: str,
    ) -> dict:
        action, adapter = self._adapters.get(source_channel, self._default)
        try:
            result = await adapter.execute(action, {
                "message": message,
                "recipient": recipient,
                "channel": source_channel.value,
            })
            return {"success": True, "channel": source_channel.value, **result}
        except Exception:
            # Fallback routing
            fb_action, fb_adapter = self._default
            result = await fb_adapter.execute(fb_action, {
                "message": message,
                "recipient": recipient,
                "channel": "fallback",
            })
            return {"success": True, "channel": "fallback", **result}


class TestNotificationRouting:
    """Test notification routing per §11.5 channel selection rules."""

    @pytest.mark.asyncio
    async def test_outlook_source_routes_to_outlook(
        self,
        fake_outlook_adapter: FakeAdapter,
        fake_linear_adapter: FakeAdapter,
    ) -> None:
        """Outlook source -> reply via Outlook."""
        default = FakeAdapter()
        router = NotificationRouter(fake_outlook_adapter, fake_linear_adapter, default)

        result = await router.route(
            SourceChannel.OUTLOOK,
            message="Your request has been processed",
            recipient="user@example.com",
        )

        assert result["success"] is True
        assert result["channel"] == "outlook"
        fake_outlook_adapter.assert_called("send_email")
        fake_linear_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_linear_source_routes_to_linear(
        self,
        fake_outlook_adapter: FakeAdapter,
        fake_linear_adapter: FakeAdapter,
    ) -> None:
        """Linear source -> reply via Linear comment."""
        default = FakeAdapter()
        router = NotificationRouter(fake_outlook_adapter, fake_linear_adapter, default)

        result = await router.route(
            SourceChannel.LINEAR,
            message="Issue has been triaged",
            recipient="user@example.com",
        )

        assert result["success"] is True
        assert result["channel"] == "linear"
        fake_linear_adapter.assert_called("add_comment")
        fake_outlook_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_routing_on_unknown_channel(
        self,
        fake_outlook_adapter: FakeAdapter,
        fake_linear_adapter: FakeAdapter,
    ) -> None:
        """Unknown channel falls back to default adapter."""
        default = FakeAdapter()
        router = NotificationRouter(fake_outlook_adapter, fake_linear_adapter, default)

        result = await router.route(
            SourceChannel.CLI,
            message="Update notification",
            recipient="user@example.com",
        )

        assert result["success"] is True
        assert result["channel"] == "cli"  # original channel used
        default.assert_called("send_notification")

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(
        self,
        fake_linear_adapter: FakeAdapter,
    ) -> None:
        """When primary channel fails, fall back to default."""
        failing_outlook = FakeAdapter()

        async def fail_execute(action, params):
            raise RuntimeError("Outlook unavailable")

        failing_outlook.execute = fail_execute

        default = FakeAdapter()
        router = NotificationRouter(failing_outlook, fake_linear_adapter, default)

        result = await router.route(
            SourceChannel.OUTLOOK,
            message="Fallback test",
            recipient="user@example.com",
        )

        assert result["success"] is True
        assert result["channel"] == "fallback"
        default.assert_called("send_notification")

    @pytest.mark.asyncio
    async def test_email_source_routes_to_outlook(
        self,
        fake_outlook_adapter: FakeAdapter,
        fake_linear_adapter: FakeAdapter,
    ) -> None:
        """Email source also routes to Outlook adapter."""
        default = FakeAdapter()
        router = NotificationRouter(fake_outlook_adapter, fake_linear_adapter, default)

        result = await router.route(
            SourceChannel.EMAIL,
            message="Email reply",
            recipient="user@example.com",
        )

        assert result["success"] is True
        fake_outlook_adapter.assert_called("send_email")
