"""Reviewed object mappings shared by the audit, the map and the registry."""

from typing import Literal, NotRequired, TypedDict

# An inclusive tile rectangle: (x1, y1, x2, y2).
type Rect = tuple[int, int, int, int]


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
