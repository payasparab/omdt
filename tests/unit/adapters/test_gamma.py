"""Unit tests for the Gamma adapter — job lifecycle polling."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.gamma import GammaAdapter
from app.adapters.base import AdapterError
from tests.fixtures.gamma_responses import (
    VALID_CONFIG,
    SUBMIT_JOB_RESPONSE,
    POLL_JOB_PENDING_RESPONSE,
    POLL_JOB_COMPLETE_RESPONSE,
    RETRIEVE_OUTPUT_RESPONSE,
)


@pytest.fixture
def adapter() -> GammaAdapter:
    return GammaAdapter(config=VALID_CONFIG.copy())


def _mock_api(response: dict[str, Any]):
    return patch.object(
        GammaAdapter, "_api_request", new_callable=AsyncMock, return_value=response
    )


class TestValidateConfig:
    @pytest.mark.asyncio
    async def test_valid(self, adapter: GammaAdapter):
        await adapter.validate_config()

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        a = GammaAdapter(config={})
        with pytest.raises(AdapterError, match="api_key"):
            await a.validate_config()


class TestJobLifecycle:
    @pytest.mark.asyncio
    async def test_submit_job(self, adapter: GammaAdapter):
        with _mock_api(SUBMIT_JOB_RESPONSE):
            result = await adapter.execute(
                "submit_generation_job",
                {"template": "briefing", "content": {"title": "Q1 Review"}},
            )
            assert result["job_id"] == "job_01"
            assert result["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_submit_job_missing_template(self, adapter: GammaAdapter):
        with pytest.raises(AdapterError, match="template"):
            await adapter.execute("submit_generation_job", {})

    @pytest.mark.asyncio
    async def test_poll_pending(self, adapter: GammaAdapter):
        with _mock_api(POLL_JOB_PENDING_RESPONSE):
            result = await adapter.execute(
                "poll_job_status", {"job_id": "job_01"}
            )
            assert result["status"] == "processing"
            assert result["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_poll_complete(self, adapter: GammaAdapter):
        with _mock_api(POLL_JOB_COMPLETE_RESPONSE):
            result = await adapter.execute(
                "poll_job_status", {"job_id": "job_01"}
            )
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_poll_missing_job_id(self, adapter: GammaAdapter):
        with pytest.raises(AdapterError, match="job_id"):
            await adapter.execute("poll_job_status", {})

    @pytest.mark.asyncio
    async def test_retrieve_output(self, adapter: GammaAdapter):
        with _mock_api(RETRIEVE_OUTPUT_RESPONSE):
            result = await adapter.execute(
                "retrieve_output", {"job_id": "job_01"}
            )
            assert result["output_url"] == "https://gamma.app/output/job_01.pdf"
            assert result["format"] == "pdf"

    @pytest.mark.asyncio
    async def test_retrieve_missing_job_id(self, adapter: GammaAdapter):
        with pytest.raises(AdapterError, match="job_id"):
            await adapter.execute("retrieve_output", {})


class TestRegisterArtifact:
    @pytest.mark.asyncio
    async def test_register(self, adapter: GammaAdapter):
        result = await adapter.execute(
            "register_artifact",
            {"job_id": "job_01", "output_url": "https://gamma.app/out.pdf"},
        )
        assert result["registered"] is True
