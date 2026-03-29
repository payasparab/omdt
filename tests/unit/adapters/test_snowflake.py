"""Unit tests for the Snowflake adapter."""

from __future__ import annotations

from typing import Any

import pytest

from app.adapters.snowflake import SnowflakeAdapter
from app.adapters.base import AdapterError
from app.core.audit import AuditWriter
from tests.fixtures.snowflake_responses import VALID_CONFIG


@pytest.fixture
def adapter() -> SnowflakeAdapter:
    return SnowflakeAdapter(config=VALID_CONFIG.copy())


@pytest.fixture
def adapter_with_audit() -> tuple[SnowflakeAdapter, AuditWriter]:
    writer = AuditWriter()
    a = SnowflakeAdapter(config=VALID_CONFIG.copy(), audit_writer=writer)
    return a, writer


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid_config_passes(self, adapter: SnowflakeAdapter):
        await adapter.validate_config()  # should not raise

    @pytest.mark.asyncio
    async def test_missing_account_raises(self):
        a = SnowflakeAdapter(config={"user": "u"})
        with pytest.raises(AdapterError, match="missing required fields"):
            await a.validate_config()

    @pytest.mark.asyncio
    async def test_missing_user_raises(self):
        a = SnowflakeAdapter(config={"account": "acc"})
        with pytest.raises(AdapterError, match="missing required fields"):
            await a.validate_config()


class TestActions:
    @pytest.mark.asyncio
    async def test_test_connection(self, adapter: SnowflakeAdapter):
        result = await adapter.execute("test_connection", {})
        assert result["connected"] is True
        assert result["account"] == "test_account"

    @pytest.mark.asyncio
    async def test_run_query(self, adapter: SnowflakeAdapter):
        result = await adapter.execute("run_query", {"query": "SELECT 1"})
        assert result["status"] == "executed"
        assert result["query"] == "SELECT 1"

    @pytest.mark.asyncio
    async def test_run_query_missing_query(self, adapter: SnowflakeAdapter):
        with pytest.raises(AdapterError, match="requires a 'query'"):
            await adapter.execute("run_query", {})

    @pytest.mark.asyncio
    async def test_list_databases(self, adapter: SnowflakeAdapter):
        result = await adapter.execute("list_databases", {})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_list_roles(self, adapter: SnowflakeAdapter):
        result = await adapter.execute("list_roles", {})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_describe_schema(self, adapter: SnowflakeAdapter):
        result = await adapter.execute(
            "describe_schema", {"database": "ANALYTICS", "schema": "PUBLIC"}
        )
        assert result["database"] == "ANALYTICS"

    @pytest.mark.asyncio
    async def test_get_warehouse_usage(self, adapter: SnowflakeAdapter):
        result = await adapter.execute("get_warehouse_usage", {})
        assert "credits_used" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self, adapter: SnowflakeAdapter):
        with pytest.raises(AdapterError, match="Unknown Snowflake action"):
            await adapter.execute("nonexistent", {})


class TestMutationsRequireApproval:
    @pytest.mark.asyncio
    async def test_create_user_without_approval_fails(self, adapter: SnowflakeAdapter):
        with pytest.raises(AdapterError, match="requires approval context"):
            await adapter.execute("create_user", {"username": "new"})

    @pytest.mark.asyncio
    async def test_create_user_with_approval_succeeds(self, adapter: SnowflakeAdapter):
        result = await adapter.execute(
            "create_user", {"username": "new", "approval_id": "appr_01"}
        )
        assert result["created"] is True

    @pytest.mark.asyncio
    async def test_grant_role_without_approval_fails(self, adapter: SnowflakeAdapter):
        with pytest.raises(AdapterError, match="requires approval context"):
            await adapter.execute("grant_role", {"role": "R", "username": "u"})

    @pytest.mark.asyncio
    async def test_grant_role_with_approval_succeeds(self, adapter: SnowflakeAdapter):
        result = await adapter.execute(
            "grant_role",
            {"role": "ANALYST", "username": "u", "approval_id": "appr_01"},
        )
        assert result["granted"] is True

    @pytest.mark.asyncio
    async def test_revoke_role_without_approval_fails(self, adapter: SnowflakeAdapter):
        with pytest.raises(AdapterError, match="requires approval context"):
            await adapter.execute("revoke_role", {"role": "R", "username": "u"})


class TestAuditEmission:
    @pytest.mark.asyncio
    async def test_mutation_emits_audit(
        self, adapter_with_audit: tuple[SnowflakeAdapter, AuditWriter]
    ):
        a, writer = adapter_with_audit
        await a.execute(
            "create_user", {"username": "new", "approval_id": "appr_01"}
        )
        assert len(writer.records) == 1
        assert "snowflake.create_user" in writer.records[0].event_name

    @pytest.mark.asyncio
    async def test_read_emits_audit(
        self, adapter_with_audit: tuple[SnowflakeAdapter, AuditWriter]
    ):
        a, writer = adapter_with_audit
        await a.execute("list_databases", {})
        assert len(writer.records) == 1
