"""Tests for WorkItem domain model."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import CanonicalState, Priority, SourceChannel, WorkItemType
from app.domain.models.work_item import WorkItem


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestWorkItemCreation:
    def test_minimal_valid(self) -> None:
        wi = WorkItem(
            id=uuid4(),
            title="Build dashboard",
            work_type=WorkItemType.DASHBOARD_REQUEST,
            created_at=_now(),
            updated_at=_now(),
        )
        assert wi.canonical_state == CanonicalState.NEW
        assert wi.priority == Priority.MEDIUM
        assert wi.requires_approval is False

    def test_all_fields(self) -> None:
        now = _now()
        wi = WorkItem(
            id=uuid4(),
            project_id=uuid4(),
            title="Pipeline fix",
            description="Fix the nightly ETL",
            work_type=WorkItemType.PIPELINE_REQUEST,
            canonical_state=CanonicalState.IN_PROGRESS,
            priority=Priority.HIGH,
            source_channel=SourceChannel.OUTLOOK,
            source_external_id="MSG-123",
            requester_person_key="alice",
            owner_person_key="bob",
            route_key="engineer",
            risk_level="high",
            due_at=now,
            requires_approval=True,
            latest_prd_revision_id=uuid4(),
            linear_issue_id="LIN-42",
            created_at=now,
            updated_at=now,
            closed_at=None,
        )
        assert wi.canonical_state == CanonicalState.IN_PROGRESS
        assert wi.source_channel == SourceChannel.OUTLOOK

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            WorkItem(
                id=uuid4(),
                title="",
                work_type=WorkItemType.ANALYSIS_REQUEST,
                created_at=_now(),
                updated_at=_now(),
            )

    def test_invalid_work_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkItem(
                id=uuid4(),
                title="Bad type",
                work_type="not_a_real_type",  # type: ignore[arg-type]
                created_at=_now(),
                updated_at=_now(),
            )
