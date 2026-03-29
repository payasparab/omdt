"""Tests for CLI bootstrap commands."""

from __future__ import annotations

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


class TestBootstrapInit:
    def test_runs_without_error(self) -> None:
        result = runner.invoke(app, ["bootstrap", "init"])
        assert result.exit_code == 0
        assert "Welcome to OMDT" in result.output

    def test_shows_config_status(self) -> None:
        result = runner.invoke(app, ["bootstrap", "init"])
        assert result.exit_code == 0
        # Should mention either config files or missing directory
        assert "config" in result.output.lower()


class TestBootstrapCheckConfig:
    def test_runs_without_crash(self) -> None:
        result = runner.invoke(app, ["bootstrap", "check-config"])
        # exit_code 0 or 1 depending on whether config/ exists — both are valid
        assert result.exit_code in (0, 1)


class TestBootstrapSnowflake:
    def test_prompts_for_inputs(self) -> None:
        # Provide all prompted values via stdin
        inputs = "my_account\nmy_user\nCOMPUTE_WH\nOMDT\nOMDT_ROLE\n"
        result = runner.invoke(app, ["bootstrap", "snowflake"], input=inputs)
        assert result.exit_code == 0
        assert "my_account" in result.output
        assert "Connection summary" in result.output
