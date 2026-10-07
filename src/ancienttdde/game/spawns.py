"""The units each purchase places for a lane, which XS creates before it takes any Kings."""

from dataclasses import dataclass

from ancienttdde.game.catalog import Castle, Purchase, Relics, Shop, Traders, Villagers
from ancienttdde.game.config import EngineLane
from ancienttdde.game.sites import Tile
from ancienttdde.scenario.objects import stock


@dataclass(frozen=True)
class Spawned:
    """A unit to create; XS positions use tenths of a tile to stay integers in tables."""

    unit: int
    gaia: bool
    x10: int
    y10: int


def center(tile: Tile) -> tuple[int, int]:
    x, y = tile
    return 10 * x + 5, 10 * y + 5


def placed(kind: str, tiles: tuple[Tile, ...], *, gaia: bool = False) -> tuple[Spawned, ...]:
    return tuple(Spawned(stock(kind), gaia, *center(tile)) for tile in tiles)


def purchase_spawns(lane: EngineLane, purchase: Purchase) -> tuple[Spawned, ...]:
    sites = lane.sites
    match purchase.effect:
        case Villagers(area=where):
            return placed("villager", sites.villagers[where].tiles)
        case Traders(medium=medium):
            if medium == "land":
                return placed("cart", sites.carts)
            return placed("cog", sites.cogs)
        case Relics():
            return placed("relic", sites.relics, gaia=True) + placed("monk", sites.monks)
        case Castle():
            # A castle's even footprint is centered on the tile corner its site names.
            x, y = sites.castle
            return (Spawned(stock("castle"), False, 10 * x, 10 * y),)
        case _:
            return ()


def creation_tiles(lane: EngineLane, shop: Shop) -> set[Tile]:
    """Every tile the XS creates a unit on for this lane: the King stall, the transfer arrivals
    and the spots of bought units. Nothing may be placed there, or the collision check fails."""
    tiles = {lane.sites.king_spawn}
    tiles.update(transfer.arrival for transfer in lane.sites.transfers.values())
    for purchase in shop.purchases:
        for spawned in purchase_spawns(lane, purchase):
            tiles.add((spawned.x10 // 10, spawned.y10 // 10))
    return tiles
