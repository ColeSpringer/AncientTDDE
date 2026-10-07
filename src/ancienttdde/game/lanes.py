"""Per-lane setup, economy, purchases, cleanup and status for the playable game."""

from dataclasses import asdict

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.game.catalog import Shop
from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.economy import (
    lane_attack,
    lane_bonuses,
    lane_kings,
    lane_messages,
    lane_transfers,
    starting_relics,
)
from ancienttdde.game.shop import lane_purchases
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import lane_route, lane_waves
from ancienttdde.scenario.triggers import STORAGE, area, effect


def lane_actions(game: Game, lane: EngineLane, balance: Balance, shop: Shop) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    mill = game.scenario.unit_manager.add_unit(
        player=player, unit_const=game.stock("mill"), x=84, y=lane.center_y
    )
    game.names.register("object", f"{prefix}.berry_mill", mill.reference_id)
    lane_initialize(game, lane, balance)
    lane_cleanup(game, lane, mill.reference_id)
    lane_waves(game, lane, balance)
    lane_route(game, lane)
    lane_status(game, lane, balance)
    lane_kings(game, lane)
    family = shop.attack_family()
    if family is not None:
        lane_attack(game, lane, balance.towers.family_ids(family))
    lane_transfers(game, lane)
    lane_messages(game, lane, balance)
    lane_bonuses(game, lane, balance)
    lane_purchases(game, lane, shop, balance)


def lane_initialize(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    init = game.trigger(f"{prefix}.initialize", looping=True)
    game.value(init, f"{prefix}.active", 1)
    game.value(init, f"{prefix}.initialized", 0)
    start = asdict(balance.economy.starting_resources)
    for resource, attribute in STORAGE.items():
        effect(
            init,
            "modify_resource",
            source_player=player,
            tribute_list=attribute,
            quantity=start[resource],
            operation=Operation.SET,
        )
    game.research(init, "FEUDAL_AGE", player=player)
    for technology in balance.economy.starting_technologies:
        game.research(init, technology, player=player)
    effect(
        init,
        "enable_disable_object",
        source_player=player,
        object_list_unit_id=game.stock("watch-tower"),
        enabled=1,
    )
    # Only the special towers bought for this lane use this definition.
    game.attack_bonus(init, player, (balance.towers.special_id,), balance.towers.special_pierce)
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
    starting_relics(game, init, lane, balance)
    game.set_value(init, f"{prefix}.initialized", 1)


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


def lane_status(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    lives = game.names.resolve("variable", f"{prefix}.lives")
    objective = game.scenario.trigger_manager.add_trigger(
        f"{prefix}.status",
        short_description=f"P{player} lives: <Variable {lives}>/{balance.lives}",
        description=f"P{player}: prevent enemies reaching the right-hand exit.",
        display_as_objective=True,
        display_on_screen=True,
        enabled=True,
        execute_on_load=False,
    )
    # Never fires: its sole purpose is displaying the persisted life total.
    game.value(objective, "game.phase", -1)
