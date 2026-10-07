"""Names given to placed objects at the start, as the original map does with a rename trigger.

DE shows an object's name when it is selected, so the display unit beside each pad, the relic
labels at the transfer pads and arrivals, the life Outposts and the credit all carry their text
from the first second. Sign objects cannot be renamed, so the shop has none.
"""

import math
from collections.abc import Iterable

from ancienttdde.game.catalog import Shop, display_captions
from ancienttdde.game.config import EngineLane
from ancienttdde.game.instructions import CREDIT
from ancienttdde.game.sites import Tile
from ancienttdde.game.triggers import Game
from ancienttdde.models import Rect

# The original renames the hero standing here to its credit.
CREDIT_TILE = (130, 75)
# Where each transfer leads, and where its arrivals come from.
TRANSFER_AREAS = {
    "build": ("build area", "resource area"),
    "economy": ("resource area", "build area"),
    "north": ("north build rows", "south build rows"),
    "south": ("south build rows", "north build rows"),
}
# The villager area each transfer arrives in, where bought villagers also appear.
ARRIVAL_AREAS = {"build": "build", "economy": "economy"}
# The relic labelling a transfer pad or arrival stands this close to its center.
LABEL_REACH = 2.5
# Bought villagers appearing this close to an arrival are mentioned on its label.
BOUGHT_REACH = 3.0


def center(region: Rect) -> tuple[float, float]:
    x1, y1, x2, y2 = region
    return (x1 + x2 + 1) / 2, (y1 + y2 + 1) / 2


def relic_label(game: Game, region: Rect) -> int:
    """The Gaia relic the original placed beside a transfer pad or arrival to label it."""
    middle = center(region)
    found = [
        ref for ref, spot in game.gaia("relic").items() if math.dist(spot, middle) <= LABEL_REACH
    ]
    if len(found) != 1:
        raise ValueError(f"Expected one relic label beside {region}, found {len(found)}")
    return found[0]


def arrival_text(origin: str, arrival: Tile, bought: tuple[Tile, ...]) -> str:
    text = f"Villagers arrive here from the {origin}"
    if arrival in bought:
        return text + " and when bought"
    if any(math.dist(arrival, tile) <= BOUGHT_REACH for tile in bought):
        return text + "; bought villagers appear beside it"
    return text


def name_objects(game: Game, lanes: Iterable[EngineLane], shop: Shop) -> None:
    trigger = game.trigger("game.labels", looping=False)
    owners = game.owners()
    for placed, caption in display_captions(shop).items():
        game.rename(trigger, game.placement(placed), caption, owners=owners)
    for purchase in shop.purchases:
        if purchase.display_at is not None:
            king = game.names.resolve("object", f"shop.{purchase.key}.display")
            game.rename(trigger, king, purchase.caption, owners=owners)
    for lane in lanes:
        lives = f"P{lane.player} lives: health shows the share left"
        game.rename(trigger, game.placement(lane.life_reference), lives, owners=owners)
        for key, transfer in lane.sites.transfers.items():
            destination, origin = TRANSFER_AREAS[key]
            pad = f"Transfer pad: a villager standing here moves to the {destination}"
            game.rename(trigger, relic_label(game, transfer.pad), pad, owners=owners)
            area = ARRIVAL_AREAS.get(key)
            bought = lane.sites.villagers[area].tiles if area else ()
            arrival = relic_label(game, (*transfer.arrival, *transfer.arrival))
            text = arrival_text(origin, transfer.arrival, bought)
            game.rename(trigger, arrival, text, owners=owners)
    credit = [
        ref
        for ref, (x, y) in game.gaia("william").items()
        if (math.floor(x), math.floor(y)) == CREDIT_TILE
    ]
    if len(credit) != 1:
        raise ValueError(f"Expected one credit hero at {CREDIT_TILE}, found {len(credit)}")
    game.rename(trigger, credit[0], CREDIT, owners=owners)
