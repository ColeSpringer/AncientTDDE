"""The stock DE data snapshot the balance model reads: towers, enemies, raiders, siege, techs.

`tools/dat/stock_stats.py` writes the snapshot from the installed game's data file; the loader
only checks it. Attack and armor values are per damage class, as the data file keeps them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.techs import TechInfo

from ancienttdde.common.data import digest, integer, object_value, read_object, rows, text_field
from ancienttdde.game.config import RAIDERS, TOWER_BUILDINGS, WAVE_UNITS

# DE's damage classes the model reads.
PIERCE_CLASS = 3
MELEE_CLASS = 4
BUILDING_CLASS = 11
# The unit class of towers in the data file.
TOWER_CLASS = 52
# Technologies whose availability the snapshot records for every civilization. The fire ship
# upgrade is the War Galley technology, which the dataset does not name.
WATCHED_TECHNOLOGIES: dict[str, int] = {
    name: TechInfo[name].ID
    for name in (
        "FLETCHING",
        "BODKIN_ARROW",
        "BRACER",
        "CHEMISTRY",
        "ARROWSLITS",
        "HEATED_SHOT",
        "MASONRY",
        "ARCHITECTURE",
        "TREADMILL_CRANE",
        "SIEGE_ENGINEERS",
        "MURDER_HOLES",
        "BALLISTICS",
        "GUILDS",
        "CARAVAN",
        "STONE_MINING",
        "STONE_SHAFT_MINING",
        "GOLD_MINING",
        "GOLD_SHAFT_MINING",
        "WHEELBARROW",
        "HAND_CART",
        "SANCTITY",
        "FERVOR",
        "HERBAL_MEDICINE",
        "TOWN_WATCH",
        "GUARD_TOWER",
        "KEEP",
        "BOMBARD_TOWER",
        "LIGHT_CAVALRY",
        "HUSSAR",
        "WINGED_HUSSAR",
        "FAST_FIRE_SHIP",
        "CASTLE_AGE",
        "IMPERIAL_AGE",
    )
} | {"WAR_GALLEY": 34}
REQUIRED_UNITS = frozenset(
    TOWER_BUILDINGS
    | WAVE_UNITS
    | RAIDERS["land"]
    | RAIDERS["naval"]
    | {
        "TREBUCHET",
        "TREBUCHET_PACKED",
        "TRADE_CART_EMPTY",
        "TRADE_COG",
        "KING",
        "MONK",
        "RELIC",
        "GOLD_MINE",
        "STONE_MINE",
        "FORAGE_BUSH",
        "TREE_A",
        "OUTPOST",
        "CASTLE",
    }
)
RESOURCE_NAMES = ("food", "wood", "stone", "gold")


def class_amount(value: float) -> tuple[int, float]:
    """Unpack a data-file attack or armor value: |value| = class * 256 + amount, signed amount."""
    magnitude = abs(value)
    damage_class = int(magnitude // 256)
    amount = magnitude - damage_class * 256
    amount = -amount if value < 0 else amount
    return damage_class, int(amount) if amount == int(amount) else amount


@dataclass(frozen=True)
class StockSource:
    file: str
    version: str
    sha256: str
    civilizations: int


@dataclass(frozen=True)
class StockCivilization:
    id: int
    name: str
    # Watched technologies the civilization can never research.
    lacks: frozenset[str]


@dataclass(frozen=True)
class StockUnit:
    id: int
    hit_points: int
    attacks: tuple[tuple[int, float], ...]
    armors: tuple[tuple[int, float], ...]
    reload: float
    range: float
    min_range: float
    accuracy: int
    speed: float
    line_of_sight: float
    cost: Mapping[str, int]
    build_time: int
    work_rate: float
    storage: int

    def attack(self, damage_class: int) -> float:
        return sum(amount for found, amount in self.attacks if found == damage_class)

    def armor(self, damage_class: int) -> float:
        return sum(amount for found, amount in self.armors if found == damage_class)


@dataclass(frozen=True)
class TowerEffects:
    """What a technology does to the Watch Tower, as a stand-in for the tower family."""

    attack: int = 0
    range: int = 0
    hit_points_percent: int = 0
    melee_armor: int = 0
    pierce_armor: int = 0
    minimum_range_removed: bool = False


@dataclass(frozen=True)
class StockTechnology:
    id: int
    cost: Mapping[str, int]
    time: int
    towers: TowerEffects


@dataclass(frozen=True)
class Stock:
    source: StockSource
    civilizations: tuple[StockCivilization, ...]
    units: Mapping[str, StockUnit]
    technologies: Mapping[str, StockTechnology]
    relic_gold_per_minute: int

    def unit(self, name: str) -> StockUnit:
        return self.units[name]

    def technology(self, name: str) -> StockTechnology:
        return self.technologies[name]

    def find(self, civilization_id: int) -> StockCivilization | None:
        """The civilization's record, or None when the snapshot predates it."""
        for civilization in self.civilizations:
            if civilization.id == civilization_id:
                return civilization
        return None

    def civilization(self, civilization_id: int) -> StockCivilization:
        found = self.find(civilization_id)
        if found is None:
            raise ValueError(f"Stock snapshot has no civilization {civilization_id}")
        return found


