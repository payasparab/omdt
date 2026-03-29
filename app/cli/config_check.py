"""Config CLI commands — validate and show configuration."""

from __future__ import annotations

import re
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True)

_CONFIG_DIR = Path("config")

# Patterns that likely contain secrets
_SECRET_PATTERNS = re.compile(
    r"(password|secret|token|api_key|private_key)", re.IGNORECASE
)


@app.command()
def validate() -> None:
    """Validate all config files against their Pydantic schemas."""
    # TODO (Wave 2): import config schemas and run validation
    typer.echo("Validating configuration files …")

    if not _CONFIG_DIR.exists():
        typer.secho(f"Config directory '{_CONFIG_DIR}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    yaml_files = sorted(_CONFIG_DIR.glob("*.yaml")) + sorted(_CONFIG_DIR.glob("*.yml"))
    if not yaml_files:
        typer.echo("No YAML files found in config/")
        raise typer.Exit(code=0)

    for path in yaml_files:
        # TODO (Wave 2): actually load and validate against Pydantic schema
        typer.echo(f"  [ok] {path.name}  (exists, schema validation pending)")

    typer.echo("\nFull schema validation not yet implemented — pending config chat delivery.")


@app.command()
def show() -> None:
    """Display current active configuration (secrets redacted)."""
    # TODO (Wave 2): load merged config and display
    typer.echo("Active configuration (secrets redacted):")
    typer.echo("-" * 40)

    if not _CONFIG_DIR.exists():
        typer.secho(f"Config directory '{_CONFIG_DIR}' not found.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    yaml_files = sorted(_CONFIG_DIR.glob("*.yaml")) + sorted(_CONFIG_DIR.glob("*.yml"))
    for path in yaml_files:
        typer.echo(f"\n--- {path.name} ---")
        try:
            content = path.read_text(encoding="utf-8")
            # Redact lines that look like secrets
            lines = content.splitlines()
            for line in lines:
                if _SECRET_PATTERNS.search(line) and ":" in line:
                    key = line.split(":")[0]
                    typer.echo(f"{key}: ****")
                else:
                    typer.echo(line)
        except Exception as exc:
            typer.secho(f"  Error reading {path.name}: {exc}", fg=typer.colors.RED)
