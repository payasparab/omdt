"""Unit tests for the GitHub adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.github import GitHubAdapter
from app.adapters.base import AdapterError
from tests.fixtures.github_responses import (
    VALID_CONFIG,
    CREATE_ISSUE_RESPONSE,
    UPDATE_ISSUE_RESPONSE,
    PR_STATUS_RESPONSE,
    WORKFLOW_STATUS_RESPONSE,
    TRIGGER_WORKFLOW_RESPONSE,
    COMMIT_RESPONSE,
)


@pytest.fixture
def adapter() -> GitHubAdapter:
    return GitHubAdapter(config=VALID_CONFIG.copy())


def _mock_api(response: dict[str, Any]):
    return patch.object(
        GitHubAdapter, "_api_request", new_callable=AsyncMock, return_value=response
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid(self, adapter: GitHubAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_token(self):
        a = GitHubAdapter(config={"owner": "o", "repo": "r"})
        with pytest.raises(AdapterError, match="missing required fields"):
            await a.validate_config()


class TestCreateIssue:
    @pytest.mark.asyncio
    async def test_creates(self, adapter: GitHubAdapter):
        with _mock_api(CREATE_ISSUE_RESPONSE):
            result = await adapter.execute(
                "create_issue",
                {"title": "Test issue", "labels": ["bug"]},
            )
            assert result["created"] is True
            assert result["issue_number"] == 42

    @pytest.mark.asyncio
    async def test_missing_title(self, adapter: GitHubAdapter):
        with pytest.raises(AdapterError, match="title"):
            await adapter.execute("create_issue", {})


class TestUpdateIssue:
    @pytest.mark.asyncio
    async def test_updates(self, adapter: GitHubAdapter):
        with _mock_api(UPDATE_ISSUE_RESPONSE):
            result = await adapter.execute(
                "update_issue",
                {"issue_number": 42, "state": "closed"},
            )
            assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_missing_number(self, adapter: GitHubAdapter):
        with pytest.raises(AdapterError, match="issue_number"):
            await adapter.execute("update_issue", {"title": "T"})


class TestGetPrStatus:
    @pytest.mark.asyncio
    async def test_gets_status(self, adapter: GitHubAdapter):
        with _mock_api(PR_STATUS_RESPONSE):
            result = await adapter.execute("get_pr_status", {"pr_number": 10})
            assert result["state"] == "open"
            assert result["merged"] is False
            assert result["head_sha"] == "abc123def456"

    @pytest.mark.asyncio
    async def test_missing_pr_number(self, adapter: GitHubAdapter):
        with pytest.raises(AdapterError, match="pr_number"):
            await adapter.execute("get_pr_status", {})


class TestGetWorkflowStatus:
    @pytest.mark.asyncio
    async def test_gets_status(self, adapter: GitHubAdapter):
        with _mock_api(WORKFLOW_STATUS_RESPONSE):
            result = await adapter.execute(
                "get_workflow_status", {"run_id": 999}
            )
            assert result["status"] == "completed"
            assert result["conclusion"] == "success"


class TestTriggerWorkflow:
    @pytest.mark.asyncio
    async def test_triggers(self, adapter: GitHubAdapter):
        with _mock_api(TRIGGER_WORKFLOW_RESPONSE):
            result = await adapter.execute(
                "trigger_workflow",
                {"workflow_id": "ci.yml", "ref": "main"},
            )
            assert result["triggered"] is True

    @pytest.mark.asyncio
    async def test_missing_workflow_id(self, adapter: GitHubAdapter):
        with pytest.raises(AdapterError, match="workflow_id"):
            await adapter.execute("trigger_workflow", {})


class TestLinkCommit:
    @pytest.mark.asyncio
    async def test_links(self, adapter: GitHubAdapter):
        with _mock_api(COMMIT_RESPONSE):
            result = await adapter.execute(
                "link_commit", {"sha": "abc123def456"}
            )
            assert result["sha"] == "abc123def456"
            assert result["author"] == "Payas Parab"
