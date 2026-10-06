"""Development CLI for scenario inspection, generation and validation."""

from pathlib import Path
from typing import Annotated

import typer

from ancienttdde.audit import inspect_evidence, run_audit
from ancienttdde.engine.build import build_game, validate_game
from ancienttdde.generation.build import build_map, validate_build
from ancienttdde.probes.build import build_probes, validate_probes
from ancienttdde.probes.models import Outcome, ProbeId
from ancienttdde.probes.results import record_result
from ancienttdde.probes.serialization import read_object
from ancienttdde.validation import (
    validate_inputs,
    validate_inventory,
    validate_references,
    validate_report,
)

app = typer.Typer(help="Ancient TD DE inspection and scenario development.", no_args_is_help=True)
Root = Annotated[Path, typer.Option(help="Project root containing source and content definitions.")]
probe_app = typer.Typer(help="Generate solo mechanic scenarios or record observed results.")
app.add_typer(probe_app, name="probe")


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
        Path | None, typer.Option(help="Generated game or map build directory to check.")
    ] = None,
    probes: Annotated[
        Path | None, typer.Option(help="Generated mechanic probe directory to check.")
    ] = None,
) -> None:
    """Check current content, source provenance, and optionally an audit report."""
    try:
        root = root.resolve()
        if sum(path is not None for path in (report, build, probes)) > 1:
            raise ValueError("Choose one of --report, --build or --probes")
        if probes:
            validate_probes(probes.resolve(), root)
        elif build:
            if read_object(build / "manifest.json").get("kind") == "ancient-td-game":
                validate_game(build, root)
            else:
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
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Validation failed: {error}", err=True)
        raise typer.Exit(1) from error
    if probes:
        typer.echo(
            "Probe artifacts, native references, current definitions and embedded XS validated. "
            "Observed in-game results are recorded separately."
        )
        return
    if build:
        typer.echo(
            "Map/game artifacts, current definitions and build hashes validated. "
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
    output: Annotated[Path | None, typer.Option(help="Generated scenario directory.")] = None,
    map_only: Annotated[
        bool, typer.Option(help="Build the map template without gameplay.")
    ] = False,
) -> None:
    """Generate a playable stock-DE game and a repeatable build manifest."""
    try:
        if map_only:
            build_map(root, output)
        else:
            build_game(root, output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Build failed: {error}", err=True)
        raise typer.Exit(1) from error
    destination = (
        (output or root / ".build/map") / "ancient-td-de-map.aoe2scenario"
        if map_only
        else (output or root / ".build/game") / "ancient-td-de.aoe2scenario"
    )
    typer.echo(f"{'Map foundation' if map_only else 'Playable game'} built: {destination}")
    typer.echo("In-game verification remains pending.")


@probe_app.callback(invoke_without_command=True)
def probe(
    ctx: typer.Context,
    root: Root = Path("."),
    output: Annotated[Path | None, typer.Option(help="Generated probe suite directory.")] = None,
    only: Annotated[
        list[ProbeId] | None, typer.Option(help="Generate only these probes; repeatable.")
    ] = None,
) -> None:
    """Generate self-contained scenarios, instructions and an observation ledger."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        manifest = build_probes(root, output, only=[p.value for p in only] if only else None)
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Probe generation failed: {error}", err=True)
        raise typer.Exit(1) from error
    destination = output or root / ".build/probes"
    typer.echo(f"Built {len(manifest['probes'])} solo mechanic scenarios: {destination}")
    typer.echo("In-game results are pending. Test instructions and results.json are included.")


@probe_app.command("record")
def record_probe(
    suite: Annotated[Path, typer.Option(help="Generated probe suite directory.")],
    case: Annotated[str, typer.Option(help="Case ID from the generated instructions.")],
    status: Annotated[Outcome, typer.Option(help="Observed result.")],
    game_build: Annotated[str, typer.Option(help="Tested DE game build.")],
    tester: Annotated[str, typer.Option(help="Person who performed the test.")],
    notes: Annotated[str, typer.Option(help="Observed behavior and evidence.")],
) -> None:
    """Append an attributed observation tied to the inspected scenario content."""
    try:
        record_result(
            suite.resolve(), case, status.value, game_build=game_build, tester=tester, notes=notes
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"Recording failed: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Recorded {status.value}: {case}. Results: {suite / 'results.json'}")
