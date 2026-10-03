import contextlib
import io
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.inspection.scenario import inspect_scenario


def test_isolated_extraction_keeps_zero_ids_negatives_order_and_messages(tmp_path):
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_default()
        first = scenario.trigger_manager.add_trigger("Income")
        first.new_effect.tribute(quantity=-125, tribute_list=2, source_player=1, target_player=0)
        second = scenario.trigger_manager.add_trigger("Begin")
        second.new_effect.activate_trigger(trigger_id=first.trigger_id)
        scenario.trigger_manager.trigger_display_order = [1, 0]
        scenario.message_manager.hints = "The displayed rules\rwith a second line."
        scenario.unit_manager.add_unit(player=0, unit_const=79, x=8, y=14)
        scenario.trigger_manager.add_variable("life.p1", variable_id=0)
        source = tmp_path / "fixture.aoe2scenario"
        scenario.write_to_file(str(source))
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


def test_real_legacy_regression_when_original_is_available():
    source = Path(
        "legacy/original/resources/_common/scenario/++ Ancient TD v5.3 ++ By DRAX.aoe2scenario"
    )
    if not source.is_file():
        import pytest

        pytest.skip("Original package is intentionally not committed")
    result = inspect_scenario(source)
    assert result["scenario_version"] == "1.49"
    assert result["map"]["width"] == result["map"]["height"] == 200
    assert len(result["triggers"]) == 1018
    assert len(result["units"]) == 7395
    assert result["players"][8]["civilization"] == "PERSIANS"
    assert result["triggers"][485]["effects"][4]["type"] == "deactivate_trigger"
    assert result["triggers"][485]["effects"][4]["attributes"]["trigger_id"] == 34
    assert result["triggers"][1010]["conditions"][0]["attributes"]["timer"] == 70
