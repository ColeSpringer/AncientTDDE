"""Worker: construct the playable game over the migrated stock-DE map, and its XS prelude."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.common.data import object_value, read_object
from ancienttdde.common.worker import capture_stdout_for_errors
from ancienttdde.game.catalog import Shop, load_shop
from ancienttdde.game.civilizations import Profiles, load_profiles
from ancienttdde.game.config import Balance, EngineLane, Interaction, load_balance, load_lanes
from ancienttdde.game.controls import CONTROLS
from ancienttdde.game.economy import endless_deposits
from ancienttdde.game.instructions import instructions
from ancienttdde.game.interaction import pvp_diplomacy, siege_countdowns
from ancienttdde.game.labels import name_objects
from ancienttdde.game.lanes import lane_actions
from ancienttdde.game.objectives import run_objectives
from ancienttdde.game.restrictions import restrict_competitive
from ancienttdde.game.script import render_prelude, render_xs
from ancienttdde.game.selection import (
    chooser_view,
    options_objectives,
    place_controls,
    retire_controls,
)
from ancienttdde.game.shop import caption_displays, place_displays, remove_shop_signs
from ancienttdde.game.sites import numbers
from ancienttdde.game.spawns import creation_tiles
from ancienttdde.game.stock import load_stock
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import (
    configure_waves,
    declare_results,
    endless_growth,
    endless_lumber,
    game_clock,
    game_status,
    wave_warnings,
)
from ancienttdde.map.construct import construct_scenario
from ancienttdde.map.models import MapAnchor
from ancienttdde.scenario.objects import marker_flags
from ancienttdde.scenario.settings import (
    disable_automatic_victory,
    embed_passive_ai,
    lock_lobby_options,
    reset_player,
)
from ancienttdde.scenario.triggers import effect
from ancienttdde.scenario.xs import check_xs, xs_checker


def clear_sites(
    game: Game, lanes: tuple[EngineLane, ...], shop: Shop, interaction: Interaction
) -> None:
    """Take the map's marker flags off the tiles the XS creates units on.

    Creation checks collisions, and DE gives even a flag an obstruction. Anything else on
    those tiles is a content error.
    """
    flags = marker_flags()
    for lane in lanes:
        tiles = creation_tiles(lane, shop, interaction)
        for placed in game.scenario.unit_manager.units:
            for unit in list(placed):
                tile = (int(unit.x), int(unit.y))
                if tile not in tiles:
                    continue
                if unit.unit_const not in flags:
                    raise ValueError(f"Object {unit.unit_const} blocks a creation tile {tile}")
                placed.remove(unit)
                game.placements.discard(unit.reference_id)


def remove_selectors(game: Game, lanes: tuple[EngineLane, ...]) -> None:
    """Take out the original's difficulty selectors: player Outposts that show no lives."""
    lives = {lane.life_reference for lane in lanes}
    outpost = game.stock("outpost")
    for placed in game.scenario.unit_manager.units[1:8]:
        for unit in [u for u in placed if u.unit_const == outpost]:
            if unit.reference_id not in lives:
                placed.remove(unit)
                game.placements.discard(unit.reference_id)


def settings(
    game: Game,
    balance: Balance,
    lanes: tuple[EngineLane, ...],
    shop: Shop,
    anchors: dict[str, object],
) -> None:
    scenario = game.scenario
    clear_sites(game, lanes, shop, balance.interaction)
    remove_shop_signs(game, shop)
    remove_selectors(game, lanes)
    place_displays(game, shop)
    caption_displays(game, shop)
    place_controls(game, anchors, balance)
    keeper = keeper_point(anchors)
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
    # A protected counted unit keeps the scenario-controlled enemy alive between waves.
    king = scenario.unit_manager.add_unit(
        player=8, unit_const=game.stock("king"), x=keeper[0], y=keeper[1]
    )
    game.names.register("object", "enemy.keeper", king.reference_id)
    init = game.trigger("game.initialize", looping=False)
    game.protect(init, [king.reference_id])
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
    # The lanes' population yurts stand beside the trade channel, outside every combat area.
    yurts = {game.stock("yurt"), game.stock("wide-yurt")}
    game.protect(
        init,
        [
            u.reference_id
            for placed in scenario.unit_manager.units[1:8]
            for u in placed
            if u.unit_const in yurts
        ],
    )
    game.protect(init, [game.names.resolve("object", f"control.{c.key}") for c in CONTROLS])


def keeper_point(anchors: dict[str, object]) -> tuple[float, float]:
    """The isolated islet where the enemy's protected King waits, away from every siege spot."""
    x, y = numbers(
        object_value(anchors.get("enemy.keeper"), "enemy.keeper").get("point"), "enemy.keeper", 2
    )
    return x, y


def add_logic(
    game: Game,
    balance: Balance,
    lanes: tuple[EngineLane, ...],
    shop: Shop,
    profiles: Profiles,
    anchors: dict[str, object],
) -> None:
    endless_lumber(game, lanes)
    endless_deposits(game, balance)
    name_objects(game, lanes, shop, balance)
    game_clock(game)
    game_status(game, balance)
    run_objectives(game)
    options_objectives(game, balance)
    chooser_view(game, anchors)
    configure_waves(game, balance)
    endless_growth(game, balance)
    wave_warnings(game, balance)
    pvp_diplomacy(game)
    siege_countdowns(game, balance)
    retire_controls(game)
    restrict_competitive(game)
    for lane in lanes:
        lane_actions(game, lane, balance, shop, profiles)
    declare_results(game)


def construct_game(root: Path, map_path: Path, destination: Path, prelude: Path) -> None:
    balance = load_balance(root / "content/balance/game.json")
    anchors = object_value(read_object(map_path).get("anchors"), "anchors")
    lanes = load_lanes(anchors)
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(
        root / "content/balance/shop.json", cast(dict[str, MapAnchor], anchors), families
    )
    stock = load_stock(root / "content/balance/stock.json")
    stock.check_waves(balance)
    profiles = load_profiles(root / "content/balance/civilizations.json", balance, shop, stock)
    with TemporaryDirectory(prefix="ancienttdde-map-") as temporary:
        foundation = Path(temporary) / "foundation.aoe2scenario"
        construct_scenario(root / "content/maps/format-seed.aoe2scenario", map_path, foundation)
        scenario = AoE2DEScenario.from_file(str(foundation))
    game = Game(scenario)
    settings(game, balance, lanes, shop, anchors)
    scenario.xs_manager.add_script(xs_string=render_xs(balance, lanes, shop, profiles))
    prelude.write_text(
        render_prelude(balance, lanes, shop, profiles, extern=True), encoding="utf-8"
    )
    add_logic(game, balance, lanes, shop, profiles, anchors)
    scenario.message_manager.instructions = instructions(balance, shop, profiles).replace(
        "\n", "\r"
    )
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
        scenario.write_to_file(str(destination))
    check_xs(AoE2DEScenario.from_file(str(destination)))


if __name__ == "__main__":
    with capture_stdout_for_errors():
        if sys.argv[1] == "--check-xs":
            check_xs(AoE2DEScenario.from_file(sys.argv[2]))
        else:
            construct_game(
                Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
            )
