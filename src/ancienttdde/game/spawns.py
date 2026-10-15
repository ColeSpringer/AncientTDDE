"""The units each purchase places for a lane, which XS creates before it takes any Kings."""

from dataclasses import dataclass

from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.game.catalog import Castle, Purchase, Raider, Relics, Shop, Traders, Villagers
from ancienttdde.game.config import EngineLane, Interaction, Raiders
from ancienttdde.game.sites import Tile
from ancienttdde.scenario.objects import stock


@dataclass(frozen=True)
class Spawned:
    """A unit to create; XS positions use tenths of a tile to stay integers in tables."""

    unit: int
    gaia: bool
    x10: int
    y10: int
    # Creation is not checked: the spot lies in a trade area every lane's raiders reach, or
    # holds the original's marker flag.
    shared: bool = False


def center(tile: Tile) -> tuple[int, int]:
    x, y = tile
    return 10 * x + 5, 10 * y + 5


def placed(
    kind: str, tiles: tuple[Tile, ...], *, gaia: bool = False, shared: bool = False
) -> tuple[Spawned, ...]:
    return tuple(Spawned(stock(kind), gaia, *center(tile), shared) for tile in tiles)


def purchase_spawns(lane: EngineLane, purchase: Purchase, raiders: Raiders) -> tuple[Spawned, ...]:
    sites = lane.sites
    match purchase.effect:
        case Raider(medium=medium):
            unit = raiders.kind(medium).unit_id
            return tuple(
                Spawned(unit, False, *center(t), True) for t in sites.raiders[medium].tiles
            )
        case Villagers(area=where):
            # The original created bought villagers natively on these flagged tiles.
            return placed("villager", sites.villagers[where].tiles, shared=True)
        case Traders(medium=medium):
            if medium == "land":
                return placed("cart", sites.carts, shared=True)
            return placed("cog", sites.cogs, shared=True)
        case Relics():
            return placed("relic", sites.relics, gaia=True) + placed("monk", sites.monks)
        case Castle():
            # A castle's even footprint is centered on the tile corner its site names.
            x, y = sites.castle
            return (Spawned(stock("castle"), False, 10 * x, 10 * y),)
        case _:
            return ()


def free_of_population() -> tuple[int, ...]:
    """The units a lane's setup frees of population: the Kings it pays with and the relics'
    monks, with and without a relic."""
    return (stock("king"), stock("monk"), UnitInfo["MONK_WITH_RELIC"].ID)


def spawned_population(made: tuple[Spawned, ...]) -> int:
    """The population created units take: every one but the relics, which are Gaia, the
    castle, a building, and the units the lane frees."""
    free = {*free_of_population(), stock("castle")}
    return sum(1 for s in made if not s.gaia and s.unit not in free)


def creation_tiles(lane: EngineLane, shop: Shop, interaction: Interaction) -> set[Tile]:
    """Every tile a unit of the lane's appears on: the King stall, the transfer arrivals
    villagers are teleported to, the spots of bought units, the sites of a profile's starting
    towers and the islets where a rival's trebuchets arrive. Only the marked tiles may hold
    anything, their marker flags: a checked spot would stay blocked, and a teleport or an
    unchecked spot would put the unit inside whatever stands there. Enemies appear on the
    lane's spawn column without collision checks."""
    tiles = {lane.sites.king_spawn}
    tiles.update(transfer.arrival for transfer in lane.sites.transfers.values())
    tiles.update(lane.sites.siege[: interaction.siege.trebuchets_per_rival])
    tiles.update(tile for pair in lane.sites.towers for tile in pair)
    for purchase in shop.purchases:
        for spawned in purchase_spawns(lane, purchase, interaction.raiders):
            tiles.add((spawned.x10 // 10, spawned.y10 // 10))
    return tiles


def marked_tiles(lane: EngineLane) -> set[Tile]:
    """The transfer arrivals and bought villagers' spots, which keep the original's marker
    flags: villagers are teleported there, or created without a collision check."""
    tiles = {transfer.arrival for transfer in lane.sites.transfers.values()}
    tiles.update(spot for spawn in lane.sites.villagers.values() for spot in spawn.tiles)
    return tiles
