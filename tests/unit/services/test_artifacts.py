"""Tests for the artifact service."""

import hashlib

import pytest

from app.core.audit import clear_audit_log, get_audit_log
from app.core.events import clear_handlers, subscribe
from app.domain.enums import ArtifactType
from app.services import artifacts as artifact_service


@pytest.fixture(autouse=True)
def _clean():
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()
    yield
    artifact_service.clear_store()
    clear_audit_log()
    clear_handlers()


class TestComputeSHA256:
    def test_string_content(self):
        result = artifact_service.compute_sha256("hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert result == expected

    def test_bytes_content(self):
        result = artifact_service.compute_sha256(b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert result == expected


class TestRegisterArtifact:
    @pytest.mark.asyncio
    async def test_registers_artifact(self):
        art = await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD,
            version="1.0",
            storage_uri="s3://bucket/prd.md",
            content="PRD content",
            linked_object_type="work_item",
            linked_object_id="wi-1",
            created_by="payas",
        )
        assert art.artifact_type == ArtifactType.PRD
        assert art.version == "1.0"
        assert art.hash_sha256 == hashlib.sha256(b"PRD content").hexdigest()

    @pytest.mark.asyncio
    async def test_emits_event(self):
        events = []
        async def handler(e): events.append(e)
        subscribe("artifact.created", handler)

        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD,
            version="1.0",
            storage_uri="s3://bucket/prd.md",
        )
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_creates_audit_record(self):
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD,
            version="1.0",
            storage_uri="s3://bucket/prd.md",
        )
        assert any(r["event_name"] == "artifact.created" for r in get_audit_log())


class TestGetArtifact:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        art = await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD,
            version="1.0",
            storage_uri="s3://bucket/prd.md",
        )
        found = await artifact_service.get_artifact(art.id)
        assert found is not None
        assert found.id == art.id

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        assert await artifact_service.get_artifact("nope") is None


class TestListArtifacts:
    @pytest.mark.asyncio
    async def test_list_all(self):
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD, version="1.0", storage_uri="a",
        )
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.DBML, version="1.0", storage_uri="b",
        )
        all_arts = await artifact_service.list_artifacts()
        assert len(all_arts) == 2

    @pytest.mark.asyncio
    async def test_filter_by_type(self):
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD, version="1.0", storage_uri="a",
        )
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.DBML, version="1.0", storage_uri="b",
        )
        prds = await artifact_service.list_artifacts(artifact_type=ArtifactType.PRD)
        assert len(prds) == 1

    @pytest.mark.asyncio
    async def test_filter_by_linked_object(self):
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD, version="1.0", storage_uri="a",
            linked_object_id="wi-1",
        )
        await artifact_service.register_artifact(
            artifact_type=ArtifactType.PRD, version="1.0", storage_uri="b",
            linked_object_id="wi-2",
        )
        arts = await artifact_service.list_artifacts(linked_object_id="wi-1")
        assert len(arts) == 1
