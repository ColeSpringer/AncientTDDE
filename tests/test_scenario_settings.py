"""Scenario settings the game and the probes share."""

import pytest
from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from conftest import new_scenario

from ancienttdde.common.data import asset_text
from ancienttdde.scenario.settings import (
    disable_automatic_victory,
    embed_passive_ai,
    lock_lobby_options,
    reset_player,
)


@pytest.fixture
def scenario() -> AoE2DEScenario:
    return new_scenario("1.59")


def test_automatic_victory_is_disabled_without_requiring_custom_conditions(
    scenario: AoE2DEScenario,
) -> None:
    victory = scenario.sections["GlobalVictory"]
    victory.conquest_required = 1
    victory.gold_required = 500
    disable_automatic_victory(scenario)
    assert scenario.option_manager.victory_condition == 4
    assert not scenario.option_manager.victory_custom_conditions_required
    assert {
        victory.conquest_required,
        victory.ruins,
        victory.artifacts_required,
        victory.discovery,
        victory.explored_percent_of_map_required,
        victory.gold_required,
    } == {0}


def test_lobby_options_keep_fixed_teams_and_standard_technology(scenario: AoE2DEScenario) -> None:
    lock_lobby_options(scenario)
    options = scenario.option_manager
    assert options.lock_teams and not options.allow_players_choose_teams
    assert not options.random_start_points and not options.legacy_execution_order
    assert options.secondary_game_modes == 0
    assert scenario.sections["Options"].all_techs == 0


def test_passive_ai_is_embedded_only_in_the_requested_slots(scenario: AoE2DEScenario) -> None:
    data = scenario.sections["PlayerDataTwo"]
    embed_passive_ai(scenario, range(1, 8))
    assert data.ai_names[0] != "Ancient TD Passive"
    assert all(data.ai_names[slot] == "Ancient TD Passive" for slot in range(1, 8))
    assert all(
        data.ai_files[slot].ai_per_file_text == asset_text("passive.per") for slot in range(1, 8)
    )
    assert all(data.ai_type[slot] == 0 for slot in range(1, 8))


def test_players_are_reset_to_an_empty_controlled_start(scenario: AoE2DEScenario) -> None:
    player = scenario.player_manager.players[3]
    player.food = 500
    reset_player(
        player,
        human=False,
        civilization="BRITONS",
        lock_personality=True,
        starting_age=StartingAge.DARK_AGE,
    )
    assert (player.human, player.lock_civ, player.lock_personality) == (False, False, True)
    assert player.starting_age == StartingAge.DARK_AGE
    assert (player.population_cap, player.allied_victory) == (200, False)
    assert (player.food, player.wood, player.gold, player.stone) == (0, 0, 0, 0)
