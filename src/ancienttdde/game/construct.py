"""Worker: construct the playable game over the migrated stock-DE map."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.common.data import object_value, read_object
from ancienttdde.common.worker import capture_stdout_for_errors
from ancienttdde.game.config import Balance, EngineLane, load_balance, load_lanes
from ancienttdde.game.instructions import instructions
from ancienttdde.game.lanes import lane_actions
from ancienttdde.game.script import render_xs
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import configure_waves, declare_results, endless_lumber, game_clock
from ancienttdde.map.construct import construct_scenario
from ancienttdde.scenario.settings import (
    disable_automatic_victory,
    embed_passive_ai,
    lock_lobby_options,
    reset_player,
)
from ancienttdde.scenario.triggers import effect
from ancienttdde.scenario.xs import check_xs, xs_checker


def settings(game: Game) -> None:
    scenario = game.scenario
    scenario.player_manager.active_players = 8
    for player in scenario.player_manager.players[1:]:
        human = player.player_id != 8
        reset_player(
            player,
            human=human,
            civilization="RANDOM" if human else "BRITONS",
            lock_personality=True,
            starting_age=StartingAge.FEUDAL_AGE,
        )
        diplomacy: list[int] = [DiplomacyState.NEUTRAL] * 16
        diplomacy[7] = DiplomacyState.ENEMY
        if not player.human:
            diplomacy[:7] = [DiplomacyState.ENEMY] * 7
        diplomacy[player.player_id - 1] = DiplomacyState.ALLY
        player.diplomacy = diplomacy
    disable_automatic_victory(scenario)
    lock_lobby_options(scenario)
    scenario.xs_manager.script_name = ""
    embed_passive_ai(scenario, range(8))
    for unit in scenario.unit_manager.units[0]:
        # Gaia trade endpoints and displays must not convert to a nearby player.
        unit.capture_flag = CaptureFlag.NEVER
        if unit.unit_const == game.stock("sign"):
            unit.caption_string = "Shop closed; build towers with your lane villagers"
    # A protected counted unit keeps the scenario-controlled enemy alive between waves.
    keeper = scenario.unit_manager.add_unit(player=8, unit_const=game.stock("king"), x=25.5, y=2.5)
    game.names.register("object", "enemy.keeper", keeper.reference_id)
    init = game.trigger("game.initialize", looping=False)
    game.protect(init, [keeper.reference_id])
    effect(
        init,
        "modify_attribute",
        source_player=8,
        object_list_unit_id=game.stock("king"),
        object_attributes=ObjectAttribute.MOVEMENT_SPEED,
        quantity=0,
        operation=Operation.SET,
    )
    endpoints = {game.stock("market"), game.stock("dock")}
    game.protect(
        init,
        [u.reference_id for u in scenario.unit_manager.units[0] if u.unit_const in endpoints],
    )


def add_logic(game: Game, balance: Balance, lanes: tuple[EngineLane, ...]) -> None:
    endless_lumber(game, lanes)
    game_clock(game)
    configure_waves(game, balance)
    for lane in lanes:
        lane_actions(game, lane, balance)
    declare_results(game)


def construct_game(root: Path, map_path: Path, destination: Path) -> None:
    balance = load_balance(root / "content/balance/game.json")
    lanes = load_lanes(object_value(read_object(map_path).get("anchors"), "anchors"))
    with TemporaryDirectory(prefix="ancienttdde-map-") as temporary:
        foundation = Path(temporary) / "foundation.aoe2scenario"
        construct_scenario(root / "content/maps/format-seed.aoe2scenario", map_path, foundation)
        scenario = AoE2DEScenario.from_file(str(foundation))
    game = Game(scenario)
    settings(game)
    scenario.xs_manager.add_script(xs_string=render_xs(balance, lanes))
    add_logic(game, balance, lanes)
    scenario.message_manager.instructions = instructions(balance).replace("\n", "\r")
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
        scenario.write_to_file(str(destination))
    check_xs(AoE2DEScenario.from_file(str(destination)))


if __name__ == "__main__":
    with capture_stdout_for_errors():
        if sys.argv[1] == "--check-xs":
            check_xs(AoE2DEScenario.from_file(sys.argv[2]))
        else:
            construct_game(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
