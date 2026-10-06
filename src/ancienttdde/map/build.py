"""Build, reload, and validate a stock-DE map independently of the legacy package."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from ancienttdde.common.data import (
    HashRecord,
    digest,
    hashes,
    object_value,
    read_object,
    write_json,
)
from ancienttdde.common.hashing import hash_inputs, hash_records, verify_hashes, verify_inputs
from ancienttdde.common.manifest import (
    SCHEMA_VERSION,
    parse_manifest,
    rebuild_command,
    require_current_versions,
    versions,
)
from ancienttdde.common.output import prepare_output, project_path, publish
from ancienttdde.common.worker import run_module
from ancienttdde.map.foundation import migrate_map, validate_map
from ancienttdde.map.models import (
    BuildManifest,
    FoundationConfig,
    MapDocument,
    MapValidation,
)
from ancienttdde.scenario.checks import (
    require_custom_victory,
    require_no_dependencies,
    require_unique_placements,
    require_version,
)
from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.snapshot import ScenarioSnapshot, scenario_digest

CONTENT_INPUTS = (
    "content/maps/foundation.json",
    "content/maps/legacy-map.json",
    "content/maps/format-seed.aoe2scenario",
)
SCENARIO_NAME = "ancient-td-de-map.aoe2scenario"
ARTIFACTS = (SCENARIO_NAME, "map.json", "anchors.json", "validation.json")


def current_inputs(root: Path) -> list[HashRecord]:
    return hash_inputs(root, CONTENT_INPUTS, "map", layer="map")


def read_content(root: Path) -> tuple[MapDocument, FoundationConfig]:
    """Read the map definitions; hashing the current inputs first proves they exist."""
    config = cast(
        FoundationConfig, json.loads((root / CONTENT_INPUTS[0]).read_text(encoding="utf-8"))
    )
    legacy = cast(MapDocument, json.loads((root / CONTENT_INPUTS[1]).read_text(encoding="utf-8")))
    return legacy, config


def read_manifest(path: Path) -> BuildManifest:
    raw = read_object(path)
    base = parse_manifest(
        raw, kind="stock-de-map", rebuild=rebuild_command("stock-de-map", path.parent)
    )
    [source] = hashes([raw.get("source")], "source")
    return BuildManifest(
        **base,
        kind="stock-de-map",
        normalized_sha256=digest(raw.get("normalized_sha256")),
        source=source,
        # Compared with the current connectivity checks during validation.
        validation=cast(MapValidation, object_value(raw.get("validation"), "validation")),
    )


def check_reload(path: Path, expected: MapDocument) -> ScenarioSnapshot:
    reloaded = inspect_scenario(path, include_terrain=True)
    require_version(reloaded)
    if reloaded["triggers"] or reloaded["variables"]:
        raise ValueError("Map foundation must not contain gameplay logic")
    require_custom_victory(reloaded, conditions_required=True)
    require_no_dependencies(reloaded, allow_embedded_xs=False)
    for field in ("width", "height", "tiles"):
        if reloaded["map"].get(field) != expected["map"][field]:
            raise ValueError(f"Reloaded map differs from migrated terrain: {field}")
    if len(reloaded["units"]) != len(expected["units"]):
        raise ValueError("Reloaded placement count differs from migrated map")
    require_unique_placements(reloaded)
    actual = {u["reference_id"]: u for u in reloaded["units"]}
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


def build_map(root: Path, output: Path | None = None) -> Path:
    root = root.resolve()
    directory = prepare_output(root, output, ".build/map", ARTIFACTS, kind="stock-de-map")
    inputs = current_inputs(root)
    legacy, config = read_content(root)
    data = migrate_map(legacy, config)
    report = validate_map(data, config)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ancienttdde-map-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        write_json(staging / "map.json", data)
        run_module(
            "ancienttdde.map.construct",
            str(root / CONTENT_INPUTS[2]),
            str(staging / "map.json"),
            str(staging / SCENARIO_NAME),
            label="Modern map construction",
        )
        snapshot = check_reload(staging / SCENARIO_NAME, data)
        write_json(staging / "anchors.json", data.get("anchors", {}))
        write_json(staging / "validation.json", report)
        manifest = BuildManifest(
            schema_version=SCHEMA_VERSION,
            kind="stock-de-map",
            **versions(),
            inputs=inputs,
            artifacts=hash_records(staging, ARTIFACTS),
            normalized_sha256=scenario_digest(snapshot),
            source=data["source"],
            validation=report,
        )
        write_json(staging / "manifest.json", manifest)
        publish(staging, directory, ARTIFACTS)
    return directory


def validate_map_build(directory: Path, root: Path) -> BuildManifest:
    root, directory = root.resolve(), directory.resolve()
    manifest = read_manifest(project_path(directory, "manifest.json"))
    rebuild = rebuild_command("stock-de-map", directory)
    require_current_versions(manifest, kind="stock-de-map", rebuild=rebuild)
    verify_inputs(manifest["inputs"], current_inputs(root), "map")
    legacy, config = read_content(root)
    if {r["path"] for r in manifest["artifacts"]} != set(ARTIFACTS) or len(
        manifest["artifacts"]
    ) != len(ARTIFACTS):
        raise ValueError("Map manifest must record every artifact")
    verify_hashes(directory, manifest["artifacts"], "map artifact")
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
    if scenario_digest(snapshot) != manifest["normalized_sha256"]:
        raise ValueError("Map normalized content hash mismatch")
    if report != manifest["validation"]:
        raise ValueError("Map validation report differs from current checks")
    return manifest
