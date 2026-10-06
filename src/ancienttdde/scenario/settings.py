"""Scenario settings the playable game and the mechanic probes share."""

from collections.abc import Iterable
from typing import Protocol

from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.common.data import asset_text


class Player(Protocol):
    """The parser's player fields a reset writes."""

    human: bool
    lock_civ: bool
    lock_personality: bool
    starting_age: int
    population_cap: int | None
    allied_victory: bool | None
    food: int
    wood: int
    gold: int
    stone: int

    @property
    def civilization(self) -> object: ...
    @civilization.setter
    def civilization(self, value: str) -> None: ...


def disable_automatic_victory(scenario: AoE2DEScenario) -> None:
    scenario.option_manager.victory_condition = VictoryCondition.CUSTOM
    scenario.option_manager.victory_custom_conditions_required = False
    victory = scenario.sections["GlobalVictory"]
    # Custom victory does not clear the seed's Conquest checkbox; left on, it ends the game
    # as soon as every enemy is defeated, including players defeated at the start.
    victory.conquest_required = victory.ruins = victory.artifacts_required = 0
    victory.discovery = victory.explored_percent_of_map_required = victory.gold_required = 0


def lock_lobby_options(scenario: AoE2DEScenario) -> None:
    scenario.option_manager.lock_teams = True
    scenario.option_manager.allow_players_choose_teams = False
    scenario.option_manager.random_start_points = False
    scenario.option_manager.secondary_game_modes = 0
    scenario.option_manager.legacy_execution_order = False
    scenario.sections["Options"].all_techs = 0


def embed_passive_ai(scenario: AoE2DEScenario, slots: Iterable[int]) -> None:
    passive = asset_text("passive.per")
    data = scenario.sections["PlayerDataTwo"]
    for slot in slots:
        data.ai_names[slot] = "Ancient TD Passive"
        data.ai_files[slot].ai_per_file_text = passive
        # The embedded name and script take effect only with the custom AI type, 0.
        data.ai_type[slot] = 0


def reset_player(
    player: Player, *, human: bool, civilization: str, lock_personality: bool, starting_age: int
) -> None:
    """Start the player with no stockpile, a 200 population cap and no allied victory."""
    player.human = human
    player.civilization = civilization
    player.lock_civ = False
    player.lock_personality = lock_personality
    player.starting_age = starting_age
    player.population_cap = 200
    player.allied_victory = False
    player.food = player.wood = player.gold = player.stone = 0
