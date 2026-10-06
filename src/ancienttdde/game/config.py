"""Validate the finite wave schedule at the JSON input boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
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


@dataclass(frozen=True)
class Balance:
    lives: int
    setup_seconds: int
    preparation_seconds: int
    intermission_seconds: int
    income_interval: int
    income_amount: int
    starting_resources: int
    tower_attack_bonus: int
    max_enemies_per_lane: int
    sudden_death_interval: int
    sudden_death_damage: int
    waves: tuple[WaveDefinition, ...]

    @property
    def scheduled_seconds(self) -> int:
        return (
            self.setup_seconds
            + self.preparation_seconds
            + sum(w.duration for w in self.waves)
            + self.intermission_seconds * (len(self.waves) - 1)
        )


def load_balance(path: Path) -> Balance:
    raw = read_object(path)
    if integer(raw, "schema_version", 1, 1) != 1:
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
            hit_points=integer(row, "hit_points", 1, 10000),
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
        income_interval=integer(raw, "income_interval", 1, 60),
        income_amount=integer(raw, "income_amount", 1, 1000),
        starting_resources=integer(raw, "starting_resources", 1, 10000),
        tower_attack_bonus=integer(raw, "tower_attack_bonus", 0, 100),
        max_enemies_per_lane=integer(raw, "max_enemies_per_lane", 5, 100),
        sudden_death_interval=integer(raw, "sudden_death_interval", 1, 60),
        sudden_death_damage=integer(raw, "sudden_death_damage", 1, 10),
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
            )
        )
    return tuple(result)
