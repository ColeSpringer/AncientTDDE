import json
from pathlib import Path

import pytest
from conftest import load_scenario, new_scenario, rehash_artifacts, save_scenario, tiles
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.common.hashing import hash_file
from ancienttdde.scenario.inspect import inspect_scenario


def test_isolated_stock_map_build_reload_and_repeatability(map_project: Path) -> None:
    from ancienttdde.map.build import build_map, read_manifest, validate_map_build

    directory = build_map(map_project)
    assert directory == map_project / ".build/map"
    first = read_manifest(directory / "manifest.json")
    scenario = directory / "ancient-td-de-map.aoe2scenario"
    reloaded = inspect_scenario(scenario, include_terrain=True)
    assert reloaded["scenario_version"] == "1.59"
    assert reloaded["map"]["width"] == reloaded["map"]["height"] == 16
    assert tiles(reloaded)[7 * 16 + 3] == [4, 2, 0]
    assert tiles(reloaded)[2 * 16 + 12] == [0, 0, -1]
    assert reloaded["triggers"] == []
    assert reloaded["victory_condition"] == 4
    assert reloaded["external_xs"] == ""
    units = {u["reference_id"]: u for u in reloaded["units"]}
    assert units[0]["unit_const"] == 1776
    assert units[14]["garrisoned_in_id"] == 13
    assert units[12].get("caption_string") == "+4 attack: 1 King"
    assert reloaded["players"][1]["civilization"] == "RANDOM"
    assert reloaded["players"][1]["disabled_units"] == []
    assert all(p["active"] for p in reloaded["players"][1:])
    assert all(p["human"] for p in reloaded["players"][1:8])
    assert reloaded["players"][8]["human"] is False
    second = read_manifest(build_map(map_project, map_project / ".build/repeat") / "manifest.json")
    assert first["normalized_sha256"] == second["normalized_sha256"]
    assert first["inputs"] == second["inputs"]
    assert (
        validate_map_build(directory, map_project)["normalized_sha256"]
        == first["normalized_sha256"]
    )


def test_build_cli_and_validation_work_from_plain_data_without_original_package(
    map_project: Path,
) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["build", "--map-only", "--root", str(map_project)])
    assert result.exit_code == 0, result.output
    assert "in-game" in result.output.lower()
    result = runner.invoke(
        app, ["validate", "--root", str(map_project), "--build", str(map_project / ".build/map")]
    )
    assert result.exit_code == 0, result.output
    assert "Map" in result.output


@pytest.mark.parametrize(
    "filename", ["foundation.json", "legacy-map.json", "format-seed.aoe2scenario"]
)
def test_validation_rejects_stale_map_inputs(map_project: Path, filename: str) -> None:
    from ancienttdde.map.build import build_map, validate_map_build

    build_map(map_project)
    with (map_project / "content/maps" / filename).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="input SHA-256"):
        validate_map_build(map_project / ".build/map", map_project)


def test_a_map_built_with_other_tools_must_be_rebuilt(map_project: Path) -> None:
    from ancienttdde.map.build import build_map, validate_map_build

    directory = build_map(map_project)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["parser_version"] = "0.0.1"
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="stock-de-map was built with AoE2ScenarioParser 0.0.1"):
        validate_map_build(directory, map_project)


def test_validation_reloads_scenario_even_when_hashes_have_been_updated(map_project: Path) -> None:
    from ancienttdde.map.build import build_map, validate_map_build

    build_map(map_project)
    directory = map_project / ".build/map"
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    scenario = load_scenario(scenario_path)
    scenario.unit_manager.units[0][0].unit_const = 9999
    edited = directory / "edited.aoe2scenario"
    save_scenario(scenario, edited)
    edited.replace(scenario_path)
    rehash_artifacts(directory, scenario_path.name)
    with pytest.raises(ValueError, match="(unreviewed|Reloaded|normalized)"):
        validate_map_build(directory, map_project)


