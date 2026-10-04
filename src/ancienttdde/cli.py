"""Development CLI for scenario inspection, generation and validation."""

from pathlib import Path
from typing import Annotated

import typer

from ancienttdde.audit import inspect_evidence, run_audit
from ancienttdde.generation.build import build_map, validate_build
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
    build: Annotated[
        Path | None, typer.Option(help="Generated map build directory to check.")
    ] = None,
) -> None:
    """Check current content, source provenance, and optionally an audit report."""
    try:
        root = root.resolve()
        if report and build:
            raise ValueError("Choose either --report or --build")
        if build:
            validate_build(build, root)
        elif report:
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
    if build:
        typer.echo(
            "Map terrain, stock identities, anchors, routes and build hashes validated. "
            "In-game verification remains pending."
        )
        return
    typer.echo(
        "Content coverage, source provenance and references validated."
        + (" Audit artifacts and current input hashes validated." if report else "")
    )


@app.command()
def build(
    root: Root = Path("."),
    output: Annotated[Path | None, typer.Option(help="Generated map build directory.")] = None,
) -> None:
    """Generate the stock-DE map foundation and a repeatable build manifest."""
    try:
        result = build_map(root, output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Build failed: {error}", err=True)
        raise typer.Exit(1) from error
    destination = (output or root / ".build/map") / "ancient-td-de-map.aoe2scenario"
    typer.echo(f"Map foundation built: {destination}")
    typer.echo(
        f"Checked {len(result['validation']['routes'])} routes. "
        "In-game verification remains pending."
    )


@app.command()
def probe() -> None:
    """Generate focused in-game probe scenarios."""
    typer.echo("In-game probe generation is not implemented.", err=True)
    raise typer.Exit(2)
