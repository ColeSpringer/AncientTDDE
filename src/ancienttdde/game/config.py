"""Validate the finite wave schedule at the JSON input boundary."""

from collections.abc import Collection
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.heroes import HeroInfo
from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
from ancienttdde.game.restricted import POINTLESS, TECHNOLOGIES
from ancienttdde.game.sites import LaneSites, RaiderMedium, Tile, TradeMedium, load_sites
from ancienttdde.models import Rect
from ancienttdde.scenario.objects import technology

# DE stores unit hit points in 16 bits. A boss may carry more: its current hit points are
# a float the engine keeps, so the XS tops a boss up after creating it.
MAX_HIT_POINTS = 32767
BOSS_HIT_POINTS = 5_000_000
# The schedule may hold this many waves; every wave is a trigger per difficulty level.
MAX_WAVES = 60
# A batch stands side by side across the lane: one row above and below its center, or three
# rows. The lane's path must hold those rows.
MAX_BATCH = 3
PATH_ROWS = 3


def wave_unit(name: str) -> int:
    """The object ID of a wave unit: a unit or a hero the pinned dataset names, other than
    the King the shop counts."""
    if name == "KING":
        raise ValueError("The King is the shop's currency, not a wave unit")
    for dataset in (UnitInfo, HeroInfo):
        if name in dataset.__members__:
            return dataset[name].ID
    raise ValueError(f"Unknown wave unit: {name}")


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
    # The pierce armor the enemies carry instead of the unit's own, when the schedule says.
    pierce_armor: int | None = None

    @property
    def object_id(self) -> int:
        return wave_unit(self.unit)

    @property
    def enemies(self) -> int:
        return self.count * self.batches


# Building definitions that tower purchases may modify; anything else is rejected.
TOWER_BUILDINGS = frozenset(
    {"WATCH_TOWER", "GUARD_TOWER", "KEEP", "BOMBARD_TOWER", "DONJON", "THE_ACCURSED_TOWER"}
)
# Ages and tower upgrades are granted by the game or sold at the shop, never given at the start.
RESERVED_TECHNOLOGIES = frozenset(
    {"FEUDAL_AGE", "CASTLE_AGE", "IMPERIAL_AGE", "GUARD_TOWER", "KEEP", "BOMBARD_TOWER"}
)
# Technologies every lane rules out. Conversions of monks and buildings, and a longer
# conversion range:
CONVERSIONS = ("ATONEMENT", "REDEMPTION", "BLOCK_PRINTING")
# range that would carry castle arrows and fire ships past the walls:
WALL_RANGE = ("CRENELLATIONS", "GREEK_FIRE")
# castle technologies that would multiply every tower's volley, far beyond any profile:
TOWER_MULTIPLIERS = ("YASAMA", "STRONGHOLD")
# and, in competitive games only, two more tiles of tower range: with Fletching, Bodkin Arrow
# and Bracer, towers reach 11 tiles, and the nearest tiles of the next lane are 12 away.
TOWER_RANGE = ("EUPSEONG", "ARTILLERY")
# What every game rules out, and what no lane may research or be granted.
RULED_OUT = CONVERSIONS + WALL_RANGE + TOWER_MULTIPLIERS
UNRESEARCHABLE = frozenset(RULED_OUT + TOWER_RANGE)
# DE's lobby difficulty settings, as xsGetDifficulty reports them.
LOBBY_DIFFICULTIES = {
    "extreme": -1,
    "hardest": 0,
    "hard": 1,
    "moderate": 2,
    "standard": 3,
    "easiest": 4,
}
DIFFICULTY_LEVELS = ("easy", "normal", "hard")
# Endless waves stop growing once every one has reached the hit point limit; more growth
# levels than this would need a trigger per level and difficulty for little difference.
MAX_ENDLESS_LEVELS = 30
# Raiders cannot reach across a one-tile wall: land raiders fight in melee, naval raiders at
# the fire ships' short range.
RAIDERS: dict[RaiderMedium, frozenset[str]] = {
    "land": frozenset(
        {
            "SCOUT_CAVALRY",
            "LIGHT_CAVALRY",
            "HUSSAR",
            "WINGED_HUSSAR",
            "KNIGHT",
            "CAVALIER",
            "PALADIN",
            "CAMEL_RIDER",
            "HEAVY_CAMEL_RIDER",
        }
    ),
    "naval": frozenset({"FIRE_GALLEY", "FIRE_SHIP", "FAST_FIRE_SHIP"}),
}


@dataclass(frozen=True)
class Resources:
    food: int
    wood: int
    stone: int
    gold: int


