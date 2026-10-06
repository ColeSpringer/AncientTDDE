"""Generate, reload and validate reproducible solo mechanic experiments."""

from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from ancienttdde.common.data import HashRecord, read_object, rows, text_field, write_json
from ancienttdde.common.hashing import hash_inputs, hash_records, verify_hashes, verify_inputs
from ancienttdde.common.manifest import SCHEMA_VERSION, require_current_versions, versions
from ancienttdde.common.output import prepare_output, project_path, publish
from ancienttdde.common.worker import run_module, run_parallel
from ancienttdde.probes.catalog import instructions, select_probes
from ancienttdde.probes.models import ProbeDefinition, ProbeManifest, ProbeRecord
from ancienttdde.probes.results import case_ids, empty_results, read_results
from ancienttdde.probes.suite import inspect_probe, read_manifest, rebuild, reload_probe
from ancienttdde.scenario.snapshot import ScenarioSnapshot, content_digest

CONTENT_INPUTS = ("content/maps/format-seed.aoe2scenario",)


def current_inputs(root: Path) -> list[HashRecord]:
    return hash_inputs(root, CONTENT_INPUTS, "probe", layer="probes")


def run_worker(root: Path, name: str, path: Path, *, check: bool = False) -> None:
    arguments = [str(root), name, str(path)] + (["--check-xs"] if check else [])
    run_module("ancienttdde.probes.construct", *arguments, label=f"Probe {name}")


def build_probe(root: Path, definition: ProbeDefinition, path: Path) -> ScenarioSnapshot:
    run_worker(root, definition.id.value, path)
    return inspect_probe(path)


def recorded_selection(directory: Path) -> list[str] | None:
    """Return the probe IDs an existing suite's manifest lists, whatever its schema."""
    path = directory / "manifest.json"
    if not path.exists():
        return None
    return [text_field(row, "id") for row in rows(read_object(path).get("probes"), "probes")]


def build_probes(root: Path, output: Path | None = None, *, only: list[str] | None = None) -> Path:
    root = root.resolve()
    definitions = select_probes(only)
    scenarios = [f"{p.id}.{suffix}" for p in definitions for suffix in ("aoe2scenario", "json")]
    directory = prepare_output(
        root,
        output,
        ".build/probes",
        [*scenarios, "instructions.md", "results.json"],
        kind="mechanics-probes",
    )
    previous = recorded_selection(directory)
    if previous is not None and previous != [p.id.value for p in definitions]:
        raise ValueError("Existing probe suite uses a different selection; choose another output")
    inputs = current_inputs(root)
    existing = None
    if (directory / "results.json").exists():
        existing = read_results(directory, [c.id for p in definitions for c in p.cases])
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ancienttdde-probes-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        snapshots = run_parallel(
            [
                partial(build_probe, root, definition, staging / f"{definition.id}.aoe2scenario")
                for definition in definitions
            ]
        )
        records: list[ProbeRecord] = []
        for definition, snapshot in zip(definitions, snapshots, strict=True):
            write_json(staging / f"{definition.id}.json", snapshot)
            records.append(
                ProbeRecord(
                    id=definition.id.value,
                    scenario=f"{definition.id}.aoe2scenario",
                    snapshot=f"{definition.id}.json",
                    normalized_sha256=content_digest(snapshot),
                    case_ids=[c.id for c in definition.cases],
                )
            )
        if existing:
            content = {c: p["normalized_sha256"] for p in records for c in p["case_ids"]}
            if any(
                r["scenario_sha256"] != content[c["id"]]
                for c in existing["cases"]
                for r in c["runs"]
            ):
                raise ValueError(
                    "Recorded results refer to different probe content; choose another output"
                )
        (staging / "instructions.md").write_text(instructions(definitions), encoding="utf-8")
        artifacts = hash_records(staging, sorted(p.name for p in staging.iterdir()))
        manifest = ProbeManifest(
            schema_version=SCHEMA_VERSION,
            kind="mechanics-probes",
            **versions(),
            inputs=inputs,
            artifacts=artifacts,
            probes=records,
            xs_checked=True,
            in_game_verified=False,
        )
        write_json(staging / "manifest.json", manifest)
        published = [*scenarios, "instructions.md"]
        if existing is None:
            write_json(staging / "results.json", empty_results(manifest))
            published.append("results.json")
        publish(staging, directory, published)
    return directory


