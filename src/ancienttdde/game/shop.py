"""Native acknowledgements that apply what the XS shop has paid for, and the shop's signs."""

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.game.catalog import (
    AgeUp,
    Castle,
    Expansion,
    Investment,
    Population,
    Purchase,
    RelicEnclosure,
    Relics,
    Repair,
    ResourceGrant,
    Shop,
    SpecialTower,
    TowerAttack,
    Traders,
    Villagers,
    label_captions,
)
from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.economy import around, at
from ancienttdde.game.sites import Tile
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.objects import technology
from ancienttdde.scenario.triggers import STORAGE, TriggerHandle, area, effect


def hay_stack(game: Game, tile: Tile) -> int:
    """Return the placed Hay Stack that reserves a tile."""
    found = [
        unit.reference_id
        for unit in game.scenario.unit_manager.units[0]
        if unit.unit_const == game.stock("hay-stack") and (int(unit.x), int(unit.y)) == tile
    ]
    if len(found) != 1:
        raise ValueError(f"Expected one Hay Stack reserving {tile}, found {len(found)}")
    return game.placement(found[0])


def apply(
    game: Game, trigger: TriggerHandle, lane: EngineLane, purchase: Purchase, balance: Balance
) -> None:
    """Add the native effects of a paid purchase; XS has already created its units."""
    player = lane.player
    sites = lane.sites
    match purchase.effect:
        case TowerAttack(family=family, amount=amount):
            game.attack_bonus(trigger, player, balance.towers.family_ids(family), amount)
        case ResourceGrant(resource=resource, amount=amount):
            effect(
                trigger,
                "modify_resource",
                source_player=player,
                tribute_list=STORAGE[resource],
                quantity=amount,
                operation=Operation.ADD,
            )
        case AgeUp(age=age):
            # XS adds the tower upgrade when the civilization has it.
            effect(
                trigger,
                "research_technology",
                source_player=player,
                technology=technology(age),
                force_research_technology=1,
            )
        case SpecialTower(side=side):
            pad = sites.special[side]
            effect(
                trigger,
                "remove_object",
                source_player=0,
                selected_object_ids=[hay_stack(game, pad)],
            )
            effect(
                trigger,
                "create_object",
                source_player=player,
                object_list_unit_id=balance.towers.special_id,
                **at(pad),
            )
        case Villagers(area=where):
            spawn = sites.villagers[where]
            effect(
                trigger,
                "task_object",
                source_player=player,
                object_list_unit_id=game.stock("villager"),
                action_type=ActionType.MOVE,
                **around(spawn.tiles),
                **at(spawn.walk),
            )
        case Traders(medium=medium):
            kind = "cart" if medium == "land" else "cog"
            tiles = sites.carts if medium == "land" else sites.cogs
            partner = lane.land_trade_partner if medium == "land" else lane.water_trade_partner
            effect(
                trigger,
                "task_object",
                source_player=player,
                object_list_unit_id=game.stock(kind),
                location_object_reference=game.placement(partner),
                action_type=ActionType.DEFAULT,
                **around(tiles),
            )
        case RelicEnclosure():
            for kind in ("monastery", "monk"):
                effect(
                    trigger,
                    "change_ownership",
                    source_player=0,
                    target_player=player,
                    object_list_unit_id=game.stock(kind),
                    **area(sites.relic_enclosure),
                )
        case Population(amount=amount):
            effect(
                trigger,
                "modify_resource",
                source_player=player,
                tribute_list=Attribute.POPULATION_HEADROOM,
                quantity=amount,
                operation=Operation.ADD,
            )
        case Expansion(row=row):
            for rows in sites.expansion[row]:
                effect(
                    trigger,
                    "remove_object",
                    source_player=0,
                    object_list_unit_id=game.stock("hay-stack"),
                    **area(rows),
                )
        case Investment() | Repair() | Relics() | Castle():
            # XS pays investments and repairs, and creates relics, monks and castles.
            pass


def lane_purchases(game: Game, lane: EngineLane, shop: Shop, balance: Balance) -> None:
    """Each purchase the XS paid for is applied once, then its request is cleared."""
    player = lane.player
    prefix = f"lane.p{player}"
    for purchase in shop.purchases:
        trigger = game.trigger(f"{prefix}.buy.{purchase.key}", looping=True)
        game.value(trigger, f"{prefix}.active", 1)
        game.value(trigger, f"{prefix}.purchase", purchase.index)
        apply(game, trigger, lane, purchase, balance)
        effect(
            trigger,
            "send_chat",
            source_player=player,
            message=f"Bought {purchase.name} for {purchase.price}.",
        )
        game.set_value(trigger, f"{prefix}.purchase", 0)


def shop_signs(game: Game, shop: Shop) -> None:
    """Caption the shop's signs from the catalog, and place the signs it adds."""
    units = {unit.reference_id: unit for unit in game.scenario.unit_manager.units[0]}
    for label, caption in label_captions(shop).items():
        units[game.placement(label)].caption_string = caption
    for purchase in shop.purchases:
        if purchase.new_sign is not None:
            x, y = purchase.new_sign
            sign = game.scenario.unit_manager.add_unit(
                player=0, unit_const=game.stock("sign"), x=x, y=y, caption_string=purchase.caption
            )
            game.names.register("object", f"shop.{purchase.key}.sign", sign.reference_id)
