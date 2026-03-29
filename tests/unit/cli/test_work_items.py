"""Tests for CLI work-items commands."""

from __future__ import annotations

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


class TestWorkItemCreate:
    def test_create_with_all_options(self) -> None:
        result = runner.invoke(
            app,
            ["work-items", "create", "--title", "Test item", "--description", "A test", "--priority", "high"],
        )
        assert result.exit_code == 0
        assert "Test item" in result.output
        assert "high" in result.output

    def test_create_requires_title(self) -> None:
        result = runner.invoke(app, ["work-items", "create"])
        assert result.exit_code != 0


class TestWorkItemList:
    def test_list_placeholder(self) -> None:
        result = runner.invoke(app, ["work-items", "list"])
        assert result.exit_code == 0
        assert "placeholder" in result.output.lower() or "not yet" in result.output.lower()

    def test_list_with_state_filter(self) -> None:
        result = runner.invoke(app, ["work-items", "list", "--state", "TRIAGE"])
        assert result.exit_code == 0
        assert "TRIAGE" in result.output


class TestWorkItemShow:
    def test_show_placeholder(self) -> None:
        result = runner.invoke(app, ["work-items", "show", "wi-123"])
        assert result.exit_code == 0
        assert "wi-123" in result.output
