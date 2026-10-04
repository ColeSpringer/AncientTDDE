"""Build, reload, and validate a stock-DE map independently of the legacy package."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition

from ancienttdde.generation.foundation import migrate_map, validate_map
from ancienttdde.generation.models import (
    BuildManifest,
    FoundationConfig,
    HashRecord,
    MapDocument,
    ScenarioSnapshot,
)
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.provenance import hash_file, project_path

INPUTS = (
    "content/maps/foundation.json",
    "content/maps/legacy-map.json",
    "content/maps/format-seed.aoe2scenario",
)
SCENARIO_NAME = "ancient-td-de-map.aoe2scenario"
ARTIFACTS = (SCENARIO_NAME, "map.json", "anchors.json", "validation.json")


def write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def content_inputs(root: Path) -> tuple[MapDocument, FoundationConfig, list[HashRecord]]:
    for relative in INPUTS:
        if not project_path(root, relative).is_file():
            raise ValueError(f"Missing map input: {relative}")
    config = cast(FoundationConfig, json.loads((root / INPUTS[0]).read_text(encoding="utf-8")))
    legacy = cast(MapDocument, json.loads((root / INPUTS[1]).read_text(encoding="utf-8")))
    records = [HashRecord(path=p, sha256=hash_file(root / p)) for p in INPUTS]
    return legacy, config, records


def check_reload(path: Path, expected: MapDocument) -> ScenarioSnapshot:
    reloaded = cast(ScenarioSnapshot, inspect_scenario(path, include_terrain=True))
    if reloaded["scenario_version"] != "1.59":
        raise ValueError("Reloaded map must use scenario version 1.59")
    if reloaded["triggers"] or reloaded["variables"]:
        raise ValueError("Map foundation must not contain gameplay logic")
    if reloaded["victory_condition"] != VictoryCondition.CUSTOM:
        raise ValueError("Map foundation must not use automatic standard victory")
    dependencies = reloaded["dependencies"]
    if (
        dependencies["external_xs"]
        or dependencies["embedded_xs"]
        or dependencies["ai_files"]
        or any(dependencies["cinematics"])
        or dependencies["background_image"]
    ):
        raise ValueError("Map foundation must have no external or embedded gameplay dependencies")
    for field in ("width", "height", "tiles"):
        if reloaded["map"][field] != expected["map"][field]:
            raise ValueError(f"Reloaded map differs from migrated terrain: {field}")
    if len(reloaded["units"]) != len(expected["units"]):
        raise ValueError("Reloaded placement count differs from migrated map")
    actual = {u["reference_id"]: u for u in reloaded["units"]}
    if len(actual) != len(reloaded["units"]):
        raise ValueError("Reloaded placements must have unique instance IDs")
    if type(reloaded["next_unit_id"]) is not int or reloaded["next_unit_id"] <= max(
        actual, default=-1
    ):
        raise ValueError("Reloaded unit ID allocator would collide with existing placements")
    for unit in expected["units"]:
        found = actual.get(unit["reference_id"])
        if found is None or any(
            found.get(key) != value for key, value in unit.items() if key != "object_key"
        ):
            raise ValueError(
                f"Reloaded placement differs from migrated map: {unit['reference_id']}"
            )
    for player in reloaded["players"][1:]:
        if not player["active"] or player["human"] != (player["player_id"] != 8):
            raise ValueError("Reloaded map must provide seven human slots and a computer slot")
        if player["civilization"] != "RANDOM" or any(
            player[field] for field in ("disabled_units", "disabled_buildings", "disabled_techs")
        ):
            raise ValueError("Reloaded map contains legacy civilization restrictions")
    return reloaded


def normalized_hash(snapshot: ScenarioSnapshot) -> str:
    # Scenario headers can carry save metadata; gameplay-relevant content is stable.
    normalized = {
        "version": snapshot["scenario_version"],
        "next_unit_id": snapshot["next_unit_id"],
        "victory_condition": snapshot["victory_condition"],
        "map": {
            "width": snapshot["map"]["width"],
            "height": snapshot["map"]["height"],
            "tiles": snapshot["map"]["tiles"],
        },
        "units": sorted(snapshot["units"], key=lambda u: u["reference_id"]),
        "players": snapshot["players"],
        "dependencies": snapshot["dependencies"],
        "triggers": snapshot["triggers"],
        "variables": snapshot["variables"],
    }
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_map(root: Path, output: Path | None = None) -> BuildManifest:
    root = root.resolve()
    legacy, config, inputs = content_inputs(root)
    data = migrate_map(legacy, config)
    report = validate_map(data, config)
    destination = (output or root / ".build/map").resolve()
    protected = ("content", "legacy", "src", "tests", "tools", "docs", ".git", ".agents", ".codex")
    if destination == root or any(destination.is_relative_to(root / p) for p in protected):
        raise ValueError("Build output cannot overwrite source directories")
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "map.json", data)
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "ancienttdde.generation.scenario",
            str(root / INPUTS[2]),
            str(destination / "map.json"),
            str(destination / SCENARIO_NAME),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if process.returncode:
        raise ValueError(f"Modern map construction failed: {process.stderr.strip()}")
    snapshot = check_reload(destination / SCENARIO_NAME, data)
    write_json(destination / "anchors.json", data.get("anchors", {}))
    write_json(destination / "validation.json", report)
    manifest: BuildManifest = {
        "schema_version": 1,
        "kind": "stock-de-map",
        "inputs": inputs,
        "artifacts": [HashRecord(path=p, sha256=hash_file(destination / p)) for p in ARTIFACTS],
        "normalized_sha256": normalized_hash(snapshot),
        "source": data["source"],
        "validation": report,
    }
    write_json(destination / "manifest.json", manifest)
    return manifest


def validate_build(directory: Path, root: Path) -> BuildManifest:
    root = root.resolve()
    manifest = cast(
        BuildManifest, json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    )
    if manifest["schema_version"] != 1 or manifest["kind"] != "stock-de-map":
        raise ValueError("Unsupported map build manifest")
    if {r["path"] for r in manifest["inputs"]} != set(INPUTS) or len(manifest["inputs"]) != len(
        INPUTS
    ):
        raise ValueError("Map manifest must record every input")
    for record in manifest["inputs"]:
        path = project_path(root, record["path"])
        if not path.is_file() or hash_file(path) != record["sha256"]:
            raise ValueError(f"Map input SHA-256 mismatch: {record['path']}")
    if {r["path"] for r in manifest["artifacts"]} != set(ARTIFACTS) or len(
        manifest["artifacts"]
    ) != len(ARTIFACTS):
        raise ValueError("Map manifest must record every artifact")
    for record in manifest["artifacts"]:
        path = project_path(directory, record["path"])
        if not path.is_file() or hash_file(path) != record["sha256"]:
            raise ValueError(f"Map artifact SHA-256 mismatch: {record['path']}")
    legacy, config, _ = content_inputs(root)
    expected = migrate_map(legacy, config)
    generated = cast(MapDocument, json.loads((directory / "map.json").read_text(encoding="utf-8")))
    if generated != expected:
        raise ValueError("Generated map differs from current migration definitions")
    report = validate_map(expected, config)
    if json.loads((directory / "anchors.json").read_text(encoding="utf-8")) != expected.get(
        "anchors"
    ):
        raise ValueError("Map anchors sidecar differs from current definitions")
    if json.loads((directory / "validation.json").read_text(encoding="utf-8")) != report:
        raise ValueError("Map validation sidecar differs from current checks")
    if manifest["source"] != expected["source"]:
        raise ValueError("Map source provenance differs from extracted evidence")
    snapshot = check_reload(directory / SCENARIO_NAME, expected)
    if normalized_hash(snapshot) != manifest["normalized_sha256"]:
        raise ValueError("Map normalized content hash mismatch")
    if report != manifest["validation"]:
        raise ValueError("Map validation report differs from current checks")
    return manifest
