"""Development CLI; unsupported milestones fail explicitly."""

from pathlib import Path
from typing import Annotated

import typer

from ancienttdde.audit import inspect_evidence, run_audit
from ancienttdde.validation import (
    validate_inputs,
    validate_inventory,
    validate_references,
    validate_report,
)

app = typer.Typer(help="Ancient TD DE inspection and scenario development.", no_args_is_help=True)
Root = Annotated[Path, typer.Option(help="Project root containing content/audit.toml.")]


@app.command()
def audit(
    root: Root = Path("."),
    output: Annotated[Path | None, typer.Option(help="Generated report directory.")] = None,
) -> None:
    """Inventory original behavior and DAT dependencies; generate JSON and Markdown."""
    try:
        result = run_audit(root, output)
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"Audit failed: {error}", err=True)
        raise typer.Exit(1) from error
    summary = result["summary"]
    destination = output or root / ".build/audit"
    typer.echo(
        f"Audit: {summary['triggers']} triggers, {summary['waves']} waves, "
        f"{summary['purchase_triggers']} purchase triggers. Reports: {destination}"
    )
    if summary["dangling_references"]:
        typer.echo("Legacy reference findings are recorded in behavior.json.")


@app.command()
def validate(
    root: Root = Path("."),
    report: Annotated[Path | None, typer.Option(help="Audit report to check as well.")] = None,
) -> None:
    """Check current content, source provenance, and optionally an audit report."""
    try:
        root = root.resolve()
        if report:
            validate_report(report, root)
        else:
            config, classification, mappings = validate_inputs(root)
            scenario, dat = inspect_evidence(root, config)
            validate_inventory(classification, mappings, scenario, dat)
            dangling = validate_references(scenario)
            if dangling:
                raise ValueError(f"Dangling scenario references: {dangling}")
    except (OSError, ValueError, KeyError) as error:
        typer.echo(f"Validation failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(
        "Content coverage, source provenance and references validated."
        + (" Audit artifacts and current input hashes validated." if report else "")
    )


@app.command()
def build() -> None:
    """Generate the playable scenario (starts with milestone 2)."""
    typer.echo("Scenario generation starts with milestone 2; use audit for milestone 1.", err=True)
    raise typer.Exit(2)


@app.command()
def probe() -> None:
    """Generate focused in-game probes (milestone 3)."""
    typer.echo("In-game probe generation is scheduled for milestone 3.", err=True)
    raise typer.Exit(2)
