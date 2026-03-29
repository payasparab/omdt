"""Bootstrap CLI commands — init, check-config, snowflake setup."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True)

_CONFIG_DIR = Path("config")
_REQUIRED_CONFIGS = [
    "omdt.yaml",
    "people.yaml",
    "linear.schema.yaml",
    "notifications.yaml",
    "approvals.yaml",
    "role_bundles.yaml",
    "prompts.yaml",
    "testing.yaml",
]


@app.command()
def init() -> None:
    """Initialise OMDT — welcome message, validate config presence."""
    typer.echo("Welcome to OMDT — One Man Data Team!")
    typer.echo()

    if not _CONFIG_DIR.exists():
        typer.echo(f"[warn] Config directory '{_CONFIG_DIR}' not found.")
        typer.echo("Run 'omdt bootstrap check-config' after creating your config files.")
        raise typer.Exit(code=0)

    missing: list[str] = []
    for name in _REQUIRED_CONFIGS:
        path = _CONFIG_DIR / name
        if path.exists():
            typer.echo(f"  [ok]   {name}")
        else:
            typer.echo(f"  [miss] {name}")
            missing.append(name)

    if missing:
        typer.echo(f"\n{len(missing)} config file(s) missing — create them before proceeding.")
    else:
        typer.echo("\nAll config files present. Run 'omdt bootstrap check-config' to validate.")


@app.command("check-config")
def check_config() -> None:
    """Load and validate all YAML config files against their schemas."""
    # TODO (Wave 2): call config loader / validator from app.core.config
    typer.echo("Checking configuration files …")

    if not _CONFIG_DIR.exists():
        typer.secho(f"Config directory '{_CONFIG_DIR}' does not exist.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    for name in _REQUIRED_CONFIGS:
        path = _CONFIG_DIR / name
        if path.exists():
            # TODO (Wave 2): actually parse and validate against Pydantic schema
            typer.echo(f"  [ok]   {name}  (exists, schema validation pending)")
        else:
            typer.secho(f"  [miss] {name}", fg=typer.colors.YELLOW)

    typer.echo("\nSchema validation not yet implemented — pending config chat delivery.")


@app.command()
def snowflake() -> None:
    """Interactive Snowflake connection setup."""
    typer.echo("Snowflake connection setup")
    typer.echo("-" * 40)

    account = typer.prompt("Snowflake account identifier")
    username = typer.prompt("Username")
    warehouse = typer.prompt("Warehouse", default="COMPUTE_WH")
    database = typer.prompt("Database", default="OMDT")
    role = typer.prompt("Role", default="OMDT_ROLE")

    typer.echo()
    typer.echo("Connection summary:")
    typer.echo(f"  Account   : {account}")
    typer.echo(f"  Username  : {username}")
    typer.echo(f"  Warehouse : {warehouse}")
    typer.echo(f"  Database  : {database}")
    typer.echo(f"  Role      : {role}")

    # TODO (Wave 2): test connection using snowflake-connector-python,
    # persist credentials to secrets manager / .env
    typer.echo("\n[placeholder] Connection test not yet implemented.")
    typer.echo("Save these values to config/omdt.yaml under the snowflake section.")
