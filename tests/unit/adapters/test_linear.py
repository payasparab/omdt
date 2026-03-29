"""Unit tests for the Linear adapter.

Tests GraphQL request building, response normalization, idempotent sync,
and webhook payload parsing.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.linear import LinearAdapter
from app.adapters.base import AdapterError
from app.core.audit import AuditWriter
from tests.fixtures.linear_responses import (
    VALID_CONFIG,
    CREATE_ISSUE_RESPONSE,
    UPDATE_ISSUE_RESPONSE,
    CREATE_PROJECT_RESPONSE,
    COMMENT_CREATE_RESPONSE,
    SEARCH_RESPONSE,
    WEBHOOK_ISSUE_CREATE,
    WEBHOOK_ISSUE_UPDATE,
)


@pytest.fixture
def adapter() -> LinearAdapter:
    return LinearAdapter(config=VALID_CONFIG.copy())


@pytest.fixture
def adapter_with_audit() -> tuple[LinearAdapter, AuditWriter]:
    writer = AuditWriter()
    a = LinearAdapter(config=VALID_CONFIG.copy(), audit_writer=writer)
    return a, writer


def _mock_graphql(response: dict[str, Any]):
    """Patch _graphql_request to return a canned response."""
    return patch.object(
        LinearAdapter, "_graphql_request", new_callable=AsyncMock, return_value=response
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid_config(self, adapter: LinearAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        a = LinearAdapter(config={})
        with pytest.raises(AdapterError, match="api_key"):
            await a.validate_config()


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_creates_issue(self, adapter: LinearAdapter):
        with _mock_graphql(CREATE_ISSUE_RESPONSE) as mock:
            result = await adapter.execute(
                "create_issue",
                {"title": "Test Issue", "team_id": "team_01"},
            )
            assert result["success"] is True
            assert result["issue"]["identifier"] == "DATA-1"
            # Verify GraphQL was called with the right mutation
            call_args = mock.call_args
            assert "IssueCreate" in call_args[1].get("query", call_args[0][0])

    @pytest.mark.asyncio
    async def test_create_issue_missing_title(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="title"):
            await adapter.execute("create_issue", {"team_id": "team_01"})

    @pytest.mark.asyncio
    async def test_create_issue_missing_team_id(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="team_id"):
            await adapter.execute("create_issue", {"title": "T"})


class TestUpdateIssue:
    @pytest.mark.asyncio
    async def test_updates_issue(self, adapter: LinearAdapter):
        with _mock_graphql(UPDATE_ISSUE_RESPONSE):
            result = await adapter.execute(
                "update_issue",
                {"issue_id": "issue_01", "title": "Updated Issue"},
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_issue_missing_id(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="issue_id"):
            await adapter.execute("update_issue", {"title": "T"})


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_creates_project(self, adapter: LinearAdapter):
        with _mock_graphql(CREATE_PROJECT_RESPONSE):
            result = await adapter.execute(
                "create_project",
                {"name": "Test Project", "team_ids": ["team_01"]},
            )
            assert result["success"] is True
            assert result["project"]["name"] == "Test Project"

    @pytest.mark.asyncio
    async def test_create_project_missing_name(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="name"):
            await adapter.execute("create_project", {"team_ids": ["t"]})


class TestCommentOnIssue:
    @pytest.mark.asyncio
    async def test_creates_comment(self, adapter: LinearAdapter):
        with _mock_graphql(COMMENT_CREATE_RESPONSE):
            result = await adapter.execute(
                "comment_on_issue",
                {"issue_id": "issue_01", "body": "A comment"},
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_comment_missing_body(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="body"):
            await adapter.execute("comment_on_issue", {"issue_id": "i"})


class TestSearchIssue:
    @pytest.mark.asyncio
    async def test_search(self, adapter: LinearAdapter):
        with _mock_graphql(SEARCH_RESPONSE):
            result = await adapter.execute(
                "search_issue", {"query": "dashboard"}
            )
            assert result["count"] == 1
            assert result["issues"][0]["identifier"] == "DATA-1"

    @pytest.mark.asyncio
    async def test_search_missing_query(self, adapter: LinearAdapter):
        with pytest.raises(AdapterError, match="query"):
            await adapter.execute("search_issue", {})


class TestSyncWorkItem:
    @pytest.mark.asyncio
    async def test_sync_existing_updates(self, adapter: LinearAdapter):
        with _mock_graphql(UPDATE_ISSUE_RESPONSE):
            result = await adapter.execute(
                "sync_work_item",
                {
                    "work_item_id": "wi_01",
                    "linear_issue_id": "issue_01",
                    "title": "Updated",
                },
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_new_creates(self, adapter: LinearAdapter):
        with _mock_graphql(CREATE_ISSUE_RESPONSE):
            result = await adapter.execute(
                "sync_work_item",
                {
                    "work_item_id": "wi_01",
                    "title": "New Issue",
                    "team_id": "team_01",
                },
            )
            assert result["success"] is True


class TestReceiveWebhook:
    @pytest.mark.asyncio
    async def test_parses_create_webhook(self, adapter: LinearAdapter):
        result = await adapter.execute("receive_webhook", WEBHOOK_ISSUE_CREATE)
        assert result["webhook_type"] == "Issue"
        assert result["action"] == "create"
        assert result["linear_id"] == "issue_webhook_01"
        assert result["identifier"] == "DATA-5"

    @pytest.mark.asyncio
    async def test_parses_update_webhook(self, adapter: LinearAdapter):
        result = await adapter.execute("receive_webhook", WEBHOOK_ISSUE_UPDATE)
        assert result["action"] == "update"
        assert result["state"] == "In Progress"


class TestAuditEmission:
    @pytest.mark.asyncio
    async def test_mutation_emits_audit(
        self, adapter_with_audit: tuple[LinearAdapter, AuditWriter]
    ):
        a, writer = adapter_with_audit
        with _mock_graphql(CREATE_ISSUE_RESPONSE):
            await a.execute(
                "create_issue",
                {"title": "Test", "team_id": "team_01"},
            )
        assert len(writer.records) == 1
        assert "linear.create_issue" in writer.records[0].event_name
