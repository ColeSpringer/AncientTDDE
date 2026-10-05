"""Typed probe definitions, build evidence, and attributed in-game observations."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Literal, TypedDict

from ancienttdde.generation.models import HashRecord, ScenarioSnapshot
from ancienttdde.inspection.scenario import (
    GlobalVictorySnapshot,
    JSONValue,
    ScenarioOptionsSnapshot,
)


class ProbeId(StrEnum):
    PAYMENTS = "payments"
    TOWERS = "towers"
    TRADE = "trade"
    TRADE_GAIA = "trade-gaia"
    RAIDERS = "raiders"
    SIEGE = "siege"
    SCRIPTS_ENEMY = "scripts-enemy"


class Outcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class AiMode(IntEnum):
    CUSTOM = 0


@dataclass(frozen=True)
class ProbeCase:
    id: str
    action: str
    expected: str


@dataclass(frozen=True)
class ProbeDefinition:
    id: ProbeId
    title: str
    setup: str
    cases: tuple[ProbeCase, ...]


class ProbeRecord(TypedDict):
    id: str
    scenario: str
    snapshot: str
    normalized_sha256: str
    case_ids: list[str]


class ProbeManifest(TypedDict):
    schema_version: int
    kind: Literal["mechanics-probes"]
    inputs: list[HashRecord]
    artifacts: list[HashRecord]
    probes: list[ProbeRecord]
    xs_checked: bool
    in_game_verified: Literal[False]


class ProbeRun(TypedDict):
    status: Literal["pass", "fail", "blocked"]
    game_build: str
    tester: str
    notes: str
    recorded_at: str
    scenario_sha256: str


class CaseResults(TypedDict):
    id: str
    runs: list[ProbeRun]


class ProbeResults(TypedDict):
    schema_version: int
    cases: list[CaseResults]


class AiSnapshot(TypedDict):
    player_id: int
    name: str
    script: str
    type: int


class ProbeSnapshot(ScenarioSnapshot):
    embedded_ai: list[AiSnapshot]
    messages: dict[str, JSONValue]
    options: ScenarioOptionsSnapshot
    global_victory: GlobalVictorySnapshot


type FieldValue = int | float | str | bool | list[int]
