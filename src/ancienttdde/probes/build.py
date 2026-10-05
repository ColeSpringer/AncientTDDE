"""Generate, reload and validate reproducible solo mechanic experiments."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from ancienttdde.generation.build import normalized_hash, write_json
from ancienttdde.generation.models import HashRecord
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.probes.catalog import instructions, select_probes
from ancienttdde.probes.models import (
    AiMode,
    ProbeDefinition,
    ProbeManifest,
    ProbeRecord,
    ProbeSnapshot,
)
from ancienttdde.probes.native import OBJECTS, footprint_sizes, grid_offset, stock, survival_ids
from ancienttdde.probes.results import empty_results, read_results
from ancienttdde.probes.serialization import digest, hashes, read_object, rows, text_field
from ancienttdde.provenance import hash_file, project_path
from ancienttdde.validation import validate_references

INPUTS = (
    "content/maps/format-seed.aoe2scenario",
    "src/ancienttdde/ai/passive.per",
    "src/ancienttdde/xs/probe-heartbeat.xs",
    "src/ancienttdde/xs/probe-raider-purchases.xs",
    "src/ancienttdde/inspection/scenario.py",
    "src/ancienttdde/probes/catalog.py",
    "src/ancienttdde/probes/models.py",
    "src/ancienttdde/probes/native.py",
    "src/ancienttdde/probes/scenarios.py",
    "src/ancienttdde/probes/xs.py",
)


def probe_digest(snapshot: ProbeSnapshot) -> str:
    serialized = json.dumps(
        {
            "scenario": normalized_hash(snapshot),
            "embedded_ai": snapshot["embedded_ai"],
            "messages": snapshot["messages"],
            "options": snapshot["options"],
            "global_victory": snapshot["global_victory"],
        },
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def read_manifest(path: Path) -> ProbeManifest:
    raw = read_object(path)
    if (
        type(raw.get("schema_version")) is not int
        or raw["schema_version"] != 1
        or (raw.get("kind") != "mechanics-probes")
    ):
        raise ValueError("Unsupported probe manifest")
    records: list[ProbeRecord] = []
    for row in rows(raw.get("probes"), "probes"):
        name = text_field(row, "id")
        definition = select_probes([name])[0]
        expected_ids = [c.id for c in definition.cases]
        if row.get("case_ids") != expected_ids:
            raise ValueError(f"Probe case coverage differs from current definitions: {name}")
        if row.get("scenario") != f"{name}.aoe2scenario" or row.get("snapshot") != f"{name}.json":
            raise ValueError("Unexpected probe artifact path")
        records.append(
            ProbeRecord(
                id=name,
                scenario=f"{name}.aoe2scenario",
                snapshot=f"{name}.json",
                normalized_sha256=digest(row.get("normalized_sha256")),
                case_ids=expected_ids,
            )
        )
    if not records or len({p["id"] for p in records}) != len(records):
        raise ValueError("Probe manifest must list distinct, nonempty probes")
    if raw.get("xs_checked") is not True or raw.get("in_game_verified") is not False:
        raise ValueError("Probe manifest must distinguish static validation from game observations")
    return ProbeManifest(
        schema_version=1,
        kind="mechanics-probes",
        inputs=hashes(raw.get("inputs"), "input"),
        artifacts=hashes(raw.get("artifacts"), "artifact"),
        probes=records,
        xs_checked=True,
        in_game_verified=False,
    )


def run_worker(root: Path, name: str, path: Path, *, check: bool = False) -> None:
    arguments = [sys.executable, "-m", "ancienttdde.probes.scenarios", str(root), name, str(path)]
    if check:
        arguments.append("--check-xs")
    process = subprocess.run(arguments, capture_output=True, text=True, timeout=120, check=False)
    if process.returncode:
        raise ValueError(f"Probe {name} failed: {process.stderr.strip()}")


def inspect_probe(path: Path) -> ProbeSnapshot:
    raw = inspect_scenario(path, include_terrain=True)
    findings = validate_references(raw)
    if findings:
        raise ValueError(f"Probe has dangling references: {findings}")
    snapshot = cast(ProbeSnapshot, raw)
    if snapshot["scenario_version"] != "1.59" or (
        snapshot["map"]["width"] != 64 or snapshot["map"]["height"] != 64
    ):
        raise ValueError("Probe must be a 64x64 version-1.59 scenario")
    if snapshot["victory_condition"] != 4:
        raise ValueError("Probe must not end through automatic standard victory")
    if snapshot["options"]["victory_custom_conditions_required"] or snapshot["global_victory"] != {
        "conquest_required": 0,
        "ruins": 0,
        "artifacts_required": 0,
        "discovery": 0,
        "explored_percent_of_map_required": 0,
        "gold_required": 0,
    }:
        raise ValueError("Probe must disable all automatic victory conditions")
    if snapshot["options"] != {
        "lock_teams": True,
        "allow_players_choose_teams": False,
        "random_start_points": False,
        "secondary_game_modes": 0,
        "legacy_execution_order": False,
        "all_techs": False,
        "victory_custom_conditions_required": False,
        "computer_personalities_locked": True,
    }:
        raise ValueError("Probe settings must preserve fixed teams and standard technology rules")
    dependencies = snapshot["dependencies"]
    if (
        dependencies["external_xs"]
        or dependencies["ai_files"]
        or (any(dependencies["cinematics"]) or dependencies["background_image"])
    ):
        raise ValueError("Probe contains external gameplay dependencies")
    if not snapshot["players"][1]["human"] or any(p["human"] for p in snapshot["players"][2:]):
        raise ValueError("Probe must be testable solo as P1")
    active = {p["player_id"] for p in snapshot["players"] if p["active"]}
    counted = survival_ids()
    surviving = {u["player_id"] for u in snapshot["units"] if u["unit_const"] in counted}
    if defeated := active - surviving:
        raise ValueError(
            "Probe has active players the engine defeats at game start, which would satisfy "
            f"conquest or let them receive standard starts: {sorted(defeated)}"
        )
    for ai in snapshot["embedded_ai"][1:]:
        if (
            ai["name"] != "Ancient TD Passive"
            or not ai["script"].strip()
            or (ai["type"] != AiMode.CUSTOM)
        ):
            raise ValueError("Every computer must contain its passive AI")
    ids = [u["reference_id"] for u in snapshot["units"]]
    if len(ids) != len(set(ids)) or snapshot["next_unit_id"] <= max(ids, default=-1):
        raise ValueError("Probe placement IDs/allocator are invalid")
    if any(u["unit_const"] not in {stock(key) for key in OBJECTS} for u in snapshot["units"]):
        raise ValueError("Probe contains an unknown stock object")
    sizes = footprint_sizes()
    for unit in snapshot["units"]:
        if (size := sizes.get(unit["unit_const"])) is not None:
            offset = grid_offset(size)
            if (unit["x"] % 1, unit["y"] % 1) != (offset, offset):
                raise ValueError(
                    f"Probe places object {unit['reference_id']} off its {size}x{size} footprint "
                    f"grid at ({unit['x']}, {unit['y']})"
                )
    if not snapshot["triggers"]:
        raise ValueError("Probe has no mechanic logic")
    return snapshot


def reload_probe(directory: Path, record: ProbeRecord) -> ProbeSnapshot:
    snapshot = inspect_probe(project_path(directory, record["scenario"]))
    if probe_digest(snapshot) != record["normalized_sha256"]:
        raise ValueError(f"Probe normalized content differs after reload: {record['id']}")
    expected = json.loads(project_path(directory, record["snapshot"]).read_text(encoding="utf-8"))
    if snapshot != expected:
        raise ValueError(f"Probe reload differs from its inspection sidecar: {record['id']}")
    return snapshot


def output_directory(
    root: Path, output: Path | None, definitions: tuple[ProbeDefinition, ...]
) -> tuple[Path, ProbeManifest | None]:
    directory = (output or root / ".build/probes").resolve()
    protected = (
        "content",
        "legacy",
        "src",
        "tests",
        "tools",
        "docs",
        ".git",
        ".agents",
        ".codex",
        ".venv",
    )
    if root.is_relative_to(directory) or any(
        directory.is_relative_to((root / p).resolve()) for p in protected
    ):
        raise ValueError("Probe output cannot overwrite source directories or their ancestors")
    if directory.exists() and not directory.is_dir():
        raise ValueError("Probe output must be a directory")
    names = {f"{p.id}.{suffix}" for p in definitions for suffix in ("aoe2scenario", "json")}
    names |= {"manifest.json", "instructions.md", "results.json"}
    if any((directory / name).is_symlink() for name in names):
        raise ValueError("Probe output cannot replace artifact symlinks")
    previous: ProbeManifest | None = None
    if (directory / "manifest.json").exists():
        try:
            previous = read_manifest(directory / "manifest.json")
        except ValueError as error:
            raise ValueError("Probe output contains an unrelated or invalid manifest") from error
        if [p["id"] for p in previous["probes"]] != [p.id.value for p in definitions]:
            raise ValueError(
                "Existing probe suite uses a different selection; choose another output"
            )
        expected = names - {"manifest.json", "results.json"}
        if {r["path"] for r in previous["artifacts"]} != expected:
            raise ValueError("Existing manifest does not own the requested probe artifacts")
    elif any((directory / name).exists() for name in names):
        raise ValueError("Probe output cannot overwrite unrelated existing artifacts")
    return directory, previous


def build_probes(
    root: Path, output: Path | None = None, *, only: list[str] | None = None
) -> ProbeManifest:
    root = root.resolve()
    definitions = select_probes(only)
    directory, previous = output_directory(root, output, definitions)
    for relative in INPUTS:
        if not project_path(root, relative).is_file():
            raise ValueError(f"Missing probe input: {relative}")
    inputs = [HashRecord(path=p, sha256=hash_file(root / p)) for p in INPUTS]
    existing = None
    if (directory / "results.json").exists():
        if previous is None:
            raise ValueError("Existing probe results require their matching manifest")
        existing = read_results(directory, previous)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ancienttdde-probes-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        records: list[ProbeRecord] = []
        for definition in definitions:
            path = staging / f"{definition.id}.aoe2scenario"
            run_worker(root, definition.id.value, path)
            snapshot = inspect_probe(path)
            write_json(staging / f"{definition.id}.json", snapshot)
            records.append(
                ProbeRecord(
                    id=definition.id.value,
                    scenario=path.name,
                    snapshot=f"{definition.id}.json",
                    normalized_sha256=probe_digest(snapshot),
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
        artifacts = [
            HashRecord(path=p.name, sha256=hash_file(p)) for p in sorted(staging.iterdir())
        ]
        manifest: ProbeManifest = {
            "schema_version": 1,
            "kind": "mechanics-probes",
            "inputs": inputs,
            "artifacts": artifacts,
            "probes": records,
            "xs_checked": True,
            "in_game_verified": False,
        }
        write_json(staging / "manifest.json", manifest)
        directory.mkdir(parents=True, exist_ok=True)
        for path in staging.iterdir():
            path.replace(directory / path.name)
        if existing is None:
            write_json(directory / "results.json", empty_results(manifest))
    return manifest


def validate_probes(directory: Path, root: Path) -> ProbeManifest:
    directory, root = directory.resolve(), root.resolve()
    manifest = read_manifest(project_path(directory, "manifest.json"))
    if {r["path"] for r in manifest["inputs"]} != set(INPUTS):
        raise ValueError("Probe manifest must record every current input")
    for record in manifest["inputs"]:
        if hash_file(project_path(root, record["path"])) != record["sha256"]:
            raise ValueError(f"Probe input SHA-256 mismatch: {record['path']}")
    expected_paths = {p[key] for p in manifest["probes"] for key in ("scenario", "snapshot")}
    if {r["path"] for r in manifest["artifacts"]} != expected_paths | {"instructions.md"}:
        raise ValueError("Probe manifest must record every artifact")
    for record in manifest["artifacts"]:
        if hash_file(project_path(directory, record["path"])) != record["sha256"]:
            raise ValueError(f"Probe artifact SHA-256 mismatch: {record['path']}")
    definitions: tuple[ProbeDefinition, ...] = select_probes([p["id"] for p in manifest["probes"]])
    if (directory / "instructions.md").read_text(encoding="utf-8") != instructions(definitions):
        raise ValueError("Probe instructions differ from current definitions")
    with TemporaryDirectory(prefix="ancienttdde-probe-validation-") as temporary:
        for record in manifest["probes"]:
            snapshot = reload_probe(directory, record)
            # Reconstruct from current code so editing a sidecar and its hashes cannot hide changes.
            expected_path = Path(temporary) / record["scenario"]
            run_worker(root.resolve(), record["id"], expected_path)
            expected = inspect_probe(expected_path)
            if probe_digest(snapshot) != probe_digest(expected):
                raise ValueError(f"Probe logic differs from current definitions: {record['id']}")
            run_worker(root.resolve(), record["id"], directory / record["scenario"], check=True)
    results = read_results(directory, manifest)
    current = {c: p["normalized_sha256"] for p in manifest["probes"] for c in p["case_ids"]}
    if any(r["scenario_sha256"] != current[c["id"]] for c in results["cases"] for r in c["runs"]):
        raise ValueError("Recorded result belongs to different scenario content")
    return manifest
