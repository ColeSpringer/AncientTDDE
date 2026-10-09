"""Typed plain-data contracts between inspection, migration, and construction."""

from typing import Literal, NotRequired, TypedDict

from ancienttdde.common.data import HashRecord
from ancienttdde.common.manifest import ManifestBase
from ancienttdde.models import ObjectMapping
from ancienttdde.scenario.snapshot import MapUnit, TerrainData


class LegacyPlayer(TypedDict):
    player_id: int
    civilization_id: int


class MapAnchor(TypedDict):
    point: NotRequired[list[float]]
    # Ordered positions that belong together, such as a spawn and its walk target.
    points: NotRequired[list[list[float]]]
    region: NotRequired[list[int]]
    reference_id: NotRequired[int]
    label: NotRequired[str]


class PlacementOverride(TypedDict):
    reference_id: int
    owner: NotRequired[int]
    caption: NotRequired[str]


class PlacementAddition(TypedDict):
    """An object the migration places that the original map lacks."""

    key: str
    object_key: str
    player_id: int
    x: float
    y: float


class PlacementRemoval(TypedDict):
    reference_id: int


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
    placement_additions: NotRequired[list[PlacementAddition]]
    placement_removals: NotRequired[list[PlacementRemoval]]
    terrain_patches: list[TerrainPatch]
    routes: list[Route]
    isolation: list[Isolation]
    land_terrain: list[int]
    water_terrain: list[int]


class MigrationSummary(TypedDict):
    placements: dict[str, int]
    placement_additions: int
    placement_removals: int
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


class BuildManifest(ManifestBase):
    kind: Literal["stock-de-map"]
    normalized_sha256: str
    source: HashRecord
    validation: MapValidation