def number(row: dict[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if type(value) not in (int, float):
        raise ValueError(f"{key} must be a number")
    return cast(int | float, value)


def pairs(row: dict[str, object], key: str) -> tuple[tuple[int, float], ...]:
    value = row.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must list [class, amount] pairs")
    found: list[tuple[int, float]] = []
    for item in cast(list[object], value):
        pair = cast(list[object], item) if isinstance(item, list) else []
        if len(pair) != 2 or type(pair[0]) is not int or type(pair[1]) not in (int, float):
            raise ValueError(f"{key} must list [class, amount] pairs")
        found.append((pair[0], cast(int | float, pair[1])))
    return tuple(found)


def costs(row: dict[str, object], key: str) -> dict[str, int]:
    cost = object_value(row.get(key, {}), key)
    for resource in cost:
        if resource not in RESOURCE_NAMES:
            raise ValueError(f"{key} must name {', '.join(RESOURCE_NAMES)}")
    return {resource: integer(cost, resource, 0, 100000) for resource in cost}


def load_unit(raw: dict[str, object]) -> StockUnit:
    return StockUnit(
        id=integer(raw, "id", 0, 100000),
        hit_points=integer(raw, "hit_points", 0, 32767),
        attacks=pairs(raw, "attack"),
        armors=pairs(raw, "armor"),
        reload=number(raw, "reload"),
        range=number(raw, "range"),
        min_range=number(raw, "min_range"),
        accuracy=integer(raw, "accuracy", 0, 100) if "accuracy" in raw else 100,
        speed=number(raw, "speed"),
        line_of_sight=number(raw, "line_of_sight"),
        cost=costs(raw, "cost"),
        build_time=integer(raw, "build_time", 0, 10000) if "build_time" in raw else 0,
        work_rate=number(raw, "work_rate"),
        storage=integer(raw, "storage", 0, 100000) if "storage" in raw else 0,
    )


def load_technology(raw: dict[str, object]) -> StockTechnology:
    towers = object_value(raw.get("towers", {}), "towers")
    removed = towers.get("minimum_range_removed", False)
    if type(removed) is not bool:
        raise ValueError("minimum_range_removed must be a boolean")
    return StockTechnology(
        id=integer(raw, "id", 0, 100000),
        cost=costs(raw, "cost"),
        time=integer(raw, "time", 0, 10000) if "time" in raw else 0,
        towers=TowerEffects(
            attack=integer(towers, "attack", -100, 100) if "attack" in towers else 0,
            range=integer(towers, "range", -100, 100) if "range" in towers else 0,
            hit_points_percent=integer(towers, "hit_points_percent", -100, 1000)
            if "hit_points_percent" in towers
            else 0,
            melee_armor=integer(towers, "melee_armor", -100, 100) if "melee_armor" in towers else 0,
            pierce_armor=integer(towers, "pierce_armor", -100, 100)
            if "pierce_armor" in towers
            else 0,
            minimum_range_removed=removed,
        ),
    )


def load_stock(path: Path) -> Stock:
    raw = read_object(path)
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported stock schema")
    source = object_value(raw.get("source"), "source")
    technologies = {
        name: load_technology(object_value(row, name))
        for name, row in object_value(raw.get("technologies"), "technologies").items()
    }
    for name in WATCHED_TECHNOLOGIES:
        if name not in technologies:
            raise ValueError(f"Stock snapshot lacks a technology: {name}")
    units = {
        name: load_unit(object_value(row, name))
        for name, row in object_value(raw.get("units"), "units").items()
    }
    for name in sorted(REQUIRED_UNITS):
        if name not in units:
            raise ValueError(f"Stock snapshot lacks a unit: {name}")
    civilizations: list[StockCivilization] = []
    for row in rows(raw.get("civilizations"), "civilizations"):
        identifier = integer(row, "id", 1, 255)
        if identifier in {c.id for c in civilizations}:
            raise ValueError(f"Duplicate civilization id: {identifier}")
        lacks = row.get("lacks", [])
        if not isinstance(lacks, list):
            raise ValueError("lacks must list technology names")
        names: set[str] = set()
        for name in cast(list[object], lacks):
            if not isinstance(name, str) or name not in technologies:
                raise ValueError(f"Civilization {identifier} lacks an unlisted technology: {name}")
            names.add(name)
        civilizations.append(
            StockCivilization(identifier, text_field(row, "name"), frozenset(names))
        )
    return Stock(
        source=StockSource(
            file=text_field(source, "file"),
            version=text_field(source, "version"),
            sha256=digest(source.get("sha256")),
            civilizations=integer(source, "civilizations", 1, 1000),
        ),
        civilizations=tuple(civilizations),
        units=units,
        technologies=technologies,
        relic_gold_per_minute=integer(raw, "relic_gold_per_minute", 0, 10000),
    )
