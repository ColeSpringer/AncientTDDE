from pathlib import Path

import pytest
from conftest import ROOT, new_scenario, save_scenario, tiles

from ancienttdde.scenario.inspect import inspect_scenario


def test_map_extraction_preserves_tile_order_elevation_and_placements(tmp_path: Path) -> None:
    scenario = new_scenario()
    scenario.map_manager.map_size = 16
    tile = scenario.map_manager.get_tile(x=3, y=7)
    tile.terrain_id = 4
    tile.elevation = 2
    tile.layer = 0
    scenario.unit_manager.add_unit(
        player=0, unit_const=66, x=3.5, y=7.5, reference_id=0, rotation=1.5
    )
    source = tmp_path / "map.aoe2scenario"
    save_scenario(scenario, source)
    result = inspect_scenario(source, include_terrain=True)
    assert len(tiles(result)) == 256
    assert tiles(result)[7 * 16 + 3] == [4, 2, 0]
    assert tiles(result)[3 * 16 + 7] == [0, 0, -1]
    assert result["units"][0]["reference_id"] == 0
    assert result["units"][0]["rotation"] == 1.5
    assert "tiles" not in inspect_scenario(source)["map"]


def test_isolated_extraction_keeps_zero_ids_negatives_order_and_messages(tmp_path: Path) -> None:
    scenario = new_scenario()
    first = scenario.trigger_manager.add_trigger("Income")
    first.new_effect.tribute(quantity=-125, tribute_list=2, source_player=1, target_player=0)
    second = scenario.trigger_manager.add_trigger("Begin")
    second.new_effect.activate_trigger(trigger_id=first.trigger_id)
    scenario.trigger_manager.trigger_display_order = [1, 0]
    scenario.message_manager.hints = "The displayed rules\rwith a second line."
    scenario.unit_manager.add_unit(player=0, unit_const=79, x=8, y=14)
    scenario.trigger_manager.add_variable("life.p1", variable_id=0)
    source = tmp_path / "fixture.aoe2scenario"
    save_scenario(scenario, source)
    result = inspect_scenario(source)
    assert result["trigger_display_order"] == [1, 0]
    assert result["triggers"][1]["effects"][0]["attributes"]["trigger_id"] == 0
    effect = result["triggers"][0]["effects"][0]
    assert effect["attributes"]["quantity"] == -125
    assert effect["raw"]["_quantity_int"] == -125
    assert result["messages"]["hints"] == "The displayed rules\rwith a second line."
    assert result["units"][0]["player_id"] == 0
    assert result["variables"][0]["variable_id"] == 0
    assert result["references"]["trigger_ids"] == [0]
    assert 79 in result["references"]["object_ids"]


def test_float_attribute_quantities_come_from_the_stored_float_field(tmp_path: Path) -> None:
    # The parser keeps float attribute values in a separate field and drops a stored 0.0 when
    # it reads a file back, so the snapshot must report the value the file holds.
    scenario = new_scenario()
    speeds = scenario.trigger_manager.add_trigger("Speeds")
    for attribute, quantity in ((5, 0), (5, 0.6), (0, 250)):
        speeds.new_effect.modify_attribute(
            source_player=1,
            object_list_unit_id=434,
            object_attributes=attribute,
            operation=1,
            quantity=quantity,
        )
    source = tmp_path / "speeds.aoe2scenario"
    save_scenario(scenario, source)
    frozen, slowed, toughened = inspect_scenario(source)["triggers"][0]["effects"]
    assert frozen["attributes"]["quantity"] == 0.0
    assert frozen["attributes"]["quantity_float"] == 0.0
    assert frozen["raw"]["_quantity_int"] == -1 and frozen["raw"]["_quantity_float"] == 0.0
    assert slowed["attributes"]["quantity"] == pytest.approx(0.6)
    assert slowed["attributes"]["quantity_float"] == pytest.approx(0.6)
    assert toughened["attributes"]["quantity"] == 250
    assert toughened["attributes"]["quantity_float"] is None
    assert toughened["raw"]["_quantity_float"] is None


def test_real_legacy_regression_when_original_is_available() -> None:
    scenarios = ROOT / "legacy/original/resources/_common/scenario"
    source = scenarios / "++ Ancient TD v5.3 ++ By DRAX.aoe2scenario"
    if not source.is_file():
        pytest.skip("Original package is intentionally not committed")
    result = inspect_scenario(source)
    assert result["scenario_version"] == "1.49"
    assert result["options"]["secondary_game_modes"] == 0
    assert result["options"]["legacy_execution_order"] is None
    assert result["options"]["computer_personalities_locked"] is None
    assert result["map"]["width"] == result["map"]["height"] == 200
    assert len(result["triggers"]) == 1018
    assert len(result["units"]) == 7395
    assert result["players"][8]["civilization"] == "PERSIANS"
    assert result["triggers"][485]["effects"][4]["type"] == "deactivate_trigger"
    assert result["triggers"][485]["effects"][4]["attributes"]["trigger_id"] == 34
    assert result["triggers"][1010]["conditions"][0]["attributes"]["timer"] == 70


def test_game_settings_are_opt_in_for_historical_digest_compatibility(tmp_path: Path) -> None:
    scenario = new_scenario("1.59")
    scenario.player_manager.players[1].lock_personality = True
    scenario.trigger_manager.add_trigger("On load", execute_on_load=True)
    path = tmp_path / "execution.aoe2scenario"
    save_scenario(scenario, path)
    default = inspect_scenario(path)
    assert "execute_on_load" not in default["triggers"][0]
    assert "lock_personality" not in default["players"][1]
    detailed = inspect_scenario(path, include_game_settings=True)
    assert detailed["triggers"][0].get("execute_on_load")
    assert detailed["players"][1].get("lock_personality")
