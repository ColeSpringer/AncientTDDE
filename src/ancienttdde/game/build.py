"""Build and independently reconstruct self-contained playable game artifacts."""

import json
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from ancienttdde.common.data import HashRecord, digest, object_value, read_object, write_json
from ancienttdde.common.hashing import hash_inputs, hash_records, verify_hashes, verify_inputs
from ancienttdde.common.manifest import (
    SCHEMA_VERSION,
    ManifestBase,
    parse_manifest,
    rebuild_command,
    require_current_versions,
    versions,
)
from ancienttdde.common.output import prepare_output, project_path, publish
from ancienttdde.common.worker import run_module, run_parallel
from ancienttdde.game.catalog import check_pads, load_shop
from ancienttdde.game.civilizations import load_profiles
from ancienttdde.game.config import load_balance, load_lanes
from ancienttdde.game.instructions import instructions
from ancienttdde.game.stock import load_stock
from ancienttdde.game.waves import check_lumber_room
from ancienttdde.map.build import CONTENT_INPUTS as MAP_INPUTS
from ancienttdde.map.build import read_content
from ancienttdde.map.foundation import migrate_map, validate_map
from ancienttdde.scenario.checks import (
    require_custom_victory,
    require_no_dependencies,
    require_unique_placements,
    require_version,
)
from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.snapshot import ScenarioSnapshot, content_digest, validate_references

SCENARIO_NAME = "ancient-td-de.aoe2scenario"
# The declarations the scenario embeds before assets/runtime.xs, for checking that file alone.
PRELUDE = "runtime-prelude.xs"
ARTIFACTS = (
    SCENARIO_NAME,
    "map.json",
    "scenario.json",
    "instructions.md",
    "validation.json",
    PRELUDE,
)
CONTENT_INPUTS = (
    *MAP_INPUTS,
    "content/balance/game.json",
    "content/balance/shop.json",
    "content/balance/civilizations.json",
    "content/balance/stock.json",
)


class GameManifest(ManifestBase):
    kind: Literal["ancient-td-game"]
    normalized_sha256: str
    xs_checked: Literal[True]
    in_game_verified: Literal[False]


def read_manifest(path: Path) -> GameManifest:
    raw = read_object(path)
    base = parse_manifest(raw, kind="ancient-td-game", rebuild=rebuild(path.parent))
    if raw.get("xs_checked") is not True or raw.get("in_game_verified") is not False:
        raise ValueError("Game manifest must distinguish static validation from game observations")
    if {r["path"] for r in base["artifacts"]} != set(ARTIFACTS):
        raise ValueError(
            "Game manifest must record every artifact this version builds; "
            f"rebuild with {rebuild(path.parent)}"
        )
    return GameManifest(
        **base,
        kind="ancient-td-game",
        normalized_sha256=digest(raw.get("normalized_sha256")),
        xs_checked=True,
        in_game_verified=False,
    )


def rebuild(directory: Path) -> str:
    return rebuild_command("ancient-td-game", directory)


def current_inputs(root: Path) -> list[HashRecord]:
    return hash_inputs(root, CONTENT_INPUTS, "game", layer="game")


def worker(root: Path, data: Path, path: Path, *, check_only: bool = False) -> None:
    # Construction writes the XS prelude beside the scenario, from the inputs it embeds.
    construction = [str(root), str(data), str(path), str(path.with_name(PRELUDE))]
    arguments = ["--check-xs", str(path)] if check_only else construction
    run_module("ancienttdde.game.construct", *arguments, label="Game generation/XS validation")


def inspect_game(path: Path) -> ScenarioSnapshot:
    snapshot = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    if findings := validate_references(snapshot):
        raise ValueError(f"Game contains dangling references: {findings}")
    require_version(snapshot)
    if snapshot["map"]["width"] != 200 or snapshot["map"]["height"] != 200:
        raise ValueError("Game must use the migrated 200x200 map")
    require_custom_victory(snapshot, conditions_required=False)
    require_no_dependencies(snapshot, allow_embedded_xs=True)
    require_unique_placements(snapshot)
    if not snapshot["triggers"] or not snapshot["variables"]:
        raise ValueError("Game is missing its engine")
    return snapshot