@dataclass(frozen=True)
class Economy:
    # Each lane starts with these resources and technologies.
    starting_resources: Resources
    starting_technologies: tuple[str, ...]
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
    def members(self) -> tuple[str, ...]:
        """Every tower definition the families name, once each, in family order."""
        return tuple(dict.fromkeys(member for _, members in self.families for member in members))

    @property
    def definitions(self) -> tuple[int, ...]:
        return tuple(BuildingInfo[member].ID for member in self.members)

    @property
    def special_id(self) -> int:
        return BuildingInfo[self.special].ID


@dataclass(frozen=True)
class DifficultyLevel:
    key: str
    name: str
    king_gold: int
    hit_points_percent: int


@dataclass(frozen=True)
class Difficulty:
    levels: tuple[DifficultyLevel, ...]
    # Each lobby setting's xsGetDifficulty value and the level it plays.
    lobby: tuple[tuple[int, int], ...]
    # The level every competitive game plays, whatever the lobby says.
    competitive: int

    def index(self, key: str) -> int:
        for index, level in enumerate(self.levels):
            if level.key == key:
                return index
        raise ValueError(f"Unknown difficulty level: {key}")

    def level(self, key: str) -> DifficultyLevel:
        return self.levels[self.index(key)]


@dataclass(frozen=True)
class Endless:
    # Positions in the wave schedule that endless waves repeat in turn.
    templates: tuple[int, ...]
    # Hit points grow by this percentage each time the templates repeat.
    growth_percent: int
    # Pierce armor every endless wave adds to the template enemies.
    armor_step: int


@dataclass(frozen=True)
class RaiderKind:
    unit: str
    # The unit and its upgrades: a living cap counts them all, so upgrading frees no slot.
    line: tuple[str, ...]
    cap: int

    @property
    def unit_id(self) -> int:
        return UnitInfo[self.unit].ID

    @property
    def line_ids(self) -> tuple[int, ...]:
        return tuple(UnitInfo[name].ID for name in self.line)


@dataclass(frozen=True)
class Raiders:
    land: RaiderKind
    naval: RaiderKind

    def kind(self, medium: RaiderMedium) -> RaiderKind:
        match medium:
            case "land":
                return self.land
            case "naval":
                return self.naval
            case _:
                raise ValueError(f"Unknown raider medium: {medium}")


@dataclass(frozen=True)
class Siege:
    # Trebuchets created near each surviving rival.
    trebuchets_per_rival: int
    warning_seconds: int
    active_seconds: int
    shared_cooldown: int
    buyer_cooldown: int


@dataclass(frozen=True)
class Interaction:
    raiders: Raiders
    siege: Siege


@dataclass(frozen=True)
class Practice:
    kings: int
    resources: int


