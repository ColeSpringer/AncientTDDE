"""The anchors the game's economy and shop use describe open, reachable map positions."""

import json
import math
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pytest

from ancienttdde.map.foundation import migrate_map
from ancienttdde.map.geometry import Cell, cells, flood, footprint, neighbors
from ancienttdde.map.models import FoundationConfig, MapAnchor, MapDocument

ROOT = Path(__file__).resolve().parents[1]
PLAYERS = range(1, 8)
HAY_STACK = 857
CASTLE_SIZE = 4


@cache
def content() -> tuple[MapDocument, FoundationConfig]:
    legacy = json.loads((ROOT / "content/maps/legacy-map.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8"))
    return migrate_map(legacy, config), config


def anchor(key: str) -> MapAnchor:
    data, _ = content()
    return data.get("anchors", {})[key]


def points(key: str) -> list[list[float]]:
    return anchor(key).get("points", [])


def tile(point: list[float]) -> Cell:
    return math.floor(point[0]), math.floor(point[1])


def rect(key: str) -> tuple[int, int, int, int]:
    values = anchor(key).get("region")
    assert values is not None and len(values) == 4, f"{key} has no region"
    x1, y1, x2, y2 = values
    return x1, y1, x2, y2


def region(key: str) -> set[Cell]:
    return cells(rect(key))


def point(key: str) -> list[float]:
    value = anchor(key).get("point")
    assert value is not None, f"{key} has no point"
    return value


@cache
def blocked() -> frozenset[Cell]:
    data, config = content()
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    return frozenset(c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0)))


