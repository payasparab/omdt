"""Tests for Artifact domain model."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import ApprovalStatus, ArtifactType
from app.domain.models.artifact import Artifact


def _now() -> datetime:
    return datetime.now(timezone.utc)


VALID_SHA256 = "a" * 64


class TestArtifactCreation:
    def test_minimal_valid(self) -> None:
        a = Artifact(
            id=uuid4(),
            artifact_type=ArtifactType.PRD,
            storage_uri="s3://bucket/prd-v1.md",
            hash_sha256=VALID_SHA256,
            created_at=_now(),
        )
        assert a.approval_status == ApprovalStatus.PENDING
        assert a.published_at is None

    def test_hash_must_be_64_chars(self) -> None:
        with pytest.raises(ValidationError):
            Artifact(
                id=uuid4(),
                artifact_type=ArtifactType.PRD,
                storage_uri="s3://bucket/prd.md",
                hash_sha256="tooshort",
                created_at=_now(),
            )

    def test_hash_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Artifact(
                id=uuid4(),
                artifact_type=ArtifactType.PRD,
                storage_uri="s3://bucket/prd.md",
                hash_sha256="a" * 65,
                created_at=_now(),
            )

    def test_storage_uri_required(self) -> None:
        with pytest.raises(ValidationError):
            Artifact(
                id=uuid4(),
                artifact_type=ArtifactType.SQL_BUNDLE,
                storage_uri="",
                hash_sha256=VALID_SHA256,
                created_at=_now(),
            )
