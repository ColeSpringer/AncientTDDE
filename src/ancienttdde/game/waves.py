"""Wave configuration, spawns, routing, the game clock, results and endless lumber."""

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.script import State
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import area, condition, effect

# Lumber-camp trees hold more wood than a run uses. DE applies this effect value as a
# 16-bit number (1,000,000 arrived as 16,960), so it stays below 32,768.
LUMBER_TREE_WOOD = 32_000


def endless_lumber(game: Game, lanes: tuple[EngineLane, ...]) -> None:
    # New objects take their owner's current attributes, so the lumber trees are replaced
    # at the start, before any unit or building can occupy their tiles.
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
    for lane in lanes:
        x1, y1, x2, y2 = lane.economy
        trees = [
            u
            for u in game.scenario.unit_manager.units[0]
            if u.unit_const == game.stock("tree") and x1 <= int(u.x) <= x2 and y1 <= int(u.y) <= y2
        ]
        if len(trees) != 4:
            raise ValueError(f"P{lane.player} economy needs four lumber trees, found {len(trees)}")
        for tree in trees:
            placement = game.placement(tree.reference_id)
            effect(trigger, "remove_object", source_player=0, selected_object_ids=[placement])
            effect(
                trigger,
                "create_object",
                source_player=0,
                object_list_unit_id=game.stock("tree"),
                location_x=int(tree.x),
                location_y=int(tree.y),
            )


def game_clock(game: Game) -> None:
    clock = game.trigger("game.clock", looping=True)
    condition(clock, "timer", timer=1)
    effect(clock, "script_call", message="void ancientClockEffect() { ancientTick(); }")


def configure_waves(game: Game, balance: Balance) -> None:
    for index, wave in enumerate(balance.waves, 1):
        configure = game.trigger(f"game.wave.{index}.configure", looping=False)
        game.value(configure, "game.wave", index - 1)
        effect(
            configure,
            "modify_attribute",
            source_player=8,
            object_list_unit_id=wave.object_id,
            object_attributes=ObjectAttribute.HIT_POINTS,
            operation=Operation.SET,
            quantity=wave.hit_points,
        )
        effect(
            configure,
            "modify_attribute",
            source_player=8,
            object_list_unit_id=wave.object_id,
            object_attributes=ObjectAttribute.MOVEMENT_SPEED,
            operation=Operation.SET,
            quantity=0.65,
        )
        game.set_value(configure, "game.configured", index)


def wave_warnings(game: Game, balance: Balance) -> None:
    """Count down to each wave once its preparation or intermission begins."""
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
    objective = game.scenario.trigger_manager.add_trigger(
        "game.status",
        short_description=(
            f"Wave <Variable {wave}> of {len(balance.waves)}: <Variable {countdown}> s"
        ),
        description=(
            "Survive every wave. Before a wave, the seconds until it starts; during a wave, "
            "the seconds its enemies keep spawning; in sudden death, the seconds until the "
            "next loss of lives."
        ),
        display_as_objective=True,
        display_on_screen=True,
        enabled=True,
        execute_on_load=False,
    )
    # Never fires: its sole purpose is displaying the persisted wave and countdown.
    game.value(objective, "game.phase", -1)


def lane_waves(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    for index, wave in enumerate(balance.waves, 1):
        spawn = game.trigger(f"{prefix}.wave.{index}", looping=True)
        game.value(spawn, f"{prefix}.active", 1)
        game.value(spawn, f"{prefix}.spawn", index)
        game.value(spawn, "game.configured", index)
        for offset in range(wave.count):
            effect(
                spawn,
                "create_object",
                source_player=8,
                object_list_unit_id=wave.object_id,
                location_x=lane.spawn_x + offset,
                location_y=lane.center_y,
                disable_sound=1,
            )
        effect(
            spawn,
            "change_object_stance",
            source_player=8,
            object_list_unit_id=wave.object_id,
            attack_stance=AttackStance.STAND_GROUND,
            **area(lane.path),
        )
        effect(
            spawn,
            "task_object",
            source_player=8,
            object_list_unit_id=wave.object_id,
            location_x=lane.exit_x,
            location_y=lane.center_y,
            action_type=ActionType.MOVE,
            **area(lane.path),
        )
        game.set_value(spawn, f"{prefix}.spawn", 0)


def lane_route(game: Game, lane: EngineLane) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    move = game.trigger(f"{prefix}.route", looping=True)
    condition(move, "timer", timer=3)
    game.value(move, f"{prefix}.active", 1)
    effect(
        move,
        "task_object",
        source_player=8,
        location_x=lane.exit_x,
        location_y=lane.center_y,
        action_type=ActionType.MOVE,
        **area(lane.path),
    )


def declare_results(game: Game) -> None:
    for winner in range(1, 9):
        finish = game.trigger(f"game.result.p{winner}", looping=False)
        game.value(finish, "game.winner", winner)
        game.value(finish, "game.phase", State.DEFEAT if winner == 8 else State.VICTORY)
        effect(finish, "declare_victory", source_player=winner, enabled=1)
