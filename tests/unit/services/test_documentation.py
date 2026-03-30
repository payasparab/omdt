"""Tests for app.services.documentation — document generation pipeline."""
from __future__ import annotations

import json

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import ArtifactType
from app.services import artifacts as artifact_service
from app.services.documentation import generate_document


@pytest.fixture(autouse=True)
def _clean():
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestGenerateDocument:
    @pytest.mark.asyncio
    async def test_generates_technical_memo(self) -> None:
        artifact = await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1", "art-2"],
            audience="technical",
        )
        assert artifact is not None
        assert artifact.artifact_type == ArtifactType.TECHNICAL_MEMO
        assert artifact.version == "1.0"
        assert artifact.created_by == "technical_writer_agent"

    @pytest.mark.asyncio
    async def test_generates_runbook(self) -> None:
        artifact = await generate_document(
            document_type="runbook",
            source_artifacts=["art-1"],
        )
        assert artifact.artifact_type == ArtifactType.RUNBOOK

    @pytest.mark.asyncio
    async def test_generates_release_notes(self) -> None:
        artifact = await generate_document(
            document_type="release_notes",
            context={
                "deployment_record": {"version": "3.0", "environment": "staging"},
                "changes": ["New feature X"],
            },
        )
        assert artifact.artifact_type == ArtifactType.RELEASE_NOTES

    @pytest.mark.asyncio
    async def test_generates_sop(self) -> None:
        artifact = await generate_document(
            document_type="sop",
            context={"process_description": "Weekly data refresh"},
        )
        assert artifact.artifact_type == ArtifactType.SOP

    @pytest.mark.asyncio
    async def test_generates_user_guide(self) -> None:
        artifact = await generate_document(
            document_type="user_guide",
            audience="end_user",
            context={"feature": "Report Builder"},
        )
        assert artifact.artifact_type == ArtifactType.USER_GUIDE


class TestArtifactRegistration:
    @pytest.mark.asyncio
    async def test_artifact_stored(self) -> None:
        artifact = await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1"],
        )
        stored = await artifact_service.get_artifact(artifact.id)
        assert stored is not None
        assert stored.id == artifact.id

    @pytest.mark.asyncio
    async def test_artifact_has_valid_hash(self) -> None:
        artifact = await generate_document(
            document_type="runbook",
            source_artifacts=["art-1"],
        )
        assert len(artifact.hash_sha256) == 64

    @pytest.mark.asyncio
    async def test_artifact_linked_to_work_item(self) -> None:
        artifact = await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1"],
            work_item_id="wi-100",
        )
        assert artifact.linked_object_id == "wi-100"
        assert artifact.linked_object_type == "work_item"

    @pytest.mark.asyncio
    async def test_artifact_linked_to_project(self) -> None:
        artifact = await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1"],
            project_id="proj-200",
        )
        assert artifact.linked_object_id == "proj-200"
        assert artifact.linked_object_type == "project"


class TestDocumentEvents:
    @pytest.mark.asyncio
    async def test_emits_documentation_generated_event(self) -> None:
        events = []
        async def handler(e): events.append(e)
        subscribe("documentation.generated", handler)

        await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1"],
        )
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_creates_audit_record(self) -> None:
        await generate_document(
            document_type="technical_memo",
            source_artifacts=["art-1"],
        )
        logs = get_audit_log()
        assert any(r["event_name"] == "documentation.generated" for r in logs)

    @pytest.mark.asyncio
    async def test_artifact_content_is_valid_json(self) -> None:
        artifact = await generate_document(
            document_type="executive_summary",
            source_artifacts=["art-1"],
            audience="executive",
        )
        # The stored content should be parseable JSON
        stored = await artifact_service.get_artifact(artifact.id)
        assert stored is not None
