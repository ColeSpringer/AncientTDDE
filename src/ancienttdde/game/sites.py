"""The map positions a lane's economy and shop act on, read from the map anchors."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from ancienttdde.common.data import object_value
from ancienttdde.models import Rect

# A tile, as trigger effects address it.
type Tile = tuple[int, int]
RESOURCES = ("gold", "food", "stone")
TRANSFERS = ("build", "economy", "north", "south")


@dataclass(frozen=True)
class Transfer:
    """A villager standing on the pad reappears at the arrival and walks clear of it."""

    pad: Rect
    arrival: Tile
    walk: Tile


@dataclass(frozen=True)
class Spawn:
    """Where bought units appear, and where they walk so the next ones are not blocked."""

    tiles: tuple[Tile, ...]
    walk: Tile


@dataclass(frozen=True)
class LaneSites:
    special: Mapping[str, Tile]
    king_spawn: Tile
    king_rally: Tile
    transfers: Mapping[str, Transfer]
    bonuses: Mapping[str, Rect]
    endless: Mapping[str, tuple[Tile, ...]]
    villagers: Mapping[str, Spawn]
    relics: tuple[Tile, ...]
    # The tiles bought relics wait on until the lane's monks collect them.
    relic_column: Rect
    monks: tuple[Tile, ...]
    monasteries: tuple[int, ...]
    castle: Tile
    relic_enclosure: Rect
    carts: tuple[Tile, ...]
    cogs: tuple[Tile, ...]
    expansion: Mapping[str, tuple[Rect, Rect]]


def anchor(anchors: Mapping[str, object], key: str) -> dict[str, object]:
    return object_value(anchors.get(key), key)


def numbers(value: object, key: str, length: int) -> list[float]:
    items = cast(list[object], value) if isinstance(value, list) else []
    if len(items) != length or any(type(v) not in (int, float) for v in items):
        raise ValueError(f"Invalid anchor coordinates: {key}")
    return [float(cast(int | float, v)) for v in items]


def region(anchors: Mapping[str, object], key: str) -> Rect:
    x1, y1, x2, y2 = (int(v) for v in numbers(anchor(anchors, key).get("region"), key, 4))
    return x1, y1, x2, y2


def tiles(anchors: Mapping[str, object], key: str) -> tuple[Tile, ...]:
    """The tiles holding an anchor's points, in order."""
    found = anchor(anchors, key).get("points")
    items = cast(list[object], found) if isinstance(found, list) else []
    if not items:
        raise ValueError(f"Anchor needs points: {key}")
    points = [numbers(item, key, 2) for item in items]
    return tuple((math.floor(x), math.floor(y)) for x, y in points)


def single(anchors: Mapping[str, object], key: str) -> Tile:
    x1, y1, x2, y2 = region(anchors, key)
    if (x1, y1) != (x2, y2):
        raise ValueError(f"Anchor must be a single tile: {key}")
    return x1, y1


def spawn(anchors: Mapping[str, object], key: str) -> Spawn:
    *places, walk = tiles(anchors, key)
    return Spawn(tuple(places), walk)


def reference(anchors: Mapping[str, object], key: str) -> int:
    value = anchor(anchors, key).get("reference_id")
    if type(value) is not int or value < 0:
        raise ValueError(f"Anchor needs a placed instance: {key}")
    return value


def load_sites(anchors: Mapping[str, object], player: int) -> LaneSites:
    prefix = f"lane.p{player}"
    transfers: dict[str, Transfer] = {}
    for name in TRANSFERS:
        key = f"{prefix}.transfer.{name}"
        arrival, walk = tiles(anchors, key)
        transfers[name] = Transfer(region(anchors, key), arrival, walk)
    king_spawn, king_rally = tiles(anchors, f"{prefix}.kings")
    x, y = numbers(anchor(anchors, f"{prefix}.castle").get("point"), f"{prefix}.castle", 2)
    return LaneSites(
        special={side: single(anchors, f"{prefix}.special.{side}") for side in ("left", "right")},
        king_spawn=king_spawn,
        king_rally=king_rally,
        transfers=transfers,
        bonuses={name: region(anchors, f"{prefix}.bonus.{name}") for name in RESOURCES},
        endless={name: tiles(anchors, f"{prefix}.endless.{name}") for name in RESOURCES},
        villagers={
            area: spawn(anchors, f"{prefix}.villagers.{area}") for area in ("build", "economy")
        },
        relics=tiles(anchors, f"{prefix}.relics"),
        relic_column=region(anchors, f"{prefix}.relics"),
        monks=tiles(anchors, f"{prefix}.monks"),
        monasteries=tuple(reference(anchors, f"{prefix}.monastery.{i}") for i in (1, 2)),
        castle=(int(x), int(y)),
        relic_enclosure=region(anchors, f"{prefix}.relic_enclosure"),
        carts=tiles(anchors, f"{prefix}.carts"),
        cogs=tiles(anchors, f"{prefix}.cogs"),
        expansion={
            row: (
                region(anchors, f"{prefix}.expansion.{row}.north"),
                region(anchors, f"{prefix}.expansion.{row}.south"),
            )
            for row in ("third", "fourth")
        },
    )
