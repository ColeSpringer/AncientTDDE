"""Scenario settings the game and the probes share."""

from pathlib import Path

import pytest
from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from conftest import DE_RULE_SIZE, ai_rules, new_scenario

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


# The strategic numbers DE's own AI scripts name; DE rejects a script naming any other.
DE_NAMES = Path(__file__).parent / "support/de-strategic-numbers.txt"
DE_STRATEGIC_NUMBERS = frozenset(
    line.strip() for line in DE_NAMES.read_text().splitlines() if line.strip()[:1] not in ("", "#")
)


def test_ai_rules_count_nested_facts_and_skip_strings_and_comments() -> None:
    script = """; a comment with (brackets) and => an arrow
    (defrule (or (a 1) (b)) ; (c)
    => (chat-to-all "x; (y") (disable-self))
    (defrule (true) => (set-strategic-number sn-x 0))"""
    assert ai_rules(script) == [
        ([["or"], ["a", "1"], ["b"]], [["chat-to-all"], ["disable-self"]]),
        ([["true"]], [["set-strategic-number", "sn-x", "0"]]),
    ]


def test_passive_ai_rules_fit_des_rule_size() -> None:
    rules = ai_rules(asset_text("passive.per"))
    assert rules
    assert all(len(facts) + len(actions) <= DE_RULE_SIZE for facts, actions in rules)


def test_passive_ai_switches_off_the_engines_unit_management() -> None:
    """DE manages a computer player's units itself unless its script zeroes these numbers:
    online its explorer share ordered wave villagers about their lane."""
    rules = ai_rules(asset_text("passive.per"))
    assert all(facts == [["true"]] and actions[-1] == ["disable-self"] for facts, actions in rules)
    numbers = [action for _, actions in rules for action in actions[:-1]]
    assert all(action[0] == "set-strategic-number" for action in numbers)
    named = [(name, int(value)) for _, name, value in numbers]
    settings = dict(named)
    assert len(settings) == len(named)
    assert set(settings) <= DE_STRATEGIC_NUMBERS
    assert settings == {
        "sn-percent-civilian-explorers": 0,
        "sn-cap-civilian-explorers": 0,
        "sn-minimum-civilian-explorers": 0,
        "sn-total-number-explorers": 0,
        "sn-number-explore-groups": 0,
        "sn-number-boat-explore-groups": 0,
        "sn-percent-civilian-builders": 0,
        "sn-cap-civilian-builders": 0,
        "sn-percent-civilian-gatherers": 0,
        "sn-cap-civilian-gatherers": 0,
        "sn-number-civilian-militia": 0,
        "sn-allow-civilian-defense": 0,
        "sn-allow-civilian-offense": 0,
        "sn-disable-villager-garrison": 3,
        "sn-number-garrison-units": 0,
        "sn-maximum-garrison-fill": 0,
        "sn-garrison-rams": 0,
        "sn-number-attack-groups": 0,
        "sn-number-boat-attack-groups": 0,
        "sn-disable-attack-groups": 1,
        "sn-number-defend-groups": 0,
        "sn-disable-defend-groups": 1,
        "sn-task-ungrouped-soldiers": 0,
        "sn-gather-defense-units": 0,
        "sn-gather-idle-soldiers-at-center": 0,
        "sn-percent-enemy-sighted-response": 0,
        "sn-enemy-sighted-response-distance": 0,
        "sn-sentry-distance": 0,
        "sn-maximum-gaia-attack-response": 0,
        "sn-disable-trade-evasion": 1,
        "sn-do-not-scale-for-difficulty-level": 1,
    }


def test_the_builds_rules_follow_the_passive_ai(scenario: AoE2DEScenario) -> None:
    rules = "(defrule\n    (true)\n=>\n    (disable-self)\n)\n"
    embed_passive_ai(scenario, range(1, 8), rules)
    data = scenario.sections["PlayerDataTwo"]
    assert data.ai_files[1].ai_per_file_text == asset_text("passive.per") + rules
