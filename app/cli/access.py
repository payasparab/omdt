"""Access provisioning CLI commands."""

from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def request(
    role_bundle: str = typer.Option(..., help="Role bundle to request (e.g. analyst_read)"),
    requester: str = typer.Option(..., help="Person key of the requester"),
    reason: Optional[str] = typer.Option(None, help="Business justification"),
) -> None:
    """Create an access provisioning request."""
    # TODO (Wave 2): call access service to create approval-gated request
    typer.echo("Access request created (placeholder)")
    typer.echo(f"  Role bundle : {role_bundle}")
    typer.echo(f"  Requester   : {requester}")
    typer.echo(f"  Reason      : {reason or '(none)'}")
    typer.echo("\n[placeholder] Not yet connected to approval workflow.")


@app.command("list")
def list_requests(
    status: Optional[str] = typer.Option(None, help="Filter by status: pending, approved, denied"),
) -> None:
    """List pending access requests."""
    # TODO (Wave 2): query access requests from database
    typer.echo("[placeholder] Not yet connected to database.")
    if status:
        typer.echo(f"Would filter by status: {status}")
