"""Tests for app.services.training — training plan generation pipeline."""
from __future__ import annotations

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import ArtifactType
from app.services import artifacts as artifact_service
from app.services.training import generate_training_plan


@pytest.fixture(autouse=True)
def _clean():
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestGenerateTrainingPlan:
    @pytest.mark.asyncio
    async def test_generates_training_plan(self) -> None:
        artifact = await generate_training_plan(
            role="data_analyst",
            tool_scope=["snowflake", "looker"],
        )
        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.TRAINING_PLAN
        assert artifact.version == "1.0"
        assert artifact.created_by == "training_enablement_agent"

    @pytest.mark.asyncio
    async def test_generates_for_different_roles(self) -> None:
        for role in ["data_analyst", "data_engineer", "data_scientist", "business_user"]:
            artifact = await generate_training_plan(role=role)
            assert artifact.artifact_type == ArtifactType.TRAINING_PLAN


class TestTrainingArtifactRegistration:
    @pytest.mark.asyncio
    async def test_artifact_stored(self) -> None:
        artifact = await generate_training_plan(role="data_analyst")
        stored = await artifact_service.get_artifact(artifact.id)
        assert stored is not None
        assert stored.id == artifact.id

    @pytest.mark.asyncio
    async def test_artifact_has_valid_hash(self) -> None:
        artifact = await generate_training_plan(role="data_analyst")
        assert len(artifact.hash_sha256) == 64

    @pytest.mark.asyncio
    async def test_artifact_linked_to_work_item(self) -> None:
        artifact = await generate_training_plan(
            role="data_analyst",
            work_item_id="wi-300",
        )
        assert artifact.linked_object_id == "wi-300"
        assert artifact.linked_object_type == "work_item"

    @pytest.mark.asyncio
    async def test_artifact_linked_to_project(self) -> None:
        artifact = await generate_training_plan(
            role="data_analyst",
            project_id="proj-400",
        )
        assert artifact.linked_object_id == "proj-400"
        assert artifact.linked_object_type == "project"


class TestTrainingEvents:
    @pytest.mark.asyncio
    async def test_emits_training_plan_generated_event(self) -> None:
        events = []
        async def handler(e): events.append(e)
        subscribe("training.plan_generated", handler)

        await generate_training_plan(role="data_analyst")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_creates_audit_record(self) -> None:
        await generate_training_plan(role="data_analyst")
        logs = get_audit_log()
        assert any(r["event_name"] == "training.plan_generated" for r in logs)
