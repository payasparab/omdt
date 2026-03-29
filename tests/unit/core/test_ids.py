"""Tests for app.core.ids — ID generation and correlation context."""

from __future__ import annotations

import uuid

from app.core.ids import (
    generate_audit_id,
    generate_correlation_id,
    generate_id,
    generate_request_id,
    get_current_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)


class TestGenerateId:
    def test_returns_valid_uuid4(self) -> None:
        result = generate_id()
        parsed = uuid.UUID(result, version=4)
        assert str(parsed) == result

    def test_ids_are_unique(self) -> None:
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateCorrelationId:
    def test_has_corr_prefix(self) -> None:
        cid = generate_correlation_id()
        assert cid.startswith("corr-")

    def test_suffix_is_uuid(self) -> None:
        cid = generate_correlation_id()
        uuid.UUID(cid.removeprefix("corr-"), version=4)


class TestGenerateAuditId:
    def test_has_aud_prefix(self) -> None:
        aid = generate_audit_id()
        assert aid.startswith("aud-")

    def test_suffix_is_uuid(self) -> None:
        aid = generate_audit_id()
        uuid.UUID(aid.removeprefix("aud-"), version=4)


class TestGenerateRequestId:
    def test_has_req_prefix(self) -> None:
        rid = generate_request_id()
        assert rid.startswith("req-")


class TestCorrelationIdContext:
    def test_default_is_none(self) -> None:
        reset_correlation_id()
        assert get_current_correlation_id() is None

    def test_set_and_get(self) -> None:
        set_correlation_id("corr-test-123")
        assert get_current_correlation_id() == "corr-test-123"
        reset_correlation_id()

    def test_reset_clears(self) -> None:
        set_correlation_id("corr-abc")
        reset_correlation_id()
        assert get_current_correlation_id() is None