@dataclass(frozen=True)
class Balance:
    lives: int
    # Lives a leaking boss costs; any other enemy costs one.
    boss_leak_lives: int
    # The most the game waits for the chooser's run option before preparation begins.
    choice_seconds: int
    preparation_seconds: int
    intermission_seconds: int
    max_enemies_per_lane: int
    sudden_death_interval: int
    sudden_death_damage: int
    economy: Economy
    difficulty: Difficulty
    endless: Endless
    interaction: Interaction
    practice: Practice
    towers: Towers
    waves: tuple[WaveDefinition, ...]

    @property
    def scheduled_seconds(self) -> int:
        return (
            self.choice_seconds
            + self.preparation_seconds
            + sum(w.duration for w in self.waves)
            + self.intermission_seconds * (len(self.waves) - 1)
        )

    def hit_points(self, wave: int, difficulty: int) -> int:
        """A scheduled wave's enemy hit points at a difficulty level: within the engine's
        attribute limit, or a boss's larger current hit points."""
        percent = self.difficulty.levels[difficulty].hit_points_percent
        limit = BOSS_HIT_POINTS if self.waves[wave].boss else MAX_HIT_POINTS
        return min(limit, (self.waves[wave].hit_points * percent + 50) // 100)

    def endless_hit_points(self, level: int, position: int, difficulty: int) -> int:
        """Hit points of an endless template's enemies after `level` rounds of growth."""
        base = self.hit_points(self.endless.templates[position], difficulty)
        growth = 100 + self.endless.growth_percent
        return min(MAX_HIT_POINTS, base * growth**level // 100**level)

    @cached_property
    def endless_levels(self) -> int:
        """Growth levels until every endless enemy has reached the limit at every difficulty."""
        level = 1
        while any(
            self.endless_hit_points(level, position, difficulty) < MAX_HIT_POINTS
            for position in range(len(self.endless.templates))
            for difficulty in range(len(self.difficulty.levels))
        ):
            level += 1
        return level


def tower(name: object) -> str:
    if not isinstance(name, str) or name not in TOWER_BUILDINGS:
        raise ValueError(f"Not a tower: {name}")
    return name


def technologies(raw: dict[str, object], key: str) -> tuple[str, ...]:
    names = raw.get(key)
    if not isinstance(names, list):
        raise ValueError(f"{key} must list technology names")
    listed: list[str] = []
    for name in cast(list[object], names):
        if not isinstance(name, str):
            raise ValueError(f"{key} must list technology names")
        identifier = technology(name)
        if name in RESERVED_TECHNOLOGIES:
            raise ValueError(f"{name} cannot be a starting technology: the game grants or sells it")
        if name in UNRESEARCHABLE or identifier in TECHNOLOGIES or identifier in POINTLESS:
            raise ValueError(f"{name} cannot be a starting technology: the game rules it out")
        if name in listed:
            raise ValueError(f"Technology listed twice: {name}")
        listed.append(name)
    return tuple(listed)


def load_economy(raw: dict[str, object]) -> Economy:
    start = object_value(raw.get("starting_resources"), "starting_resources")
    kills = object_value(raw.get("kill_reward"), "kill_reward")
    bonus = object_value(raw.get("resource_bonus"), "resource_bonus")
    return Economy(
        starting_resources=Resources(
            *(integer(start, name, 0, 30000) for name in ("food", "wood", "stone", "gold"))
        ),
        starting_technologies=technologies(raw, "starting_technologies"),
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


def level_key(value: object, levels: Collection[str]) -> str:
    if not isinstance(value, str) or value not in levels:
        raise ValueError(f"Unknown difficulty level: {value}")
    return value


def load_difficulty(raw: dict[str, object]) -> Difficulty:
    entries = object_value(raw.get("levels"), "levels")
    if set(entries) != set(DIFFICULTY_LEVELS):
        raise ValueError(f"difficulty levels must be {', '.join(DIFFICULTY_LEVELS)}")
    levels: list[DifficultyLevel] = []
    for key in DIFFICULTY_LEVELS:
        row = object_value(entries[key], key)
        levels.append(
            DifficultyLevel(
                key=key,
                name=text_field(row, "name"),
                king_gold=integer(row, "king_gold", 100, 30000),
                hit_points_percent=integer(row, "hit_points_percent", 50, 200),
            )
        )
    lobby = object_value(raw.get("lobby"), "lobby")
    if set(lobby) != set(LOBBY_DIFFICULTIES):
        raise ValueError(f"lobby must map {', '.join(LOBBY_DIFFICULTIES)}")
    return Difficulty(
        levels=tuple(levels),
        lobby=tuple(
            (value, DIFFICULTY_LEVELS.index(level_key(lobby[name], DIFFICULTY_LEVELS)))
            for name, value in LOBBY_DIFFICULTIES.items()
        ),
        competitive=DIFFICULTY_LEVELS.index(level_key(raw.get("competitive"), DIFFICULTY_LEVELS)),
    )


def load_endless(raw: dict[str, object], waves: tuple[WaveDefinition, ...]) -> Endless:
    names = raw.get("templates")
    if not isinstance(names, list) or not names:
        raise ValueError("endless templates must list wave keys")
    keys = [wave.key for wave in waves]
    templates: list[int] = []
    for name in cast(list[object], names):
        if not isinstance(name, str) or name not in keys:
            raise ValueError(f"Unknown endless template: {name}")
        if keys.index(name) in templates:
            raise ValueError(f"Endless template listed twice: {name}")
        # Endless enemies stay within the attribute's limit, which a boss's hit points exceed.
        if waves[keys.index(name)].boss:
            raise ValueError(f"A boss cannot be an endless template: {name}")
        # Each template's enemies get their own hit points, so no two may share a unit.
        if waves[keys.index(name)].unit in {waves[t].unit for t in templates}:
            raise ValueError(f"Endless templates share a unit: {name}")
        templates.append(keys.index(name))
    return Endless(
        templates=tuple(templates),
        growth_percent=integer(raw, "hit_point_growth_percent", 10, 200),
        armor_step=integer(raw, "armor_step", 0, 1000),
    )


def raider_kind(raw: dict[str, object], medium: RaiderMedium) -> RaiderKind:
    row = object_value(raw.get(medium), medium)
    allowed = RAIDERS[medium]
    unit = row.get("unit")
    if not isinstance(unit, str) or unit not in allowed:
        raise ValueError(f"Not a {medium} raider: {unit}")
    names = row.get("line")
    if not isinstance(names, list) or not names or cast(list[object], names)[0] != unit:
        raise ValueError(f"The {medium} raider line must start with {unit}")
    line: list[str] = []
    for name in cast(list[object], names):
        if not isinstance(name, str) or name not in allowed or name in line:
            raise ValueError(f"Not a {medium} raider: {name}")
        line.append(name)
    return RaiderKind(unit=unit, line=tuple(line), cap=integer(row, "cap", 1, 10))


def load_raiders(raw: dict[str, object]) -> Raiders:
    if "bonuses" in raw:
        raise ValueError("Raider bonuses belong to content/balance/civilizations.json")
    return Raiders(land=raider_kind(raw, "land"), naval=raider_kind(raw, "naval"))


def load_siege(raw: dict[str, object]) -> Siege:
    shared = integer(raw, "shared_cooldown", 0, 600)
    return Siege(
        # Each rival has three siege positions; the third stays in reserve.
        trebuchets_per_rival=integer(raw, "trebuchets_per_rival", 1, 3),
        warning_seconds=integer(raw, "warning_seconds", 1, 60),
        active_seconds=integer(raw, "active_seconds", 10, 300),
        shared_cooldown=shared,
        # The buyer waits at least as long as everyone else.
        buyer_cooldown=integer(raw, "buyer_cooldown", shared, 1200),
    )


def load_balance(path: Path) -> Balance:
    raw = read_object(path)
    if raw.get("schema_version") != 6:
        raise ValueError("Unsupported balance schema")
    waves: list[WaveDefinition] = []
    for row in rows(raw.get("waves"), "waves"):
        key, unit = text_field(row, "key"), text_field(row, "unit")
        wave_unit(unit)
        boss = row.get("boss")
        if type(boss) is not bool:
            raise ValueError("boss must be a boolean")
        wave = WaveDefinition(
            key=key,
            unit=unit,
            boss=boss,
            count=integer(row, "count", 1, MAX_BATCH),
            batches=integer(row, "batches", 1, 80),
            interval=integer(row, "interval", 2, 120),
            duration=integer(row, "duration", 1, 600),
            hit_points=integer(row, "hit_points", 1, BOSS_HIT_POINTS if boss else MAX_HIT_POINTS),
            pierce_armor=integer(row, "pierce_armor", 0, 500) if "pierce_armor" in row else None,
        )
        if (wave.batches - 1) * wave.interval >= wave.duration:
            raise ValueError(f"Wave duration cannot contain all batches: {key}")
        # A boss comes alone: its hit points are a reservoir the engine keeps for one unit.
        if boss and (wave.count != 1 or wave.batches != 1):
            raise ValueError(f"A boss wave spawns one enemy: {key}")
        if key in {w.key for w in waves}:
            raise ValueError(f"Duplicate wave key: {key}")
        waves.append(wave)
    if not waves or len(waves) > MAX_WAVES or not waves[-1].boss:
        raise ValueError(f"waves must contain 1–{MAX_WAVES} entries ending in a boss")
    # A leak costs lives by the enemy's type, so a boss's unit is a boss's alone.
    regular_units = {w.unit for w in waves if not w.boss}
    for wave in waves:
        if wave.boss and wave.unit in regular_units:
            raise ValueError(f"A boss unit cannot also be a regular wave's: {wave.unit}")
    interaction = object_value(raw.get("interaction"), "interaction")
    practice = object_value(raw.get("practice"), "practice")
    balance = Balance(
        lives=integer(raw, "lives", 1, 100),
        boss_leak_lives=integer(raw, "boss_leak_lives", 1, 100),
        choice_seconds=integer(raw, "choice_seconds", 10, 300),
        preparation_seconds=integer(raw, "preparation_seconds", 1, 600),
        intermission_seconds=integer(raw, "intermission_seconds", 1, 120),
        max_enemies_per_lane=integer(raw, "max_enemies_per_lane", 5, 100),
        sudden_death_interval=integer(raw, "sudden_death_interval", 1, 60),
        sudden_death_damage=integer(raw, "sudden_death_damage", 1, 10),
        economy=load_economy(object_value(raw.get("economy"), "economy")),
        difficulty=load_difficulty(object_value(raw.get("difficulty"), "difficulty")),
        endless=load_endless(object_value(raw.get("endless"), "endless"), tuple(waves)),
        interaction=Interaction(
            raiders=load_raiders(object_value(interaction.get("raiders"), "raiders")),
            siege=load_siege(object_value(interaction.get("siege"), "siege")),
        ),
        practice=Practice(
            kings=integer(practice, "kings", 1, 50),
            resources=integer(practice, "resources", 1, 30000),
        ),
        towers=load_towers(object_value(raw.get("towers"), "towers")),
        waves=tuple(waves),
    )
    if balance.endless_levels > MAX_ENDLESS_LEVELS:
        raise ValueError("hit_point_growth_percent is too small for the endless wave levels")
    return balance


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

    def traders(self, medium: TradeMedium) -> tuple[str, tuple[Tile, ...], int]:
        """The trader kind, its spots and its partner's placement for a trade medium."""
        if medium == "land":
            return "cart", self.sites.carts, self.land_trade_partner
        return "cog", self.sites.cogs, self.water_trade_partner


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
        if not (y1 + PATH_ROWS // 2 <= sy <= y2 - PATH_ROWS // 2):
            raise ValueError(f"Lane path must hold {PATH_ROWS} rows around its center: {prefix}")
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
