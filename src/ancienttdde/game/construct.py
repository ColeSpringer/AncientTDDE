"""Worker: construct the playable game over the migrated stock-DE map, and its XS prelude."""

import sys
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.other import OtherInfo
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
from ancienttdde.game.interaction import open_pvp_pads, pvp_diplomacy, siege_countdowns
from ancienttdde.game.labels import caption_transfers, name_objects
from ancienttdde.game.lanes import lane_actions
from ancienttdde.game.objectives import hide_on_stop, run_objectives
from ancienttdde.game.restrictions import restrict_competitive
from ancienttdde.game.script import render_prelude, render_xs
from ancienttdde.game.selection import (
    chooser_view,
    options_objectives,
    place_controls,
    retire_controls,
    trim_controls,
)
from ancienttdde.game.shop import (
    caption_displays,
    place_displays,
    place_gates,
    remove_shop_signs,
)
from ancienttdde.game.sites import Tile, numbers
from ancienttdde.game.spawns import creation_tiles, marked_tiles
from ancienttdde.game.stock import load_stock
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import (
    declare_results,
    enemy_diplomacy,
    game_clock,
    game_status,
    wave_warnings,
)
from ancienttdde.map.build import read_content
from ancienttdde.map.construct import construct_scenario
from ancienttdde.map.geometry import blocking_sizes, cells, footprint
from ancienttdde.map.models import MapAnchor
from ancienttdde.models import Rect
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
    """Take the map's marker flags off the tiles units are created on, the King stall, the
    siege islets and the starting tower sites among them; the transfer arrivals and bought
    villagers' spots keep the original's flags. Anything else on those tiles is a content
    error.
    """
    flags = marker_flags()
    for lane in lanes:
        tiles = creation_tiles(lane, shop, interaction)
        marked = marked_tiles(lane)
        for placed in game.scenario.unit_manager.units:
            for unit in list(placed):
                tile = (int(unit.x), int(unit.y))
                if tile not in tiles:
                    continue
                if unit.unit_const not in flags:
                    raise ValueError(f"Object {unit.unit_const} blocks a creation tile {tile}")
                if tile in marked:
                    continue
                placed.remove(unit)
                game.placements.discard(unit.reference_id)


def pad_rows(key: str, region: Rect, open_tiles: set[Tile], taken: set[Tile]) -> list[list[Tile]]:
    """A pad's open tiles in rows across it, the row farthest from its entrance first, each
    in ascending order. The entrance is the side with the most free tiles just outside the
    pad beside an open one."""
    x1, y1, x2, y2 = region
    outside = {
        "west": [(x1 - 1, y) for x, y in open_tiles if x == x1],
        "east": [(x2 + 1, y) for x, y in open_tiles if x == x2],
        "north": [(x, y1 - 1) for x, y in open_tiles if y == y1],
        "south": [(x, y2 + 1) for x, y in open_tiles if y == y2],
    }
    free = {side: sum(tile not in taken for tile in tiles) for side, tiles in outside.items()}
    entrances = [side for side, count in free.items() if count == max(free.values())]
    if len(entrances) != 1:
        raise ValueError(f"{key} pad has no single entrance")
    [side] = entrances
    across = side in ("west", "east")
    rows: dict[int, list[Tile]] = {}
    for tile in open_tiles:
        rows.setdefault(tile[0] if across else tile[1], []).append(tile)
    return [sorted(rows[r]) for r in sorted(rows, reverse=side in ("west", "north"))]


