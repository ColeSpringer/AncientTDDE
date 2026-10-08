"""Development CLI for scenario inspection, generation and validation."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from ancienttdde.audit.run import inspect_evidence, run_audit
from ancienttdde.audit.validation import (
    read_audit_manifest,
    validate_inputs,
    validate_inventory,
    validate_report,
)
from ancienttdde.common.manifest import read_kind
from ancienttdde.common.output import resolve_output
from ancienttdde.game.balance import Assumptions, load_inputs
from ancienttdde.game.build import SCENARIO_NAME as GAME_SCENARIO
from ancienttdde.game.build import build_game, validate_game
from ancienttdde.game.report import REPORT_TITLE, render_report
from ancienttdde.map.build import SCENARIO_NAME as MAP_SCENARIO
from ancienttdde.map.build import build_map, validate_map_build
from ancienttdde.probes.build import build_probes, validate_probes
from ancienttdde.probes.catalog import select_probes
from ancienttdde.probes.models import Outcome, ProbeId
from ancienttdde.probes.results import record_result
from ancienttdde.scenario.snapshot import validate_references

app = typer.Typer(help="Ancient TD DE inspection and scenario development.", no_args_is_help=True)
Root = Annotated[Path, typer.Option(help="Project root containing source and content definitions.")]
probe_app = typer.Typer(help="Generate solo mechanic scenarios or record observed results.")
app.add_typer(probe_app, name="probe")


@contextmanager
def reported(action: str) -> Generator[None]:
    """Report expected failures as one line and exit status 1.

    Unchecked casts at JSON boundaries and table lookups still raise KeyError or TypeError
    on malformed input, so those are reported like validation errors.
    """
    try:
        yield
    except (OSError, ValueError, KeyError, TypeError) as error:
        typer.echo(f"{action} failed: {error}", err=True)
        raise typer.Exit(1) from error


@app.command()
def audit(
    root: Root = Path("."),
    output: Annotated[Path | None, typer.Option(help="Generated report directory.")] = None,
) -> None:
    """Inventory original behavior and DAT dependencies; generate JSON and Markdown."""
    with reported("Audit"):
        directory = run_audit(root, output)
        summary = read_audit_manifest(directory / "manifest.json")["summary"]
    typer.echo(
        f"Audit: {summary['triggers']} triggers, {summary['waves']} waves, "
        f"{summary['purchase_triggers']} purchase triggers. Reports: {directory}"
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
    with reported("Validation"):
        root = root.resolve()
        if sum(path is not None for path in (report, build, probes)) > 1:
            raise ValueError("Choose one of --report, --build or --probes")
        if probes:
            validate_probes(probes.resolve(), root)
        elif build:
            if read_kind(build / "manifest.json") == "ancient-td-game":
                validate_game(build, root)
            else:
                validate_map_build(build, root)
        elif report:
            validate_report(report, root)
        else:
            config, classification, mappings = validate_inputs(root)
            scenario, dat = inspect_evidence(root, config)
            validate_inventory(classification, mappings, scenario, dat)
            dangling = validate_references(scenario)
            if dangling:
                raise ValueError(f"Dangling scenario references: {dangling}")
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
    with reported("Build"):
        directory = build_map(root, output) if map_only else build_game(root, output)
    destination = directory / (MAP_SCENARIO if map_only else GAME_SCENARIO)
    typer.echo(f"{'Map foundation' if map_only else 'Playable game'} built: {destination}")
    typer.echo("In-game verification remains pending.")


@app.command()
def balance(
    root: Root = Path("."),
    output: Annotated[Path | None, typer.Option(help="Report directory.")] = None,
) -> None:
    """Write the balance tables from the content and the stock data snapshot."""
    with reported("Balance"):
        directory = resolve_output(root, output, ".build/balance")
        report = directory / "balance.md"
        if report.is_symlink() or (
            report.exists()
            and (
                not report.is_file()
                or not report.read_text(encoding="utf-8").startswith(REPORT_TITLE)
            )
        ):
            raise ValueError("Output cannot overwrite unrelated artifacts; choose another output")
        text = render_report(load_inputs(root.resolve()), Assumptions())
        directory.mkdir(parents=True, exist_ok=True)
        staged = report.with_name("balance.md.part")
        staged.write_text(text, encoding="utf-8")
        staged.replace(report)
    typer.echo(f"Balance tables written: {report}")


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
    selection = [p.value for p in only] if only else None
    with reported("Probe generation"):
        destination = build_probes(root, output, only=selection)
    typer.echo(f"Built {len(select_probes(selection))} solo mechanic scenarios: {destination}")
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
    with reported("Recording"):
        record_result(
            suite.resolve(), case, status.value, game_build=game_build, tester=tester, notes=notes
        )
    typer.echo(f"Recorded {status.value}: {case}. Results: {suite / 'results.json'}")
