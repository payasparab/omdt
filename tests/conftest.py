"""Shared test fixtures for OMDT test suite.

Provides fake adapters, sample domain objects, event/audit cleanup,
and async test support configuration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers
from app.core.ids import generate_id
from app.domain.enums import (
    ArtifactType,
    CanonicalState,
    Priority,
    SourceChannel,
    WorkItemType,
)
from app.domain.models.work_item import WorkItem


# ---------------------------------------------------------------------------
# pytest-asyncio mode
# ---------------------------------------------------------------------------

pytest_plugins: list[str] = []


# ---------------------------------------------------------------------------
# Cleanup fixture — clears global event/audit state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_global_state():
    """Reset module-level event handlers and audit log for every test."""
    clear_handlers()
    clear_audit_log()
    yield
    clear_handlers()
    clear_audit_log()


# ---------------------------------------------------------------------------
# Fake adapters
# ---------------------------------------------------------------------------

class FakeAdapter:
    """Generic fake adapter that records calls for assertion."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses = responses or {}

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((action, params))
        return self._responses.get(action, {"status": "ok"})

    def assert_called(self, action: str) -> None:
        assert any(a == action for a, _ in self.calls), (
            f"Expected call to '{action}', got: {[a for a, _ in self.calls]}"
        )

    def assert_not_called(self) -> None:
        assert len(self.calls) == 0, f"Expected no calls, got: {self.calls}"


@pytest.fixture
def fake_linear_adapter() -> FakeAdapter:
    return FakeAdapter({"create_issue": {"issue_id": "LIN-123", "url": "https://linear.app/LIN-123"}})


@pytest.fixture
def fake_notion_adapter() -> FakeAdapter:
    return FakeAdapter({"create_page": {"page_id": "notion-page-1", "url": "https://notion.so/page-1"}})


@pytest.fixture
def fake_outlook_adapter() -> FakeAdapter:
    return FakeAdapter({"send_email": {"message_id": "msg-001"}})


@pytest.fixture
def fake_snowflake_adapter() -> FakeAdapter:
    return FakeAdapter({
        "create_user": {"status": "ok"},
        "grant_role": {"status": "ok"},
        "revoke_role": {"status": "ok"},
    })


@pytest.fixture
def fake_render_adapter() -> FakeAdapter:
    return FakeAdapter({"deploy_service": {"deploy_id": "dep-001", "status": "live"}})


@pytest.fixture
def fake_github_adapter() -> FakeAdapter:
    return FakeAdapter({"trigger_workflow": {"run_id": "run-123", "url": "https://github.com/run/123"}})


@pytest.fixture
def fake_gamma_adapter() -> FakeAdapter:
    return FakeAdapter({"create_presentation": {"presentation_id": "pres-001"}})


# ---------------------------------------------------------------------------
# Fake event bus
# ---------------------------------------------------------------------------

class FakeEventBus:
    """Collects emitted events for test assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        self.events.append((event_name, payload))

    def get_events(self, name: str | None = None) -> list[tuple[str, dict[str, Any]]]:
        if name is None:
            return list(self.events)
        return [(n, p) for n, p in self.events if n == name]

    def assert_emitted(self, event_name: str) -> None:
        assert any(n == event_name for n, _ in self.events), (
            f"Expected event '{event_name}', got: {[n for n, _ in self.events]}"
        )

    def clear(self) -> None:
        self.events.clear()


@pytest.fixture
def fake_event_bus() -> FakeEventBus:
    return FakeEventBus()


# ---------------------------------------------------------------------------
# Fake audit writer
# ---------------------------------------------------------------------------

class FakeAuditWriter:
    """Collects audit records for test assertions."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def append(self, **kwargs: Any) -> dict[str, Any]:
        record = {**kwargs, "event_time": datetime.now(timezone.utc).isoformat()}
        self.records.append(record)
        return record

    def assert_recorded(self, event_name: str) -> None:
        assert any(r.get("event_name") == event_name for r in self.records), (
            f"Expected audit '{event_name}', got: {[r.get('event_name') for r in self.records]}"
        )


@pytest.fixture
def fake_audit_writer() -> FakeAuditWriter:
    return FakeAuditWriter()


# ---------------------------------------------------------------------------
# Fake DB session
# ---------------------------------------------------------------------------

class FakeDBSession:
    """In-memory session substitute for tests that need a session object."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_db_session() -> FakeDBSession:
    return FakeDBSession()


# ---------------------------------------------------------------------------
# Sample domain objects
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_work_item() -> WorkItem:
    return WorkItem(
        title="Test Work Item",
        description="A test work item for integration testing",
        work_type=WorkItemType.TASK,
        priority=Priority.MEDIUM,
        source_channel=SourceChannel.API,
        requester_person_key="user@example.com",
    )


@pytest.fixture
def sample_project() -> dict[str, Any]:
    return {
        "id": generate_id(),
        "name": "Test Project",
        "description": "A test project",
        "owner_person_key": "user@example.com",
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_prd() -> dict[str, Any]:
    return {
        "work_item_id": generate_id(),
        "content": "# Test PRD\n\nThis is a test PRD document.",
        "author": "user@example.com",
    }


@pytest.fixture
def sample_person() -> dict[str, str]:
    return {
        "person_key": "user@example.com",
        "display_name": "Test User",
        "email": "user@example.com",
        "role": "data_analyst",
    }