def check_probe(directory: Path, root: Path, record: ProbeRecord) -> None:
    reload_probe(directory, record)
    run_worker(root, record["id"], directory / record["scenario"], check=True)


def verify_manifest(directory: Path, root: Path) -> ProbeManifest:
    """Check the tools, inputs, artifacts, instructions and recorded results without a parser."""
    manifest = read_manifest(project_path(directory, "manifest.json"))
    selection = [p["id"] for p in manifest["probes"]]
    require_current_versions(
        manifest, kind="mechanics-probes", rebuild=rebuild(directory, selection)
    )
    verify_inputs(manifest["inputs"], current_inputs(root), "probe")
    expected_paths = {p[key] for p in manifest["probes"] for key in ("scenario", "snapshot")}
    if {r["path"] for r in manifest["artifacts"]} != expected_paths | {"instructions.md"}:
        raise ValueError("Probe manifest must record every artifact")
    verify_hashes(directory, manifest["artifacts"], "probe artifact")
    definitions: tuple[ProbeDefinition, ...] = select_probes(selection)
    if (directory / "instructions.md").read_text(encoding="utf-8") != instructions(definitions):
        raise ValueError("Probe instructions differ from current definitions")
    results = read_results(directory, case_ids(manifest))
    current = {c: p["normalized_sha256"] for p in manifest["probes"] for c in p["case_ids"]}
    if any(r["scenario_sha256"] != current[c["id"]] for c in results["cases"] for r in c["runs"]):
        raise ValueError("Recorded result belongs to different scenario content")
    return manifest


def verify_scenarios(directory: Path, root: Path, manifest: ProbeManifest) -> None:
    """Reload every probe and check it against the manifest, its sidecar and its XS."""
    run_parallel([partial(check_probe, directory, root, record) for record in manifest["probes"]])


def verify_probes(directory: Path, root: Path) -> ProbeManifest:
    """Check hashes, reloads, sidecars, instructions, embedded XS and recorded results."""
    directory, root = directory.resolve(), root.resolve()
    manifest = verify_manifest(directory, root)
    verify_scenarios(directory, root, manifest)
    return manifest


def compare_probes(directory: Path, expected: Path) -> None:
    """Reject probe logic that differs from a build of the current definitions."""
    manifest = read_manifest(project_path(directory.resolve(), "manifest.json"))
    current = read_manifest(project_path(expected.resolve(), "manifest.json"))
    if [p["id"] for p in manifest["probes"]] != [p["id"] for p in current["probes"]]:
        raise ValueError("Probe selection differs from the comparison build")
    for record, reference in zip(manifest["probes"], current["probes"], strict=True):
        if record["normalized_sha256"] != reference["normalized_sha256"]:
            raise ValueError(f"Probe logic differs from current definitions: {record['id']}")


def validate_probes(directory: Path, root: Path) -> ProbeManifest:
    directory, root = directory.resolve(), root.resolve()
    # The checks that need no parser run first, so a stale suite fails before any rebuild.
    manifest = verify_manifest(directory, root)
    selection = [p["id"] for p in manifest["probes"]]
    with TemporaryDirectory(prefix="ancienttdde-probe-validation-") as temporary:
        expected = Path(temporary)
        # Reconstruct from current code so editing a sidecar and its hashes cannot hide changes.
        run_parallel(
            (
                partial(verify_scenarios, directory, root, manifest),
                partial(build_probes, root, expected, only=selection),
            )
        )
        compare_probes(directory, expected)
    return manifest