def far_end(rows: list[list[Tile]], kings: int) -> set[Tile]:
    """Whole rows from the far end, then the first tiles of the next; a lone flag takes its
    row's middle tile, the first of two."""
    wanted: list[Tile] = []
    for row in rows:
        left = kings - len(wanted)
        if left <= 0:
            break
        if left >= len(row):
            wanted += row
        elif left == 1:
            wanted.append(row[(len(row) - 1) // 2])
        else:
            wanted += row[:left]
    return set(wanted)


def fills_far_end(rows: list[list[Tile]], flagged: set[Tile]) -> bool:
    """Whether the flags stand on open tiles and fill every row beyond the nearest flagged
    one."""
    depth = {tile: index for index, row in enumerate(rows) for tile in row}
    if not flagged or not flagged <= depth.keys():
        return False
    nearest = max(depth[tile] for tile in flagged)
    return all(set(row) <= flagged for row in rows[:nearest])


def entrance_obstacles(game: Game, blocked: set[Tile]) -> set[Tile]:
    """Tiles a King cannot step in from: those placed objects block or stand on, but for
    marker flags, which have no collision."""
    flags = marker_flags()
    return blocked | {
        (int(unit.x), int(unit.y))
        for unit in game.scenario.unit_manager.get_all_units()
        if unit.unit_const not in flags
    }


def reconcile_pad_flags(
    game: Game,
    lanes: tuple[EngineLane, ...],
    shop: Shop,
    interaction: Interaction,
    sizes: Mapping[int, int],
) -> dict[str, list[list[Tile]]]:
    """Give each pad one Gaia flag per King of its price, the siege's base price: the map's
    flags were placed for the original's prices. As in the original, the flags fill whole
    rows from the end farthest from the pad's entrance; a pad whose flags already do keeps
    them. A tile keeps one flag. Returns each pad's rows, the farthest first."""
    flags = marker_flags()
    placed = game.scenario.unit_manager.units
    # Every marker flag's reference ID, by tile.
    marked: dict[Tile, list[int]] = {}
    for owned in placed:
        for unit in owned:
            if unit.unit_const in flags:
                marked.setdefault((int(unit.x), int(unit.y)), []).append(unit.reference_id)
    reserved = {tile for lane in lanes for tile in creation_tiles(lane, shop, interaction)}
    blocked = {
        cell
        for owned in placed
        for unit in owned
        for cell in footprint({"x": unit.x, "y": unit.y}, sizes.get(unit.unit_const, 0))
    }
    taken = entrance_obstacles(game, blocked)
    doomed: set[int] = set()
    layouts: dict[str, list[list[Tile]]] = {}
    for purchase in shop.purchases:
        region = cells(purchase.pad_region)
        rows = pad_rows(purchase.key, purchase.pad_region, region - blocked - reserved, taken)
        layouts[purchase.key] = rows
        flagged = {tile for tile in region if tile in marked}
        for tile in flagged:
            doomed.update(marked[tile][1:])
        wanted = flagged
        if len(flagged) != purchase.kings or not fills_far_end(rows, flagged):
            wanted = far_end(rows, purchase.kings)
            if len(wanted) < purchase.kings:
                raise ValueError(f"The {purchase.key} pad has no room for {purchase.kings} flags")
        for tile in flagged - wanted:
            doomed.add(marked[tile][0])
        for x, y in sorted(wanted - flagged):
            flag = game.scenario.unit_manager.add_unit(
                player=0, unit_const=OtherInfo["FLAG_B"].ID, x=x + 0.5, y=y + 0.5
            )
            game.placements.add(flag.reference_id)
    for owned in placed:
        for unit in [u for u in owned if u.reference_id in doomed]:
            owned.remove(unit)
            game.placements.discard(unit.reference_id)
    return layouts


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
    sizes: Mapping[int, int],
) -> None:
    scenario = game.scenario
    clear_sites(game, lanes, shop, balance.interaction)
    # Before the pad flags, whose layout reads each pad's open entrance.
    remove_shop_signs(game, shop)
    remove_selectors(game, lanes)
    rows = reconcile_pad_flags(game, lanes, shop, balance.interaction, sizes)
    place_displays(game, shop)
    place_gates(game, shop, rows)
    caption_displays(game, shop)
    caption_transfers(game, lanes)
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
        # The original's one-way alliance with the enemy in its usual slot: lanes shoot the
        # enemy's units, and the enemy treats every lane as an ally, so its units attack nothing
        # while the lanes' towers fire at them. The enemy's trigger sets the same for whichever
        # number it holds.
        diplomacy: list[int] = [DiplomacyState.NEUTRAL] * 16
        if player.human:
            diplomacy[7] = DiplomacyState.ENEMY
        else:
            diplomacy[:7] = [DiplomacyState.ALLY] * 7
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
    endless_deposits(game, balance)
    name_objects(game, lanes, shop, balance)
    game_clock(game)
    game_status(game, balance)
    run_objectives(game)
    options_objectives(game, balance)
    chooser_view(game, anchors)
    wave_warnings(game, balance)
    enemy_diplomacy(game)
    pvp_diplomacy(game)
    open_pvp_pads(game, shop)
    siege_countdowns(game, balance)
    trim_controls(game)
    retire_controls(game)
    restrict_competitive(game)
    for lane in lanes:
        lane_actions(game, lane, balance, shop, profiles)
    hide_on_stop(game)
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
    _, config = read_content(root)
    sizes = blocking_sizes(config)
    settings(game, balance, lanes, shop, anchors, sizes)
    scenario.xs_manager.add_script(xs_string=render_xs(balance, lanes, shop, profiles, stock))
    prelude.write_text(
        render_prelude(balance, lanes, shop, profiles, stock, extern=True), encoding="utf-8"
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
