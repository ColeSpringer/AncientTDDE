"""Wave configuration, spawns, routing, the game clock, results and endless lumber."""

from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.config import MAX_HIT_POINTS, Balance, EngineLane
from ancienttdde.game.objectives import objective
from ancienttdde.game.script import State
from ancienttdde.game.sites import Tile, within
from ancienttdde.game.triggers import Game
from ancienttdde.map.geometry import blocking_sizes, footprint
from ancienttdde.map.models import FoundationConfig, MapDocument
from ancienttdde.models import Rect
from ancienttdde.scenario.triggers import PIERCE, TriggerHandle, area, condition, effect

# Lumber-camp trees hold more wood than a run uses. DE applies this effect value as a
# 16-bit number (1,000,000 arrived as 16,960), so it stays below 32,768.
LUMBER_TREE_WOOD = 32_000
# Seconds between the orders that keep every enemy in a lane walking.
ROUTE_SECONDS = 10


def lumber_trees(game: Game, lane: EngineLane) -> list[Tile]:
    """The tiles of the lane's four placed lumber trees."""
    tree = game.stock("tree")
    placed = [
        (int(u.x), int(u.y))
        for u in game.scenario.unit_manager.units[0]
        if u.unit_const == tree and within(lane.economy, u.x, u.y)
    ]
    return four_trees(lane, placed)


def four_trees(lane: EngineLane, tiles: list[Tile]) -> list[Tile]:
    if len(tiles) != 4:
        raise ValueError(f"P{lane.player} economy needs four lumber trees, found {len(tiles)}")
    return tiles


def check_lumber_room(
    lanes: tuple[EngineLane, ...], data: MapDocument, config: FoundationConfig
) -> None:
    """The tile east of each placed lumber tree, where an endless tree grows, lies under no
    placed object's footprint."""
    sizes = blocking_sizes(config)
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    tree = OtherInfo["TREE_A"].ID
    for lane in lanes:
        placed = [
            (int(u["x"]), int(u["y"]))
            for u in data["units"]
            if u["player_id"] == 0
            and u["unit_const"] == tree
            and within(lane.economy, u["x"], u["y"])
        ]
        for x, y in four_trees(lane, placed):
            if (x + 1, y) in blocked:
                raise ValueError(f"P{lane.player} has no room for an endless tree at {(x + 1, y)}")


def endless_lumber(game: Game, lanes: tuple[EngineLane, ...]) -> None:
    """An endless tree grows behind each placed lumber tree at the start.

    New objects take their owner's current attributes, so the endless trees are created once
    the game runs; the placed trees stay, so the lumberjacks can be sent to them by reference,
    and move on to the endless ones behind them when they are used up.
    """
    trigger = game.trigger("game.lumber", looping=False)
    effect(
        trigger,
        "modify_attribute",
        source_player=0,
        object_list_unit_id=game.stock("tree"),
        object_attributes=ObjectAttribute.AMOUNT_OF_1ST_RESOURCE_STORAGE,
        operation=Operation.SET,
        quantity=LUMBER_TREE_WOOD,
    )
    occupied = {(int(u.x), int(u.y)) for u in game.scenario.unit_manager.get_all_units()}
    for lane in lanes:
        for x, y in lumber_trees(game, lane):
            if (x + 1, y) in occupied:
                raise ValueError(f"P{lane.player} has no room for an endless tree at {(x + 1, y)}")
            effect(
                trigger,
                "create_object",
                source_player=0,
                object_list_unit_id=game.stock("tree"),
                location_x=x + 1,
                location_y=y,
            )


def game_clock(game: Game) -> None:
    clock = game.trigger("game.clock", looping=True)
    condition(clock, "timer", timer=1)
    effect(clock, "script_call", message="void ancientClockEffect() { ancientTick(); }")


def configure_waves(game: Game, balance: Balance) -> None:
    """Each scheduled wave's enemies get the hit points of the difficulty the run plays."""
    for index, wave in enumerate(balance.waves, 1):
        for level, difficulty in enumerate(balance.difficulty.levels):
            configure = game.trigger(f"game.wave.{index}.configure.{difficulty.key}", looping=False)
            game.value(configure, "game.wave", index - 1)
            game.value(configure, "game.difficulty", level)
            # A boss's hit points above the attribute's limit are set on the unit by the XS.
            game.set_attribute(
                configure,
                8,
                wave.object_id,
                ObjectAttribute.HIT_POINTS,
                min(MAX_HIT_POINTS, balance.hit_points(index - 1, level)),
            )
            if wave.pierce_armor is not None:
                effect(
                    configure,
                    "modify_attribute",
                    source_player=8,
                    object_list_unit_id=wave.object_id,
                    object_attributes=ObjectAttribute.ARMOR,
                    operation=Operation.SET,
                    armour_attack_class=PIERCE,
                    armour_attack_quantity=wave.pierce_armor,
                )
            game.set_value(configure, "game.configured", index)


def endless_growth(game: Game, balance: Balance) -> None:
    """Endless enemies take each new level's hit points. The XS adds their armor, which a
    native effect could not raise past 255."""
    units = [balance.waves[t].object_id for t in balance.endless.templates]
    for level in range(1, balance.endless_levels + 1):
        for index, difficulty in enumerate(balance.difficulty.levels):
            grow = game.trigger(f"game.endless.{level}.{difficulty.key}", looping=True)
            game.value(grow, "game.endless_request", level)
            game.value(grow, "game.difficulty", index)
            for position, unit in enumerate(units):
                hit_points = balance.endless_hit_points(level, position, index)
                game.set_attribute(grow, 8, unit, ObjectAttribute.HIT_POINTS, hit_points)
            game.set_value(grow, "game.endless_request", 0)


