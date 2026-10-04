"""Typed plain-data contracts between inspection, migration, and construction."""

from typing import Literal, NotRequired, TypedDict

from ancienttdde.models import ObjectMapping


class HashRecord(TypedDict):
    path: str
    sha256: str


class TerrainData(TypedDict):
    width: int
    height: int
    tiles: list[list[int]]


class MapUnit(TypedDict):
    player_id: int
    reference_id: int
    unit_const: int
    x: float
    y: float
    z: float
    rotation: float
    status: int
    initial_animation_frame: int
    garrisoned_in_id: int
    caption_string: NotRequired[str]
    caption_string_id: NotRequired[int]
    capture_flag: NotRequired[int]
    object_key: NotRequired[str]


class LegacyPlayer(TypedDict):
    player_id: int
    civilization_id: int


class MapAnchor(TypedDict):
    point: NotRequired[list[float]]
    region: NotRequired[list[int]]
    reference_id: NotRequired[int]
    label: NotRequired[str]


class PlacementOverride(TypedDict):
    reference_id: int
    owner: NotRequired[int]
    caption: NotRequired[str]


class TerrainPatch(TypedDict):
    key: str
    region: list[int]
    terrain_id: int
    allowed_source_terrain: list[int]


class Route(TypedDict):
    key: str
    start: str
    end: str
    medium: Literal["land", "water"]
    region: list[int]


class Isolation(TypedDict):
    key: str
    start: str
    medium: Literal["land", "water"]
    region: list[int]


class FoundationConfig(TypedDict):
    schema_version: int
    objects: list[ObjectMapping]
    anchors: dict[str, MapAnchor]
    placement_overrides: list[PlacementOverride]
    terrain_patches: list[TerrainPatch]
    routes: list[Route]
    isolation: list[Isolation]
    land_terrain: list[int]
    water_terrain: list[int]


class MigrationSummary(TypedDict):
    placements: dict[str, int]
    terrain_patch_tiles: int


class MapDocument(TypedDict):
    schema_version: int
    scenario_version: str
    source: HashRecord
    map: TerrainData
    players: list[LegacyPlayer]
    units: list[MapUnit]
    anchors: NotRequired[dict[str, MapAnchor]]
    migration: NotRequired[MigrationSummary]


class RouteResult(TypedDict):
    key: str
    reachable: bool
    reachable_tiles: int


class IsolationResult(TypedDict):
    key: str
    contained: bool
    reachable_tiles: int


class MapValidation(TypedDict):
    routes: list[RouteResult]
    isolation: list[IsolationResult]
    in_game_verified: bool


class BuildManifest(TypedDict):
    schema_version: int
    kind: Literal["stock-de-map"]
    inputs: list[HashRecord]
    artifacts: list[HashRecord]
    normalized_sha256: str
    source: HashRecord
    validation: MapValidation


class PlayerSnapshot(TypedDict):
    player_id: int
    civilization: str
    active: bool
    human: bool
    disabled_units: list[int] | None
    disabled_buildings: list[int] | None
    disabled_techs: list[int] | None


class DependencySnapshot(TypedDict):
    external_xs: str
    embedded_xs: str
    ai_files: int
    cinematics: list[str]
    background_image: str


class ScenarioSnapshot(TypedDict):
    scenario_version: str
    next_unit_id: int
    victory_condition: int
    map: TerrainData
    units: list[MapUnit]
    players: list[PlayerSnapshot]
    triggers: list[object]
    variables: list[object]
    dependencies: DependencySnapshot