def build_game(root: Path, output: Path | None = None) -> Path:
    root = root.resolve()
    directory = prepare_output(root, output, ".build/game", ARTIFACTS, kind="ancient-td-game")
    inputs = current_inputs(root)
    legacy, config = read_content(root)
    data = migrate_map(legacy, config)
    report = validate_map(data, config)
    balance = load_balance(root / "content/balance/game.json")
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(root / "content/balance/shop.json", config["anchors"], families)
    stock = load_stock(root / "content/balance/stock.json")
    stock.check_waves(balance)
    profiles = load_profiles(root / "content/balance/civilizations.json", balance, shop, stock)
    check_pads(shop, data, config)
    check_lumber_room(load_lanes(object_value(data.get("anchors"), "anchors")), data, config)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ancienttdde-game-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        write_json(staging / "map.json", data)
        write_json(staging / "validation.json", report)
        worker(root, staging / "map.json", staging / SCENARIO_NAME)
        snapshot = inspect_game(staging / SCENARIO_NAME)
        write_json(staging / "scenario.json", snapshot)
        (staging / "instructions.md").write_text(
            instructions(balance, shop, profiles), encoding="utf-8"
        )
        manifest = GameManifest(
            schema_version=SCHEMA_VERSION,
            kind="ancient-td-game",
            **versions(),
            inputs=inputs,
            artifacts=hash_records(staging, ARTIFACTS),
            normalized_sha256=content_digest(snapshot),
            xs_checked=True,
            in_game_verified=False,
        )
        write_json(staging / "manifest.json", manifest)
        publish(staging, directory, ARTIFACTS)
    return directory


def verify_manifest(directory: Path, root: Path) -> GameManifest:
    """Check the recorded tools, inputs and artifact hashes; none of this runs the parser."""
    manifest = read_manifest(project_path(directory, "manifest.json"))
    require_current_versions(manifest, kind="ancient-td-game", rebuild=rebuild(directory))
    verify_inputs(manifest["inputs"], current_inputs(root), "game")
    verify_hashes(directory, manifest["artifacts"], "game artifact")
    return manifest


def verify_scenario(directory: Path, root: Path, manifest: GameManifest) -> None:
    """Reload the scenario and check it against the manifest, its sidecar and its XS."""
    snapshot, _ = run_parallel(
        (
            partial(inspect_game, directory / SCENARIO_NAME),
            partial(
                worker, root, directory / "map.json", directory / SCENARIO_NAME, check_only=True
            ),
        )
    )
    if content_digest(snapshot) != manifest["normalized_sha256"]:
        raise ValueError("Game normalized content differs after reload")
    if snapshot != json.loads((directory / "scenario.json").read_text(encoding="utf-8")):
        raise ValueError("Game reload differs from the inspection sidecar")


def verify_game(directory: Path, root: Path) -> GameManifest:
    """Check the recorded hashes, the reloaded scenario, its sidecar and its XS."""
    root, directory = root.resolve(), directory.resolve()
    manifest = verify_manifest(directory, root)
    verify_scenario(directory, root, manifest)
    return manifest


def compare_game(directory: Path, expected: Path) -> None:
    """Reject logic or sidecars that differ from a build of the current definitions."""
    directory, expected = directory.resolve(), expected.resolve()
    manifest = read_manifest(project_path(directory, "manifest.json"))
    current = read_manifest(project_path(expected, "manifest.json"))
    if current["normalized_sha256"] != manifest["normalized_sha256"]:
        raise ValueError("Game logic differs from current definitions")
    for name in ("map.json", "validation.json", "instructions.md", PRELUDE):
        if (directory / name).read_bytes() != (expected / name).read_bytes():
            raise ValueError(f"Game sidecar differs from current definitions: {name}")


def validate_game(directory: Path, root: Path) -> GameManifest:
    root, directory = root.resolve(), directory.resolve()
    # The checks that need no parser run first, so a stale build fails before any rebuild.
    manifest = verify_manifest(directory, root)
    with TemporaryDirectory(prefix="ancienttdde-game-validation-") as temporary:
        expected = Path(temporary)
        # Reloading the build and rebuilding the current definitions are independent.
        run_parallel(
            (
                partial(verify_scenario, directory, root, manifest),
                partial(build_game, root, expected),
            )
        )
        compare_game(directory, expected)
    return manifest
