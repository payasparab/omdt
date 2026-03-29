"""Artifact service — register, retrieve, and list artifacts.

Computes SHA-256 hash of content and emits events.
"""
from __future__ import annotations

import hashlib

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import ArtifactType
from app.domain.models.artifact import Artifact

# In-memory store.
_store: dict[str, Artifact] = {}


def get_store() -> dict[str, Artifact]:
    return _store


def clear_store() -> None:
    _store.clear()


def compute_sha256(content: str | bytes) -> str:
    """Compute SHA-256 hash of content."""
    if isinstance(content, str):
        content = content.encode()
    return hashlib.sha256(content).hexdigest()


async def register_artifact(
    *,
    artifact_type: ArtifactType,
    version: str,
    storage_uri: str,
    content: str | bytes = b"",
    linked_object_type: str | None = None,
    linked_object_id: str | None = None,
    created_by: str = "system",
) -> Artifact:
    """Register a new artifact."""
    sha = compute_sha256(content) if content else ("0" * 64)
    artifact = Artifact(
        artifact_type=artifact_type,
        version=version,
        storage_uri=storage_uri,
        hash_sha256=sha,
        linked_object_type=linked_object_type,
        linked_object_id=linked_object_id,
        created_by=created_by,
    )
    _store[artifact.id] = artifact
    corr_id = generate_correlation_id()

    await emit(
        "artifact.created",
        {
            "artifact_id": artifact.id,
            "artifact_type": artifact_type.value,
            "version": version,
            "linked_object_type": linked_object_type,
            "linked_object_id": linked_object_id,
            "correlation_id": corr_id,
        },
    )

    record_audit_event(
        event_name="artifact.created",
        actor_type="system",
        actor_id=created_by,
        object_type="artifact",
        object_id=artifact.id,
        change_summary=f"Artifact registered: {artifact_type.value} v{version} at {storage_uri}",
        correlation_id=corr_id,
    )

    return artifact


async def get_artifact(artifact_id: str) -> Artifact | None:
    """Get an artifact by ID."""
    return _store.get(artifact_id)


async def list_artifacts(
    *,
    artifact_type: ArtifactType | None = None,
    linked_object_id: str | None = None,
) -> list[Artifact]:
    """List artifacts with optional filters."""
    results = list(_store.values())
    if artifact_type is not None:
        results = [a for a in results if a.artifact_type == artifact_type]
    if linked_object_id is not None:
        results = [a for a in results if a.linked_object_id == linked_object_id]
    return results
