"""Per-lane setup, income, cleanup and status for the playable game."""

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import lane_route, lane_waves
from ancienttdde.scenario.triggers import area, effect


def lane_actions(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    mill = game.scenario.unit_manager.add_unit(
        player=player, unit_const=game.stock("mill"), x=84, y=lane.center_y
    )
    game.names.register("object", f"{prefix}.berry_mill", mill.reference_id)
    lane_initialize(game, lane, balance)
    lane_income(game, lane, balance)
    lane_cleanup(game, lane, mill.reference_id)
    lane_waves(game, lane, balance)
    lane_route(game, lane)
    lane_status(game, lane)


def lane_initialize(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    init = game.trigger(f"{prefix}.initialize", looping=True)
    game.value(init, f"{prefix}.active", 1)
    game.value(init, f"{prefix}.initialized", 0)
    game.resources(init, balance.starting_resources, player=player)
    effect(
        init,
        "modify_resource",
        source_player=player,
        tribute_list=Attribute.POPULATION_HEADROOM,
        quantity=200,
        operation=Operation.SET,
    )
    game.research(init, "FEUDAL_AGE", player=player)
    effect(
        init,
        "enable_disable_object",
        source_player=player,
        object_list_unit_id=game.stock("watch-tower"),
        enabled=1,
    )
    game.tower_attack_bonus(init, balance.tower_attack_bonus, player=player)
    for x in (26, 40):
        effect(
            init,
            "create_object",
            source_player=player,
            object_list_unit_id=game.stock("watch-tower"),
            location_x=x,
            location_y=lane.center_y - 3,
        )
    protected = [
        u.reference_id
        for u in game.scenario.unit_manager.units[player]
        if u.unit_const in {game.stock("market"), game.stock("dock")}
    ]
    protected.append(game.placement(lane.life_reference))
    game.protect(init, protected)
    for kind, partner in (("cart", lane.land_trade_partner), ("cog", lane.water_trade_partner)):
        traders = [
            u.reference_id
            for u in game.scenario.unit_manager.units[player]
            if u.unit_const == game.stock(kind)
        ]
        if traders:
            effect(
                init,
                "task_object",
                source_player=player,
                selected_object_ids=traders,
                location_object_reference=game.placement(partner),
                action_type=ActionType.DEFAULT,
            )
    game.set_value(init, f"{prefix}.initialized", 1)


def lane_income(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    income = game.trigger(f"{prefix}.income", looping=True)
    game.value(income, f"{prefix}.active", 1)
    game.value(income, f"{prefix}.income", 1)
    game.resources(income, balance.income_amount, player=player, operation=Operation.ADD)
    game.set_value(income, f"{prefix}.income", 0)


def lane_cleanup(game: Game, lane: EngineLane, mill: int) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    cleanup = game.trigger(f"{prefix}.cleanup", looping=True)
    game.value(cleanup, f"{prefix}.cleanup", 1)
    effect(
        cleanup,
        "script_call",
        message=f"void ancientCleanupP{player}() {{ ancientCleanupLane({player}, {mill}); }}",
    )
    effect(cleanup, "remove_object", source_player=8, **area(lane.path))
    game.set_value(cleanup, f"{prefix}.cleanup", 0)


def lane_status(game: Game, lane: EngineLane) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    lives = game.names.resolve("variable", f"{prefix}.lives")
    objective = game.scenario.trigger_manager.add_trigger(
        f"{prefix}.status",
        short_description=f"P{player} lives: <Variable {lives}>",
        description=f"P{player}: prevent enemies reaching the right-hand exit.",
        display_as_objective=True,
        display_on_screen=True,
        enabled=True,
        execute_on_load=False,
    )
    # Never fires: its sole purpose is displaying the persisted life total.
    game.value(objective, "game.phase", -1)
