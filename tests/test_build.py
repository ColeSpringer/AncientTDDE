import contextlib
import io
import json

import pytest
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.provenance import hash_file


@pytest.fixture
def map_project(tmp_path, foundation_inputs):
    legacy, config = foundation_inputs
    directory = tmp_path / "content/maps"
    directory.mkdir(parents=True)
    (directory / "legacy-map.json").write_text(json.dumps(legacy))
    (directory / "foundation.json").write_text(json.dumps(config))
    with contextlib.redirect_stdout(io.StringIO()):
        seed = AoE2DEScenario.from_default("1.59")
        seed.write_to_file(str(directory / "format-seed.aoe2scenario"))
    return tmp_path


def test_isolated_stock_map_build_reload_and_repeatability(map_project):
    from ancienttdde.generation.build import build_map, validate_build

    first = build_map(map_project)
    directory = map_project / ".build/map"
    scenario = directory / "ancient-td-de-map.aoe2scenario"
    reloaded = inspect_scenario(scenario, include_terrain=True)
    assert reloaded["scenario_version"] == "1.59"
    assert reloaded["map"]["width"] == reloaded["map"]["height"] == 16
    assert reloaded["map"]["tiles"][7 * 16 + 3] == [4, 2, 0]
    assert reloaded["map"]["tiles"][2 * 16 + 12] == [0, 0, -1]
    assert reloaded["triggers"] == []
    assert reloaded["victory_condition"] == 4
    assert reloaded["external_xs"] == ""
    units = {u["reference_id"]: u for u in reloaded["units"]}
    assert units[0]["unit_const"] == 1776
    assert units[14]["garrisoned_in_id"] == 13
    assert units[12]["caption_string"] == "+4 attack: 1 King"
    assert reloaded["players"][1]["civilization"] == "RANDOM"
    assert reloaded["players"][1]["disabled_units"] == []
    assert all(p["active"] for p in reloaded["players"][1:])
    assert all(p["human"] for p in reloaded["players"][1:8])
    assert reloaded["players"][8]["human"] is False
    second = build_map(map_project, map_project / ".build/repeat")
    assert first["normalized_sha256"] == second["normalized_sha256"]
    assert first["inputs"] == second["inputs"]
    assert validate_build(directory, map_project)["normalized_sha256"] == first["normalized_sha256"]


def test_build_cli_and_validation_work_from_plain_data_without_original_package(map_project):
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
def test_validation_rejects_stale_map_inputs(map_project, filename):
    from ancienttdde.generation.build import build_map, validate_build

    build_map(map_project)
    with (map_project / "content/maps" / filename).open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(ValueError, match="input SHA-256"):
        validate_build(map_project / ".build/map", map_project)


def test_validation_reloads_scenario_even_when_hashes_have_been_updated(map_project):
    from ancienttdde.generation.build import build_map, validate_build

    build_map(map_project)
    directory = map_project / ".build/map"
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(scenario_path))
        scenario.unit_manager.units[0][0].unit_const = 9999
        edited = directory / "edited.aoe2scenario"
        scenario.write_to_file(str(edited))
        edited.replace(scenario_path)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["artifacts"]:
        if record["path"] == scenario_path.name:
            record["sha256"] = hash_file(scenario_path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="(unreviewed|Reloaded|normalized)"):
        validate_build(directory, map_project)


def test_reload_rejects_extra_placement_with_duplicate_instance_id(map_project):
    from ancienttdde.generation.build import build_map, check_reload

    build_map(map_project)
    directory = map_project / ".build/map"
    expected = json.loads((directory / "map.json").read_text())
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(scenario_path))
        # Gaia is inspected before player 1, whose life marker also has ID 10.
        scenario.unit_manager.add_unit(player=0, unit_const=9999, reference_id=10, x=1.5, y=8.5)
        edited = directory / "duplicate.aoe2scenario"
        scenario.write_to_file(str(edited))
    with pytest.raises(ValueError, match="(placement count|unique)"):
        check_reload(edited, expected)


def test_new_units_receive_unique_ids_after_loading_built_map(map_project):
    from ancienttdde.generation.build import build_map

    build_map(map_project)
    scenario_path = map_project / ".build/map/ancient-td-de-map.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(scenario_path))
        original_ids = {unit.reference_id for unit in scenario.unit_manager.get_all_units()}
        added = scenario.unit_manager.add_unit(player=0, unit_const=83, x=1.5, y=8.5)
        assert added.reference_id > max(original_ids)
        edited = scenario_path.with_name("extended.aoe2scenario")
        scenario.write_to_file(str(edited))
    reloaded = inspect_scenario(edited)
    identifiers = [unit["reference_id"] for unit in reloaded["units"]]
    assert len(set(identifiers)) == len(original_ids) + 1
    assert reloaded["next_unit_id"] > added.reference_id


def test_reload_rejects_allocator_below_existing_instance_ids(map_project):
    from ancienttdde.generation.build import build_map, check_reload

    build_map(map_project)
    directory = map_project / ".build/map"
    expected = json.loads((directory / "map.json").read_text())
    scenario_path = directory / "ancient-td-de-map.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(scenario_path))
        scenario.unit_manager.reference_id_generator = (identifier for identifier in range(100))
        edited = directory / "unsafe-allocator.aoe2scenario"
        scenario.write_to_file(str(edited))
    with pytest.raises(ValueError, match="allocator"):
        check_reload(edited, expected)


def test_build_rejects_source_directories_and_nonempty_seeds(map_project):
    from ancienttdde.generation.build import build_map

    with pytest.raises(ValueError, match="source"):
        build_map(map_project, map_project / "content/generated")
    seed_path = map_project / "content/maps/format-seed.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        seed = AoE2DEScenario.from_file(str(seed_path))
        seed.unit_manager.add_unit(player=1, unit_const=83, x=1.5, y=1.5)
        edited = seed_path.with_name("nonempty.aoe2scenario")
        seed.write_to_file(str(edited))
        edited.replace(seed_path)
    with pytest.raises(ValueError, match="empty"):
        build_map(map_project)


@pytest.mark.parametrize("filename", ["anchors.json", "validation.json"])
def test_validation_checks_sidecar_contents_after_manifest_hashes_are_updated(
    map_project, filename
):
    from ancienttdde.generation.build import build_map, validate_build

    build_map(map_project)
    directory = map_project / ".build/map"
    artifact = directory / filename
    artifact.write_text("{}")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["artifacts"]:
        if record["path"] == filename:
            record["sha256"] = hash_file(artifact)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="sidecar"):
        validate_build(directory, map_project)


def test_legacy_map_extraction_records_provenance_without_copying_logic(tmp_path):
    from ancienttdde.inspection.map import extract_map

    source = tmp_path / "legacy.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_default()
        scenario.map_manager.map_size = 16
        scenario.map_manager.get_tile(x=3, y=7).elevation = 2
        scenario.unit_manager.add_unit(player=0, unit_const=66, x=3.5, y=7.5)
        scenario.trigger_manager.add_trigger("Legacy logic must not migrate")
        scenario.write_to_file(str(source))
    result = extract_map(source, source_name="original.aoe2scenario")
    assert result["source"] == {"path": "original.aoe2scenario", "sha256": hash_file(source)}
    assert len(result["map"]["tiles"]) == 256
    assert result["map"]["tiles"][7 * 16 + 3][1] == 2
    assert len(result["units"]) == 1
    assert "triggers" not in result
