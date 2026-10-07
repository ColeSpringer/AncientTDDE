"""Native acknowledgements that apply what the XS shop has paid for, and the shop's tidying."""

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
)
from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.economy import around, at
from ancienttdde.game.sites import Tile
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.objects import technology
from ancienttdde.scenario.triggers import STORAGE, TriggerHandle, area, effect


def hay_stack(game: Game, tile: Tile) -> int:
    """Return the placed Hay Stack that reserves a tile."""
    found = [ref for ref, (x, y) in game.gaia("hay-stack").items() if (int(x), int(y)) == tile]
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


# A shop sign stands within this many tiles of the pad it once labelled; row-end signs are far off.
SIGN_REACH = 4


def beside_pad(shop: Shop, x: float, y: float, reach: float) -> bool:
    for purchase in shop.purchases:
        x1, y1, x2, y2 = purchase.pad_region
        if x1 - reach <= x <= x2 + 1 + reach and y1 - reach <= y <= y2 + 1 + reach:
            return True
    return False


def remove_shop_signs(game: Game, shop: Shop) -> None:
    """Take the signs beside the pads out: DE cannot rename them, and every pad has a named unit."""
    doomed = {
        ref for ref, (x, y) in game.gaia("sign").items() if beside_pad(shop, x, y, SIGN_REACH)
    }
    gaia = game.scenario.unit_manager.units[0]
    for unit in [u for u in gaia if u.reference_id in doomed]:
        gaia.remove(unit)
        game.placements.discard(unit.reference_id)
    game.forget_gaia("sign")


def place_displays(game: Game, shop: Shop) -> None:
    """Place a Gaia King beside each pad whose original label was an object only the mod named."""
    for purchase in shop.purchases:
        if purchase.display_at is not None:
            x, y = purchase.display_at
            king = game.scenario.unit_manager.add_unit(
                player=0, unit_const=game.stock("king"), x=x, y=y
            )
            game.names.register("object", f"shop.{purchase.key}.display", king.reference_id)
    game.forget_gaia("king")