@cache
def terrain(medium: str) -> frozenset[Cell]:
    data, config = content()
    allowed = config["land_terrain"] if medium == "land" else config["water_terrain"]
    width = data["map"]["width"]
    return frozenset(
        (i % width, i // width) for i, t in enumerate(data["map"]["tiles"]) if t[0] in allowed
    )


def open_ground(medium: str = "land") -> frozenset[Cell]:
    return terrain(medium) - blocked()


def reachable(start: Iterable[Cell], medium: str = "land") -> set[Cell]:
    return flood(set(start), set(open_ground(medium)))


def lane_y(player: int) -> int:
    return 15 + 28 * (player - 1)


def placed(stock_id: int, owner: int, area: set[Cell]) -> list[Cell]:
    data, _ = content()
    return [
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in data["units"]
        if u["unit_const"] == stock_id
        and u["player_id"] == owner
        and (math.floor(u["x"]), math.floor(u["y"])) in area
    ]


@pytest.mark.parametrize("player", PLAYERS)
def test_reserved_special_tower_pads_hold_one_hay_stack(player: int) -> None:
    cy = lane_y(player)
    for side, y in (("left", cy - 3), ("right", cy + 3)):
        pad = region(f"lane.p{player}.special.{side}")
        assert pad == {(33, y)}
        assert placed(HAY_STACK, 0, pad) == [(33, y)]
        build = "north" if side == "left" else "south"
        assert pad <= region(f"lane.p{player}.build.{build}")


@pytest.mark.parametrize("player", PLAYERS)
def test_kings_arrive_at_their_stall_and_walk_into_the_shop(player: int) -> None:
    spawn, rally = (tile(p) for p in points(f"lane.p{player}.kings"))
    assert spawn == (158 - 4 * (player - 1), 3)
    assert spawn in open_ground() and rally in open_ground()
    shop = rect("shop.bounds")
    assert rally in reachable([spawn])
    assert rally[1] >= shop[1] and shop[0] <= rally[0] <= shop[2]


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize(
    ("transfer", "source", "destination"),
    [
        ("build", "economy", "build.south"),
        ("economy", "build.north", "economy"),
        ("north", "build.south", "build.north"),
        ("south", "build.north", "build.south"),
    ],
)
def test_transfer_pads_join_separate_areas(
    player: int, transfer: str, source: str, destination: str
) -> None:
    key = f"lane.p{player}.transfer.{transfer}"
    pad = region(key)
    arrival, walk = (tile(p) for p in points(key))
    villagers = placed(83, player, region(f"lane.p{player}.{source}")) + placed(
        293, player, region(f"lane.p{player}.{source}")
    )
    assert villagers, f"no villagers start in {source}"
    start = reachable(villagers)
    # A villager can step onto the pad, and arrives where it cannot walk back.
    assert {n for c in pad for n in neighbors(c)} & start
    assert arrival in open_ground() and walk in open_ground()
    assert walk in reachable([arrival])
    assert not reachable([arrival]) & pad
    area = region(f"lane.p{player}.{destination}")
    assert walk in area or walk in reachable(area & open_ground())


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize("resource", ["gold", "food", "stone"])
def test_resource_bonuses_wait_behind_their_deposits(player: int, resource: str) -> None:
    data, _ = content()
    bonus = region(f"lane.p{player}.bonus.{resource}")
    villagers = placed(83, player, region(f"lane.p{player}.economy"))
    # Before gathering, the end of the rows is out of reach; clearing the deposits opens it.
    assert not reachable(villagers) & bonus
    deposits = {66, 59, 102}
    mined = {
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in data["units"]
        if u["unit_const"] in deposits and u["player_id"] == 0
    }
    assert flood(set(villagers), set(open_ground()) | (mined & terrain("land"))) & bonus
    for point in points(f"lane.p{player}.endless.{resource}"):
        cell = tile(point)
        assert cell in open_ground(), f"{resource} deposit at {cell} is blocked"
        assert cell in region(f"lane.p{player}.economy")


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize("area", ["build", "economy"])
def test_bought_villagers_arrive_in_their_area(player: int, area: str) -> None:
    *spawns, walk = (tile(p) for p in points(f"lane.p{player}.villagers.{area}"))
    assert len(spawns) == 2
    assert all(s in open_ground() for s in spawns) and walk in open_ground()
    assert walk in reachable(spawns)


@pytest.mark.parametrize("player", PLAYERS)
def test_monks_reach_bought_relics_and_their_monasteries(player: int) -> None:
    relics = [tile(p) for p in points(f"lane.p{player}.relics")]
    monks = [tile(p) for p in points(f"lane.p{player}.monks")]
    assert len(relics) == 3 and len(monks) == 2
    assert set(relics) <= region(f"lane.p{player}.relics")
    walkable = reachable(monks)
    assert set(relics) <= walkable
    data, _ = content()
    units = {u["reference_id"]: u for u in data["units"]}
    for index in (1, 2):
        monastery = anchor(f"lane.p{player}.monastery.{index}")
        unit = units[monastery.get("reference_id", -1)]
        assert unit["player_id"] == player and unit["unit_const"] == 104
        perimeter = {n for c in footprint(unit, 3) for n in neighbors(c)}
        assert perimeter & walkable


@pytest.mark.parametrize("player", PLAYERS)
def test_castle_sites_are_clear_land(player: int) -> None:
    x, y = point(f"lane.p{player}.castle")
    site = footprint({"x": x, "y": y}, CASTLE_SIZE)
    assert len(site) == CASTLE_SIZE**2
    assert site <= open_ground()


@pytest.mark.parametrize("player", PLAYERS)
def test_relic_enclosures_hold_twenty_relics_and_their_monks(player: int) -> None:
    enclosure = region(f"lane.p{player}.relic_enclosure")
    assert len(placed(285, 0, enclosure)) == 20
    assert len(placed(104, 0, enclosure)) == 2
    assert len(placed(125, 0, enclosure)) == 2


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize(
    ("kind", "medium", "route"), [("carts", "land", "land"), ("cogs", "water", "water")]
)
def test_bought_traders_reach_their_partner(
    player: int, kind: str, medium: str, route: str
) -> None:
    data, config = content()
    spawns = [tile(p) for p in points(f"lane.p{player}.{kind}")]
    assert len(spawns) == 3
    assert all(s in open_ground(medium) for s in spawns)
    partner = anchor(f"trade.{route}.p{player}.partner")
    units = {u["reference_id"]: u for u in data["units"]}
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    unit = units[partner.get("reference_id", -1)]
    occupied = footprint(unit, sizes[unit["unit_const"]])
    perimeter = {n for c in occupied for n in neighbors(c)} - occupied
    assert perimeter & reachable(spawns, medium)
