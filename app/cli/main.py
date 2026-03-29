"""OMDT CLI — Typer application root."""

from __future__ import annotations

import typer

from app.cli.access import app as access_app
from app.cli.bootstrap import app as bootstrap_app
from app.cli.config_check import app as config_app
from app.cli.work_items import app as work_items_app

app = typer.Typer(
    name="omdt",
    help="OMDT — One Man Data Team CLI",
    no_args_is_help=True,
)

app.add_typer(bootstrap_app, name="bootstrap", help="Bootstrap and setup commands")
app.add_typer(work_items_app, name="work-items", help="Manage work items")
app.add_typer(config_app, name="config", help="Configuration management")
app.add_typer(access_app, name="access", help="Access provisioning requests")


@app.callback()
def main() -> None:
    """OMDT — One Man Data Team CLI.

    A Python-first operating framework that behaves like an in-house data team.
    """
