"""Work-items CLI commands."""

from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def create(
    title: str = typer.Option(..., help="Work item title"),
    description: str = typer.Option("", help="Work item description"),
    priority: str = typer.Option("medium", help="Priority: low, medium, high, critical"),
) -> None:
    """Create a new work item from the CLI."""
    # TODO (Wave 2): call intake service or API to persist the work item
    typer.echo(f"Work item created (placeholder)")
    typer.echo(f"  Title       : {title}")
    typer.echo(f"  Description : {description or '(none)'}")
    typer.echo(f"  Priority    : {priority}")
    typer.echo("\n[placeholder] Not yet connected to database.")


@app.command("list")
def list_items(
    state: Optional[str] = typer.Option(None, help="Filter by canonical state"),
    limit: int = typer.Option(20, help="Max items to return"),
) -> None:
    """List work items."""
    # TODO (Wave 2): query database via work-items service
    typer.echo("[placeholder] Not yet connected to database.")
    typer.echo(f"Would list up to {limit} work items" + (f" in state '{state}'" if state else ""))


@app.command()
def show(
    work_item_id: str = typer.Argument(..., help="Work item ID to display"),
) -> None:
    """Show details of a single work item."""
    # TODO (Wave 2): fetch from database via work-items service
    typer.echo(f"[placeholder] Work item '{work_item_id}' — not yet connected to database.")
