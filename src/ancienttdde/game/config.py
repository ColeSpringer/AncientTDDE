"""Validate the finite wave schedule at the JSON input boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
from ancienttdde.game.sites import LaneSites, load_sites
from ancienttdde.models import Rect

WAVE_UNITS = frozenset(
    {
        "VILLAGER_MALE",
        "MILITIA",
        "MAN_AT_ARMS",
        "LONG_SWORDSMAN",
        "TWO_HANDED_SWORDSMAN",
        "CHAMPION",
        "SPEARMAN",
        "PIKEMAN",
        "SCOUT_CAVALRY",
        "KNIGHT",
        "CAVALIER",
        "PALADIN",
        "CAMEL_RIDER",
        "WAR_ELEPHANT",
    }
)


@dataclass(frozen=True)
class WaveDefinition:
    key: str
    unit: str
    count: int
    batches: int
    interval: int
    duration: int
    hit_points: int
    boss: bool

    @property
    def object_id(self) -> int:
        return UnitInfo[self.unit].ID


# Building definitions that tower purchases may modify; anything else is rejected.
TOWER_BUILDINGS = frozenset(
    {"WATCH_TOWER", "GUARD_TOWER", "KEEP", "BOMBARD_TOWER", "DONJON", "THE_ACCURSED_TOWER"}
)
# DE stores unit hit points in 16 bits.
MAX_HIT_POINTS = 32767


@dataclass(frozen=True)
class Resources:
    food: int
    wood: int
    stone: int
    gold: int


@dataclass(frozen=True)
class Economy:
    starting_resources: Resources
    king_gold: int
    wave_kings: int
    kills_per_reward: int
    kill_stone: int
    kill_wood: int
    rewards_per_king: int
    gold_bonus: int
    food_bonus: int
    stone_bonus: int
    endless_deposit: int
    starting_relics: int


@dataclass(frozen=True)
class Towers:
    families: tuple[tuple[str, tuple[str, ...]], ...]
    special: str
    # The bonus pierce attack the game adds to the special tower, and its stock attack and range.
    special_pierce: int
    special_attack: int
    special_range: int

    def family_ids(self, family: str) -> tuple[int, ...]:
        for name, members in self.families:
            if name == family:
                return tuple(BuildingInfo[member].ID for member in members)
        raise ValueError(f"Unknown tower family: {family}")

    @property
    def special_id(self) -> int:
        return BuildingInfo[self.special].ID


@dataclass(frozen=True)
class Balance:
    lives: int
    setup_seconds: int
    preparation_seconds: int
    intermission_seconds: int
    max_enemies_per_lane: int
    sudden_death_interval: int
    sudden_death_damage: int
    economy: Economy
    towers: Towers
    waves: tuple[WaveDefinition, ...]

    @property
    def scheduled_seconds(self) -> int:
        return (
            self.setup_seconds
            + self.preparation_seconds
            + sum(w.duration for w in self.waves)
            + self.intermission_seconds * (len(self.waves) - 1)
        )


def tower(name: object) -> str:
    if not isinstance(name, str) or name not in TOWER_BUILDINGS:
        raise ValueError(f"Not a tower: {name}")
    return name


def load_economy(raw: dict[str, object]) -> Economy:
    start = object_value(raw.get("starting_resources"), "starting_resources")
    kills = object_value(raw.get("kill_reward"), "kill_reward")
    bonus = object_value(raw.get("resource_bonus"), "resource_bonus")
    return Economy(
        starting_resources=Resources(
            *(integer(start, name, 0, 30000) for name in ("food", "wood", "stone", "gold"))
        ),
        king_gold=integer(raw, "king_gold", 1, 30000),
        wave_kings=integer(raw, "wave_kings", 0, 10),
        kills_per_reward=integer(kills, "kills", 1, 1000),
        kill_stone=integer(kills, "stone", 0, 10000),
        kill_wood=integer(kills, "wood", 0, 10000),
        rewards_per_king=integer(kills, "rewards_per_king", 1, 100),
        gold_bonus=integer(bonus, "gold", 0, 30000),
        food_bonus=integer(bonus, "food", 0, 30000),
        stone_bonus=integer(bonus, "stone", 0, 30000),
        # Larger amounts wrap around: DE applies resource storage as a 16-bit value.
        endless_deposit=integer(raw, "endless_deposit", 1, 32767),
        starting_relics=integer(raw, "starting_relics", 0, 2),
    )


def load_towers(raw: dict[str, object]) -> Towers:
    families: list[tuple[str, tuple[str, ...]]] = []
    for name, members in object_value(raw.get("families"), "families").items():
        if not isinstance(members, list) or not members:
            raise ValueError(f"Tower family needs members: {name}")
        families.append((name, tuple(tower(m) for m in cast(list[object], members))))
    special = object_value(raw.get("special"), "special")
    return Towers(
        families=tuple(families),
        special=tower(special.get("unit")),
        special_pierce=integer(special, "pierce_bonus", 0, 1000),
        special_attack=integer(special, "attack", 0, 1000),
        special_range=integer(special, "range", 1, 20),
    )


def load_balance(path: Path) -> Balance:
    raw = read_object(path)
    if integer(raw, "schema_version", 2, 2) != 2:
        raise ValueError("Unsupported balance schema")
    waves: list[WaveDefinition] = []
    for row in rows(raw.get("waves"), "waves"):
        key, unit = text_field(row, "key"), text_field(row, "unit")
        if unit not in WAVE_UNITS:
            raise ValueError(f"Unknown wave unit: {unit}")
        boss = row.get("boss")
        if type(boss) is not bool:
            raise ValueError("boss must be a boolean")
        wave = WaveDefinition(
            key=key,
            unit=unit,
            boss=boss,
            count=integer(row, "count", 1, 5),
            batches=integer(row, "batches", 1, 80),
            interval=integer(row, "interval", 2, 120),
            duration=integer(row, "duration", 1, 600),
            hit_points=integer(row, "hit_points", 1, MAX_HIT_POINTS),
        )
        if (wave.batches - 1) * wave.interval >= wave.duration:
            raise ValueError(f"Wave duration cannot contain all batches: {key}")
        if key in {w.key for w in waves}:
            raise ValueError(f"Duplicate wave key: {key}")
        waves.append(wave)
    if not waves or len(waves) > 30 or not waves[-1].boss:
        raise ValueError("waves must contain 1–30 entries ending in a boss")
    return Balance(
        lives=integer(raw, "lives", 1, 100),
        setup_seconds=integer(raw, "setup_seconds", 2, 30),
        preparation_seconds=integer(raw, "preparation_seconds", 1, 600),
        intermission_seconds=integer(raw, "intermission_seconds", 1, 120),
        max_enemies_per_lane=integer(raw, "max_enemies_per_lane", 5, 100),
        sudden_death_interval=integer(raw, "sudden_death_interval", 1, 60),
        sudden_death_damage=integer(raw, "sudden_death_damage", 1, 10),
        economy=load_economy(object_value(raw.get("economy"), "economy")),
        towers=load_towers(object_value(raw.get("towers"), "towers")),
        waves=tuple(waves),
    )


@dataclass(frozen=True)
class EngineLane:
    player: int
    spawn_x: int
    center_y: int
    exit_x: int
    path: Rect
    economy: Rect
    life_reference: int
    land_trade_partner: int
    water_trade_partner: int
    sites: LaneSites


def load_lanes(anchors: dict[str, object]) -> tuple[EngineLane, ...]:
    result: list[EngineLane] = []
    for player in range(1, 8):
        prefix = f"lane.p{player}"
        coordinates: dict[str, list[int]] = {}
        for name, field, length in (
            ("spawn", "point", 2),
            ("exit", "point", 2),
            ("path", "region", 4),
            ("economy", "region", 4),
        ):
            value = object_value(anchors.get(f"{prefix}.{name}"), name).get(field)
            if not isinstance(value, list):
                raise ValueError(f"Missing lane coordinates: {prefix}.{name}")
            items = cast(list[object], value)
            if len(items) != length or any(type(v) not in (int, float) for v in items):
                raise ValueError(f"Invalid lane coordinates: {prefix}.{name}")
            numbers = [int(cast(int | float, v)) for v in items]
            if any(v < 0 or v >= 200 for v in numbers):
                raise ValueError(f"Lane outside map: {prefix}")
            coordinates[name] = numbers
        x1, y1, x2, y2 = coordinates["path"]
        sx, sy = coordinates["spawn"]
        ex, ey = coordinates["exit"]
        if not (x1 <= sx < ex <= x2 and y1 <= sy == ey <= y2):
            raise ValueError(f"Invalid lane route: {prefix}")
        ax1, ay1, ax2, ay2 = coordinates["economy"]
        if not (ax1 <= ax2 and ay1 <= ay2):
            raise ValueError(f"Invalid economy region: {prefix}")
        life = object_value(anchors.get(f"{prefix}.life"), "life")
        land = object_value(anchors.get(f"trade.land.p{player}.partner"), "land trade partner")
        water = object_value(anchors.get(f"trade.water.p{player}.partner"), "water trade partner")
        result.append(
            EngineLane(
                player=player,
                spawn_x=sx,
                center_y=sy,
                exit_x=ex,
                path=(x1, y1, x2, y2),
                economy=(ax1, ay1, ax2, ay2),
                life_reference=integer(life, "reference_id", 0, 2**31 - 1),
                land_trade_partner=integer(land, "reference_id", 0, 2**31 - 1),
                water_trade_partner=integer(water, "reference_id", 0, 2**31 - 1),
                sites=load_sites(anchors, player),
            )
        )
    return tuple(result)
