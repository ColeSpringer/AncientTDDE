"""Waves and purchases observed in the original scenario's trigger data."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Region:
    x1: int
    y1: int
    x2: int
    y2: int


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
    linked_triggers: tuple[Mapping[str, Any], ...]