def wave_warnings(game: Game, balance: Balance) -> None:
    """Count down the choice window, then to each wave once its preparation or intermission
    begins; the engine asks for the countdown before each wave after the schedule."""
    # The engine asks for this countdown as it counts the window's first second off.
    choice = game.trigger("game.choice.warning", looping=True)
    game.value(choice, "game.wave_display", 3)
    effect(
        choice,
        "display_timer",
        display_time=balance.choice_seconds - 1,
        time_unit=TimeUnit.SECONDS,
        message="Run options close in %d",
        reset_timer=1,
        timer=0,
    )
    game.set_value(choice, "game.wave_display", 0)
    endless = game.trigger("game.wave.endless.warning", looping=True)
    game.value(endless, "game.wave_display", 1)
    effect(
        endless,
        "display_timer",
        display_time=balance.intermission_seconds,
        time_unit=TimeUnit.SECONDS,
        message="Next wave in %d",
        reset_timer=1,
        timer=0,
    )
    game.set_value(endless, "game.wave_display", 0)
    clear = game.trigger("game.wave.timer.clear", looping=True)
    game.value(clear, "game.wave_display", 2)
    effect(clear, "clear_timer", timer=0)
    game.set_value(clear, "game.wave_display", 0)
    for number, wave in enumerate(balance.waves, 1):
        trigger = game.trigger(f"game.wave.{number}.warning", looping=False)
        game.value(trigger, "game.phase", State.PREPARATION)
        game.value(trigger, "game.wave", number - 2)
        seconds = balance.preparation_seconds if number == 1 else balance.intermission_seconds
        effect(
            trigger,
            "display_timer",
            display_time=seconds,
            time_unit=TimeUnit.SECONDS,
            message=f"Wave {number}: {wave.key} in %d",
            reset_timer=1,
            timer=0,
        )


def game_status(game: Game, balance: Balance) -> None:
    wave = game.names.resolve("variable", "game.display_wave")
    countdown = game.names.resolve("variable", "game.countdown")
    objective(
        game,
        "game.status",
        f"Wave <Variable {wave}>: <Variable {countdown}> s",
        f"Survive {len(balance.waves)} scheduled waves; Endless runs and sudden death "
        "continue past them. Before a wave, the seconds until it starts; during a wave, "
        "the seconds its enemies keep spawning.",
        shown=True,
    )


type Band = tuple[Rect, int]


def lane_rows(lane: EngineLane) -> tuple[Band, ...]:
    """The lane's path in three bands, each with the exit row its enemies walk to: enemies
    created side by side keep their files instead of converging on one tile."""
    x1, y1, x2, y2 = lane.path
    center = lane.center_y
    return (
        ((x1, y1, x2, center - 1), center - 1),
        ((x1, center, x2, center), center),
        ((x1, center + 1, x2, y2), center + 1),
    )


def spawn_rows(lane: EngineLane) -> tuple[Band, ...]:
    """The lane's bands in the spawn column alone, where the XS creates each batch."""
    return tuple(
        ((lane.spawn_x, y1, lane.spawn_x + 1, y2), row) for (_, y1, _, y2), row in lane_rows(lane)
    )


def send_down_the_lane(trigger: TriggerHandle, lane: EngineLane, bands: tuple[Band, ...]) -> None:
    """Every enemy in the bands walks its band to the exit. The enemy is allied to every lane,
    so nothing stops it on the way; each new order makes a walking unit pause."""
    for band, row in bands:
        effect(
            trigger,
            "task_object",
            source_player=8,
            location_x=lane.exit_x,
            location_y=row,
            action_type=ActionType.MOVE,
            **area(band),
        )


def lane_spawned(game: Game, lane: EngineLane) -> None:
    """The XS creates each batch of enemies; this acknowledges it by sending the new batch
    off."""
    prefix = f"lane.p{lane.player}"
    spawned = game.trigger(f"{prefix}.spawned", looping=True)
    game.value(spawned, f"{prefix}.active", 1)
    game.value(spawned, f"{prefix}.spawn", 1)
    send_down_the_lane(spawned, lane, spawn_rows(lane))
    game.set_value(spawned, f"{prefix}.spawn", 0)


def lane_route(game: Game, lane: EngineLane) -> None:
    """Every enemy in the lane is ordered on again now and then, in case one lost its way."""
    prefix = f"lane.p{lane.player}"
    move = game.trigger(f"{prefix}.route", looping=True)
    condition(move, "timer", timer=ROUTE_SECONDS)
    game.value(move, f"{prefix}.active", 1)
    send_down_the_lane(move, lane, lane_rows(lane))


def declare_results(game: Game) -> None:
    for winner in range(1, 9):
        finish = game.trigger(f"game.result.p{winner}", looping=False)
        game.value(finish, "game.winner", winner)
        game.value(finish, "game.phase", State.DEFEAT if winner == 8 else State.VICTORY)
        effect(finish, "declare_victory", source_player=winner, enabled=1)
