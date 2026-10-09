"""Conservative tile connectivity checks; the game remains the pathing authority."""

import math
from collections import deque
from typing import TypedDict

from ancienttdde.map.models import (
    FoundationConfig,
    IsolationResult,
    MapAnchor,
    MapDocument,
    MapValidation,
    RouteResult,
)
from ancienttdde.models import Rect
from ancienttdde.scenario.snapshot import MapUnit

type Cell = tuple[int, int]


class Position(TypedDict):
    """A stored object position; a placed unit is one."""

    x: float
    y: float


def bounds(values: list[int], width: int, height: int) -> Rect:
    if len(values) != 4 or any(type(v) is not int for v in values):
        raise ValueError(f"Invalid region: {values}")
    x1, y1, x2, y2 = values
    if not (0 <= x1 <= x2 < width and 0 <= y1 <= y2 < height):
        raise ValueError(f"Region outside map: {values}")
    return x1, y1, x2, y2


def cells(region: Rect) -> set[Cell]:
    x1, y1, x2, y2 = region
    return {(x, y) for y in range(y1, y2 + 1) for x in range(x1, x2 + 1)}


def blocking_sizes(config: FoundationConfig) -> dict[int, int]:
    """Each mapped stock object's conservative footprint: the tiles a side it blocks."""
    return {
        row["stock_id"]: row.get("blocking_size", 0)
        for row in config["objects"]
        if row["stock_id"] is not None
    }


def footprint(unit: Position, size: int) -> set[Cell]:
    x1 = math.ceil(unit["x"] - size / 2)
    y1 = math.ceil(unit["y"] - size / 2)
    return {(x, y) for y in range(y1, y1 + size) for x in range(x1, x1 + size)}


def neighbors(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    x, y = cell
    return (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)


def flood(start: set[Cell], walkable: set[Cell]) -> set[Cell]:
    visited = start & walkable
    pending = deque(visited)
    while pending:
        for adjacent in neighbors(pending.popleft()):
            if adjacent in walkable and adjacent not in visited:
                visited.add(adjacent)
                pending.append(adjacent)
    return visited


def anchor_cells(anchor: MapAnchor, units: dict[int, MapUnit], sizes: dict[int, int]) -> set[Cell]:
    """Building endpoints are reached at their perimeter, not through their center."""
    if "reference_id" in anchor:
        unit = units[anchor["reference_id"]]
        occupied = footprint(unit, sizes[unit["unit_const"]])
        if occupied:
            return {n for cell in occupied for n in neighbors(cell)} - occupied
    if "point" in anchor:
        x, y = anchor["point"]
        return {(math.floor(x), math.floor(y))}
    region = anchor.get("region")
    if region is None:
        points = anchor.get("points", [])
        if not points:
            raise ValueError("Route anchor needs a point or region")
        return {(math.floor(x), math.floor(y)) for x, y in points}
    x1, y1, x2, y2 = region
    return cells((x1, y1, x2, y2))


def check_connectivity(data: MapDocument, config: FoundationConfig) -> MapValidation:
    width, height = data["map"]["width"], data["map"]["height"]
    units = {u["reference_id"]: u for u in data["units"]}
    sizes = blocking_sizes(config)
    blocked = {cell for u in units.values() for cell in footprint(u, sizes[u["unit_const"]])}
    terrain_ids = {"land": config["land_terrain"], "water": config["water_terrain"]}
    walkable = {
        medium: {
            (i % width, i // width)
            for i, tile in enumerate(data["map"]["tiles"])
            if tile[0] in terrain_ids[medium]
        }
        - blocked
        for medium in ("land", "water")
    }
    anchors = data.get("anchors", {})
    routes: list[RouteResult] = []
    for route in config["routes"]:
        allowed = cells(bounds(route["region"], width, height))
        traversable = walkable[route["medium"]] & allowed
        start = anchor_cells(anchors[route["start"]], units, sizes)
        end = anchor_cells(anchors[route["end"]], units, sizes)
        reached = flood(start, traversable)
        if not reached & end:
            raise ValueError(f"{route['key']}: blocked {route['medium']} route")
        routes.append({"key": route["key"], "reachable": True, "reachable_tiles": len(reached)})
    isolation: list[IsolationResult] = []
    for check in config["isolation"]:
        allowed = cells(bounds(check["region"], width, height))
        reached = flood(
            anchor_cells(anchors[check["start"]], units, sizes), walkable[check["medium"]]
        )
        if not reached or not reached.issubset(allowed):
            raise ValueError(f"{check['key']}: failed {check['medium']} isolation")
        isolation.append({"key": check["key"], "contained": True, "reachable_tiles": len(reached)})
    return {"routes": routes, "isolation": isolation, "in_game_verified": False}
