"""Native triggers that apply a civilization profile's adjustments once a lane is initialized.

The XS puts the lane's native effect set in its profile field at initialization; each set has
one trigger per lane, gated on that field, so every civilization sharing a set shares them.
Kings, King prices, kill rewards, raider caps and tower attack are the XS's own business.
"""

from dataclasses import astuple

from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.game.catalog import RESOURCES, Shop
from ancienttdde.game.civilizations import NativeEffects, Profiles
from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.economy import at, garrison_relic
from ancienttdde.game.shop import apply, grant_population, grant_resource, task_traders
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import TriggerHandle, effect


def apply_native(
    game: Game,
    trigger: TriggerHandle,
    lane: EngineLane,
    balance: Balance,
    effects: NativeEffects,
    shop: Shop,
) -> None:
    player = lane.player
    for resource, amount in zip(RESOURCES, astuple(effects.resources), strict=True):
        if amount:
            grant_resource(trigger, player, resource, amount)
    if effects.population:
        grant_population(trigger, player, effects.population)
    for name in effects.technologies:
        game.research(trigger, name, player=player)
    for attribute, amount, operation in (
        (ObjectAttribute.HIT_POINTS, effects.tower_hit_points, Operation.ADD),
        (ObjectAttribute.STONE_COSTS, effects.tower_stone, Operation.SUBTRACT),
    ):
        if amount:
            for unit in balance.towers.definitions:
                effect(
                    trigger,
                    "modify_attribute",
                    source_player=player,
                    object_list_unit_id=unit,
                    object_attributes=attribute,
                    operation=operation,
                    quantity=amount,
                )
    for _ in range(effects.relics):
        garrison_relic(game, trigger, lane.sites.monasteries[0])
    for medium, count in effects.traders:
        kind, tiles, _ = lane.traders(medium)
        if count > len(tiles):
            raise ValueError(
                f"P{player} has {len(tiles)} {kind} spots for {count} starting {kind}s"
            )
        for tile in tiles[:count]:
            effect(
                trigger,
                "create_object",
                source_player=player,
                object_list_unit_id=game.stock(kind),
                **at(tile),
            )
        task_traders(game, trigger, lane, medium, tiles[:count])
    # A granted purchase's native effects, as the shop applies them after a payment. The XS
    # places its units and marks once-only ones as owned once the lane's setup has run.
    for key in effects.purchases:
        apply(game, trigger, lane, shop.get(key), balance)


def lane_profiles(
    game: Game, lane: EngineLane, balance: Balance, profiles: Profiles, shop: Shop
) -> None:
    """One trigger per native effect set. The XS puts the set's number in the lane's profile
    field only once the lane is active and its own setup has run, so that one condition gates
    each trigger and the others cost one check a pass."""
    prefix = f"lane.p{lane.player}"
    for index, effects in enumerate(profiles.native_groups(), 1):
        trigger = game.trigger(f"{prefix}.profile.{index}", looping=False)
        game.value(trigger, f"{prefix}.profile", index)
        apply_native(game, trigger, lane, balance, effects, shop)
