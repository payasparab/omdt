"""Integration test — DB lifecycle: create work item, transition state, verify audit."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestDBLifecycle:
    """Verify basic work-item lifecycle against a real (test) database.

    TODO (Wave 2): Replace placeholders once DB session fixtures and
    models are available.
    """

    def test_create_work_item(self) -> None:
        """Create a work item in the database and read it back."""
        pytest.skip("Requires database fixtures — placeholder for Wave 2")

    def test_transition_work_item_state(self) -> None:
        """Transition a work item through its state machine and verify."""
        pytest.skip("Requires database fixtures — placeholder for Wave 2")

    def test_audit_record_created_on_transition(self) -> None:
        """Verify that an audit record is written when state changes."""
        pytest.skip("Requires database fixtures — placeholder for Wave 2")
