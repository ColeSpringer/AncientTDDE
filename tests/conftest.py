"""Shared fixtures, quiet parser helpers and typed accessors over inspection snapshots."""

import contextlib
import io
import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

import pytest
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.common.data import JSONValue, read_object, rows
from ancienttdde.common.hashing import hash_file
from ancienttdde.game.build import GameManifest
from ancienttdde.game.build import read_manifest as read_game_manifest
from ancienttdde.map.models import FoundationConfig, MapDocument
from ancienttdde.models import ObjectMapping
from ancienttdde.probes.build import build_probes
from ancienttdde.probes.models import ProbeManifest
from ancienttdde.probes.suite import read_manifest as read_probe_manifest
from ancienttdde.scenario.snapshot import MapUnit, ScenarioSnapshot, TriggerRecord

ROOT = Path(__file__).resolve().parents[1]

# Stock object IDs the probe tests look for.
KING = 434
BARRACKS = 12

type Attributes = Mapping[str, JSONValue]
type FoundationInputs = tuple[MapDocument, FoundationConfig]
type GameBuild = tuple[Path, GameManifest]
type ProbeSuite = tuple[Path, ProbeManifest]


def new_scenario(version: str | None = None) -> AoE2DEScenario:
    """Create an empty scenario without the parser's progress output."""
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_default(version)


def load_scenario(path: Path) -> AoE2DEScenario:
    """Load a scenario without the parser's progress output."""
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_file(str(path))


def save_scenario(scenario: AoE2DEScenario, path: Path) -> None:
    """Write a scenario without the parser's progress output."""
    with contextlib.redirect_stdout(io.StringIO()):
        scenario.write_to_file(str(path))


def snapshot(path: Path) -> ScenarioSnapshot:
    """Return the inspection sidecar a build wrote beside a generated scenario.

    Probe suites store `<name>.json` beside `<name>.aoe2scenario`; a game build stores
    `scenario.json`. Validation proves each sidecar equals a fresh inspection.
    """
    sidecar = path.with_suffix(".json")
    if not sidecar.is_file():
        sidecar = path.parent / "scenario.json"
    return cast(ScenarioSnapshot, json.loads(sidecar.read_text(encoding="utf-8")))


def probe_snapshot(suite: Path, name: str) -> ScenarioSnapshot:
    return snapshot(suite / f"{name}.aoe2scenario")


def tiles(scenario: ScenarioSnapshot) -> list[list[int]]:
    """Return the terrain tiles of a snapshot inspected with include_terrain=True."""
    terrain = scenario["map"]
    assert "tiles" in terrain, "the scenario was inspected without terrain"
    return terrain["tiles"]


def triggers_by_name(scenario: ScenarioSnapshot) -> dict[str, TriggerRecord]:
    return {trigger["name"]: trigger for trigger in scenario["triggers"]}


def variables_by_name(scenario: ScenarioSnapshot) -> dict[str, int]:
    return {variable["name"]: variable["variable_id"] for variable in scenario["variables"]}


def attr_int(attributes: Attributes, key: str) -> int:
    value = attributes.get(key)
    assert type(value) is int, f"{key} is not an integer: {value!r}"
    return value


def attr_number(attributes: Attributes, key: str) -> float:
    value = attributes.get(key)
    assert isinstance(value, int | float) and not isinstance(value, bool), f"{key}: {value!r}"
    return value


def attr_text(attributes: Attributes, key: str) -> str:
    value = attributes.get(key)
    assert isinstance(value, str), f"{key} is not text: {value!r}"
    return value


def attr_list(attributes: Attributes, key: str) -> list[int]:
    """Return an attribute's integers; an absent or null attribute is an empty list."""
    value = attributes.get(key) or []
    assert isinstance(value, list), f"{key} is not a list: {value!r}"
    numbers = [item for item in value if type(item) is int]
    assert len(numbers) == len(value), f"{key} holds non-integers: {value!r}"
    return numbers


def rehash_artifacts(directory: Path, *names: str) -> None:
    """Record fresh hashes for edited artifacts, as someone hiding the edit would."""
    path = directory / "manifest.json"
    manifest = read_object(path)
    for record in rows(manifest.get("artifacts"), "artifacts"):
        if record.get("path") in names:
            record["sha256"] = hash_file(directory / str(record["path"]))
    path.write_text(json.dumps(manifest), encoding="utf-8")


