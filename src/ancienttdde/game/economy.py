"""Native triggers for a lane's Kings, villager transfers and bonuses."""

import math

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.instructions import bonus_delivered
from ancienttdde.game.messages import message_code, message_texts
from ancienttdde.game.sites import Tile, within
from ancienttdde.game.triggers import Game
from ancienttdde.models import Rect
from ancienttdde.scenario.triggers import (
    STORAGE,
    FieldValue,
    TriggerHandle,
    area,
    condition,
    effect,
)

# Villagers belong to this stock class whatever task they are doing.
CIVILIAN = 4
DEPOSITS = {"gold": "gold-mine", "food": "forage-bush", "stone": "stone-mine"}
# What a placed resource villager gathers: the deposit or tree beside it.
GATHERED = ("gold-mine", "forage-bush", "stone-mine", "tree")
# A placed villager stands this close to the resource it works.
GATHER_REACH = 1.5


def at(tile: Tile) -> dict[str, FieldValue]:
    x, y = tile
    return {"location_x": x, "location_y": y}


def around(tiles: tuple[Tile, ...]) -> dict[str, FieldValue]:
    """The area that holds exactly these tiles."""
    xs, ys = [x for x, _ in tiles], [y for _, y in tiles]
    bounds: Rect = (min(xs), min(ys), max(xs), max(ys))
    return area(bounds)


def lane_gatherers(game: Game, trigger: TriggerHandle, lane: EngineLane) -> None:
    """Each villager placed in the resource area starts gathering the deposit or tree beside
    it; the build-area villagers wait for orders."""
    kinds = {game.stock(kind) for kind in GATHERED}
    resources = [
        (u.reference_id, u.x, u.y)
        for u in game.scenario.unit_manager.units[0]
        if u.unit_const in kinds and within(lane.economy, u.x, u.y)
    ]
    villagers = {game.stock("villager"), game.stock("villager-female")}
    for unit in game.scenario.unit_manager.units[lane.player]:
        if unit.unit_const not in villagers or not within(lane.economy, unit.x, unit.y):
            continue
        distances = [(r[0], math.dist((r[1], r[2]), (unit.x, unit.y))) for r in resources]
        reference, distance = min(distances, key=lambda found: found[1], default=(-1, math.inf))
        if distance > GATHER_REACH:
            raise ValueError(f"P{lane.player} villager at {(unit.x, unit.y)} stands by no resource")
        effect(
            trigger,
            "task_object",
            source_player=lane.player,
            selected_object_ids=[game.placement(unit.reference_id)],
            location_object_reference=game.placement(reference),
            action_type=ActionType.DEFAULT,
        )


def lane_kings(game: Game, lane: EngineLane) -> None:
    """Kings the XS creates at a lane's stall walk into the shop, clearing it for the next."""
    player = lane.player
    prefix = f"lane.p{player}"
    trigger = game.trigger(f"{prefix}.king", looping=True)
    game.value(trigger, f"{prefix}.active", 1)
    stall = lane.sites.king_spawn
    condition(
        trigger,
        "objects_in_area",
        source_player=player,
        object_list=game.stock("king"),
        quantity=1,
        **around((stall,)),
    )
    effect(
        trigger,
        "task_object",
        source_player=player,
        object_list_unit_id=game.stock("king"),
        action_type=ActionType.MOVE,
        **around((stall,)),
        **at(lane.sites.king_rally),
    )


def lane_transfers(game: Game, lane: EngineLane) -> None:
    """Villagers the XS moves across a transfer pad walk clear of the arrival tile."""
    player = lane.player
    prefix = f"lane.p{player}"
    for name, transfer in lane.sites.transfers.items():
        trigger = game.trigger(f"{prefix}.transfer.{name}", looping=True)
        game.value(trigger, f"{prefix}.active", 1)
        condition(
            trigger,
            "objects_in_area",
            source_player=player,
            object_group=CIVILIAN,
            quantity=1,
            **around((transfer.arrival,)),
        )
        effect(
            trigger,
            "task_object",
            source_player=player,
            object_group=CIVILIAN,
            action_type=ActionType.MOVE,
            **around((transfer.arrival,)),
            **at(transfer.walk),
        )


def lane_messages(game: Game, lane: EngineLane, balance: Balance) -> None:
    """Each message the XS requests reaches its lane's player once, then the request clears."""
    player = lane.player
    prefix = f"lane.p{player}"
    for key, text in message_texts(balance).items():
        trigger = game.trigger(f"{prefix}.message.{key}", looping=True)
        game.value(trigger, f"{prefix}.active", 1)
        game.value(trigger, f"{prefix}.message", message_code(key))
        effect(trigger, "send_chat", source_player=player, message=text)
        game.set_value(trigger, f"{prefix}.message", 0)


def lane_bonuses(game: Game, lane: EngineLane, balance: Balance) -> None:
    """Reaching the end of a resource's rows pays its bonus once and opens endless deposits."""
    player = lane.player
    prefix = f"lane.p{player}"
    economy = balance.economy
    amounts = {"gold": economy.gold_bonus, "food": economy.food_bonus, "stone": economy.stone_bonus}
    for resource, region in lane.sites.bonuses.items():
        trigger = game.trigger(f"{prefix}.bonus.{resource}", looping=False)
        game.value(trigger, f"{prefix}.active", 1)
        condition(
            trigger,
            "objects_in_area",
            source_player=player,
            object_group=CIVILIAN,
            quantity=1,
            **area(region),
        )
        effect(
            trigger,
            "modify_resource",
            source_player=player,
            tribute_list=STORAGE[resource],
            quantity=amounts[resource],
            operation=Operation.ADD,
        )
        for deposit in lane.sites.endless[resource]:
            effect(
                trigger,
                "create_object",
                source_player=0,
                object_list_unit_id=game.stock(DEPOSITS[resource]),
                **at(deposit),
            )
        effect(
            trigger,
            "remove_object",
            source_player=0,
            object_list_unit_id=game.stock("sign"),
            **area(region),
        )
        effect(
            trigger,
            "send_chat",
            source_player=player,
            message=bonus_delivered(balance, resource),
        )


def endless_deposits(game: Game, balance: Balance) -> None:
    """Deposits created later hold more than a run uses; placed deposits keep their amounts."""
    trigger = game.trigger("game.deposits", looping=False)
    for kind in ("forage-bush", "gold-mine", "stone-mine"):
        effect(
            trigger,
            "modify_attribute",
            source_player=0,
            object_list_unit_id=game.stock(kind),
            object_attributes=ObjectAttribute.AMOUNT_OF_1ST_RESOURCE_STORAGE,
            operation=Operation.SET,
            quantity=balance.economy.endless_deposit,
        )


def garrison_relic(game: Game, trigger: TriggerHandle, monastery: int) -> None:
    """A relic inside a placed monastery.

    Relics are Gaia objects: the original map fills this effect for player 0 with both object
    list fields set to the relic, and a relic created for the lane's player crashed DE on load.
    """
    relic = game.stock("relic")
    effect(
        trigger,
        "create_garrisoned_object",
        source_player=0,
        selected_object_ids=[game.placement(monastery)],
        object_list_unit_id=relic,
        object_list_unit_id_2=relic,
    )


def starting_relics(game: Game, trigger: TriggerHandle, lane: EngineLane, balance: Balance) -> None:
    """Each lane's first relics start inside its own monasteries."""
    for monastery in lane.sites.monasteries[: balance.economy.starting_relics]:
        garrison_relic(game, trigger, monastery)