def test_reload_rejects_extra_placement_with_duplicate_instance_id(map_project: Path) -> None:
    from ancienttdde.map.build import build_map, check_reload

    build_map(map_project)
    directory = map_project / ".build/map"
    expected = json.loads((directory / "map.json").read_text())
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    scenario = load_scenario(scenario_path)
    # Gaia is inspected before player 1, whose life marker also has ID 10.
    scenario.unit_manager.add_unit(player=0, unit_const=9999, reference_id=10, x=1.5, y=8.5)
    edited = directory / "duplicate.aoe2scenario"
    save_scenario(scenario, edited)
    with pytest.raises(ValueError, match="(placement count|unique)"):
        check_reload(edited, expected)


def test_new_units_receive_unique_ids_after_loading_built_map(map_project: Path) -> None:
    from ancienttdde.map.build import build_map

    build_map(map_project)
    scenario_path = map_project / ".build/map/ancient-td-de-map.aoe2scenario"
    scenario = load_scenario(scenario_path)
    original_ids = {unit.reference_id for unit in scenario.unit_manager.get_all_units()}
    added = scenario.unit_manager.add_unit(player=0, unit_const=83, x=1.5, y=8.5)
    assert added.reference_id > max(original_ids)
    edited = scenario_path.with_name("extended.aoe2scenario")
    save_scenario(scenario, edited)
    reloaded = inspect_scenario(edited)
    identifiers = [unit["reference_id"] for unit in reloaded["units"]]
    assert len(set(identifiers)) == len(original_ids) + 1
    assert reloaded["next_unit_id"] > added.reference_id


def test_reload_rejects_allocator_below_existing_instance_ids(map_project: Path) -> None:
    from ancienttdde.map.build import build_map, check_reload

    build_map(map_project)
    directory = map_project / ".build/map"
    expected = json.loads((directory / "map.json").read_text())
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    scenario = load_scenario(scenario_path)
    scenario.unit_manager.reference_id_generator = (identifier for identifier in range(100))
    edited = directory / "unsafe-allocator.aoe2scenario"
    save_scenario(scenario, edited)
    with pytest.raises(ValueError, match="allocator"):
        check_reload(edited, expected)


def test_build_rejects_source_directories_and_nonempty_seeds(map_project: Path) -> None:
    from ancienttdde.map.build import build_map

    with pytest.raises(ValueError, match="source"):
        build_map(map_project, map_project / "content/generated")
    seed_path = map_project / "content/maps/format-seed.aoe2scenario"
    seed = load_scenario(seed_path)
    seed.unit_manager.add_unit(player=1, unit_const=83, x=1.5, y=1.5)
    edited = seed_path.with_name("nonempty.aoe2scenario")
    save_scenario(seed, edited)
    edited.replace(seed_path)
    with pytest.raises(ValueError, match="empty"):
        build_map(map_project)


@pytest.mark.parametrize("filename", ["anchors.json", "validation.json"])
def test_validation_checks_sidecar_contents_after_manifest_hashes_are_updated(
    map_project: Path, filename: str
) -> None:
    from ancienttdde.map.build import build_map, validate_map_build

    build_map(map_project)
    directory = map_project / ".build/map"
    (directory / filename).write_text("{}")
    rehash_artifacts(directory, filename)
    with pytest.raises(ValueError, match="sidecar"):
        validate_map_build(directory, map_project)


def test_legacy_map_extraction_records_provenance_without_copying_logic(tmp_path: Path) -> None:
    from ancienttdde.map.extract import extract_map

    source = tmp_path / "legacy.aoe2scenario"
    scenario = new_scenario()
    scenario.map_manager.map_size = 16
    scenario.map_manager.get_tile(x=3, y=7).elevation = 2
    scenario.unit_manager.add_unit(player=0, unit_const=66, x=3.5, y=7.5)
    scenario.trigger_manager.add_trigger("Legacy logic must not migrate")
    save_scenario(scenario, source)
    result = extract_map(source, source_name="original.aoe2scenario")
    assert result["source"] == {"path": "original.aoe2scenario", "sha256": hash_file(source)}
    assert len(result["map"]["tiles"]) == 256
    assert result["map"]["tiles"][7 * 16 + 3][1] == 2
    assert len(result["units"]) == 1
    assert "triggers" not in result