def compile_harness(
    output: Path, harness: str, replacements: Mapping[str, str], *, warnings: bool = False
) -> Path:
    """Compile a tests/support C++ harness with generated code in place of its markers.

    Skips the calling test when no C++ compiler is installed.
    """
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("Executing generated XS in a C++ harness requires a C++ compiler")
    text = (ROOT / "tests/support" / harness).read_text(encoding="utf-8")
    for marker, code in replacements.items():
        assert marker in text, f"{harness} has no {marker} marker"
        text = text.replace(marker, code)
    source = output / harness
    source.write_text(text, encoding="utf-8")
    executable = source.with_suffix("")
    flags = ["-Wall", "-Wextra"] if warnings else []
    result = subprocess.run(
        [compiler, "-std=c++17", *flags, str(source), "-o", str(executable)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return executable


@pytest.fixture(scope="session")
def game_build(tmp_path_factory: pytest.TempPathFactory) -> GameBuild:
    # Built through the CLI so the command's own path is covered without another build.
    output = tmp_path_factory.mktemp("game-build")
    result = CliRunner().invoke(app, ["build", "--root", str(ROOT), "--output", str(output)])
    assert result.exit_code == 0, result.output
    return output, read_game_manifest(output / "manifest.json")


@pytest.fixture(scope="session")
def probe_suite(tmp_path_factory: pytest.TempPathFactory) -> ProbeSuite:
    directory = build_probes(ROOT, tmp_path_factory.mktemp("mechanics-probes"))
    return directory, read_probe_manifest(directory / "manifest.json")


@pytest.fixture(scope="session")
def payments_suite(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_probes(ROOT, tmp_path_factory.mktemp("payments-probe"), only=["payments"])


def object_mapping(
    key: str,
    legacy_id: int,
    stock_id: int,
    dataset: Literal["BuildingInfo", "OtherInfo", "UnitInfo", "HeroInfo"],
    name: str,
    size: int = 0,
) -> ObjectMapping:
    return {
        "key": key,
        "legacy_id": legacy_id,
        "civilization_ids": [9, 17, 8],
        "stock_id": stock_id,
        "disposition": "replace" if legacy_id != stock_id else "keep",
        "status": "reviewed",
        "map_identity": {"dataset": dataset, "name": name, "parser_version": "0.9.4"},
        "blocking_size": size,
    }


@pytest.fixture
def foundation_inputs() -> FoundationInputs:
    tiles = [[0, 0, -1] for _ in range(256)]
    for y in range(6):
        for x in range(10, 16):
            tiles[y * 16 + x] = [1, 0, -1]
    tiles[7 * 16 + 3] = [4, 2, 0]
    units: list[MapUnit] = []
    for reference, owner, unit, x, y in [
        (0, 0, 857, 6.5, 8.5),
        (10, 1, 684, 12.5, 11.5),
        (11, 1, 204, 2.5, 8.5),
        (12, 8, 1740, 3.5, 10.5),
        (13, 1, 104, 7.5, 12.5),
        (14, 1, 83, 7.5, 12.5),
    ]:
        units.append(
            {
                "reference_id": reference,
                "player_id": owner,
                "unit_const": unit,
                "x": x,
                "y": y,
                "z": 1.0,
                "rotation": 1.5,
                "status": 2,
                "initial_animation_frame": 0,
                "garrisoned_in_id": 13 if reference == 14 else -1,
            }
        )
    legacy: MapDocument = {
        "schema_version": 1,
        "scenario_version": "1.49",
        "source": {"path": "original.aoe2scenario", "sha256": "a" * 64},
        "map": {"width": 16, "height": 16, "tiles": tiles},
        "players": [{"player_id": p, "civilization_id": c} for p, c in [(0, 9), (1, 17), (8, 8)]],
        "units": units,
    }
    config: FoundationConfig = {
        "schema_version": 1,
        "objects": [
            object_mapping("blocker", 857, 1776, "OtherInfo", "BLOCKER", 1),
            object_mapping("life", 684, 598, "BuildingInfo", "OUTPOST", 1),
            object_mapping("cart", 204, 128, "UnitInfo", "TRADE_CART_EMPTY"),
            object_mapping("sign", 1740, 819, "OtherInfo", "SIGN"),
            object_mapping("monastery", 104, 104, "BuildingInfo", "MONASTERY", 3),
            object_mapping("villager", 83, 83, "UnitInfo", "VILLAGER_MALE"),
        ],
        "anchors": {
            "lane.p1.spawn": {"point": [1.5, 8.5]},
            "lane.p1.exit": {"point": [12.5, 8.5]},
            "lane.p1.life": {"point": [12.5, 11.5], "reference_id": 10},
            "trade.home": {"point": [7.5, 12.5], "reference_id": 13},
            "siege.p1.1": {"point": [12.5, 2.5], "region": [11, 1, 13, 3]},
            "shop.attack": {"region": [2, 9, 4, 10]},
        },
        "placement_overrides": [{"reference_id": 12, "owner": 0, "caption": "+4 attack: 1 King"}],
        "terrain_patches": [
            {
                "key": "siege.p1.1",
                "region": [11, 1, 13, 3],
                "terrain_id": 0,
                "allowed_source_terrain": [1],
            }
        ],
        "routes": [
            {
                "key": "lane.p1",
                "start": "lane.p1.spawn",
                "end": "lane.p1.exit",
                "medium": "land",
                "region": [1, 7, 12, 9],
            }
        ],
        "isolation": [
            {"key": "siege.p1.1", "start": "siege.p1.1", "medium": "land", "region": [11, 1, 13, 3]}
        ],
        "land_terrain": [0, 4],
        "water_terrain": [1, 4],
    }
    return legacy, config


@pytest.fixture
def map_project(tmp_path: Path, foundation_inputs: FoundationInputs) -> Path:
    """A project root holding only the map content a map build reads."""
    legacy, config = foundation_inputs
    directory = tmp_path / "content/maps"
    directory.mkdir(parents=True)
    (directory / "legacy-map.json").write_text(json.dumps(legacy))
    (directory / "foundation.json").write_text(json.dumps(config))
    save_scenario(new_scenario("1.59"), directory / "format-seed.aoe2scenario")
    return tmp_path
