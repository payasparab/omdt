"""Migration tests — verify Alembic migrations apply and roll back cleanly."""

from __future__ import annotations

import pytest


@pytest.mark.migration
class TestMigrations:
    """Ensure the migration chain is valid.

    TODO (Wave 2): Replace placeholders once Alembic env and a test
    database fixture are wired up.
    """

    def test_upgrade_head(self) -> None:
        """Running `alembic upgrade head` should succeed without errors."""
        pytest.skip("Requires Alembic env and test DB — placeholder for Wave 2")

    def test_downgrade_base(self) -> None:
        """Running `alembic downgrade base` should succeed without errors."""
        pytest.skip("Requires Alembic env and test DB — placeholder for Wave 2")

    def test_upgrade_downgrade_roundtrip(self) -> None:
        """Upgrade to head then downgrade to base — no residual state."""
        pytest.skip("Requires Alembic env and test DB — placeholder for Wave 2")
