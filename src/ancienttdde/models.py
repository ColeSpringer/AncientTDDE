"""Shared inspection and generation vocabulary; legacy values are observations."""

from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict


class MapIdentity(TypedDict):
    dataset: Literal["BuildingInfo", "OtherInfo", "UnitInfo", "HeroInfo"]
    name: str
    parser_version: str


class ObjectMapping(TypedDict):
    key: str
    legacy_id: int
    civilization_ids: list[int]
    disposition: Literal["keep", "replace", "drop"]
    stock_id: int | None
    status: Literal["candidate", "reviewed", "verified"]
    map_identity: NotRequired[MapIdentity]
    blocking_size: NotRequired[int]


@dataclass(frozen=True)
class Region:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class Lane:
    player_id: int
    center_y: int
    spawn_x: int
    exit_x: int
    life_reference_id: int
    life_variable_id: int


@dataclass(frozen=True)
class Wave:
    key: str
    kind: str
    trigger_id: int
    start_trigger_id: int | None
    stop_trigger_id: int | None
    start_seconds: int | None
    first_spawn_seconds: int | None
    duration_seconds: int | None
    interval_seconds: int | None
    spawns: tuple[dict[str, Any], ...]
    modifications: tuple[dict[str, Any], ...]
    activated_trigger_ids: tuple[int, ...]


@dataclass(frozen=True)
class Purchase:
    trigger_id: int
    name: str
    player_id: int
    required_kings: int
    initially_enabled: bool
    repeatable: bool
    condition_object_group: int | None
    condition_region: Region | None
    removal_regions: tuple[Region | None, ...]
    payment_policy: str
    conditions: tuple[dict[str, Any], ...]
    effects: tuple[dict[str, Any], ...]
    linked_triggers: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CivilizationProfile:
    civilization_id: int
    name: str
    tech_tree_id: int
    team_bonus_id: int
    resources: tuple[float, ...]
    scenario_trigger_ids: tuple[int, ...]


@dataclass(frozen=True)
class GameSettings:
    """Agreed future defaults, kept separate from extracted legacy behavior."""

    mode: str = "standard"
    pvp_enabled: bool = True
    human_slots: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)
    enemy_slot: int = 8
    language: str = "en"
