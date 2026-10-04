"""Resolve named references and civilization-dependent legacy mappings centrally."""

from ancienttdde.models import ObjectMapping


class ReferenceRegistry:
    def __init__(self, mappings: list[ObjectMapping]) -> None:
        self._objects: dict[str, ObjectMapping] = {}
        self._legacy: dict[tuple[int, int], ObjectMapping] = {}
        self._references: dict[tuple[str, str], int] = {}
        for row in mappings:
            key = row["key"]
            if key in self._objects:
                raise ValueError(f"Duplicate object key: {key}")
            if row["disposition"] not in {"keep", "replace", "drop"}:
                raise ValueError(f"Invalid disposition for {key}")
            if row["status"] not in {"candidate", "reviewed", "verified"}:
                raise ValueError(f"Invalid verification status for {key}")
            if row["stock_id"] is not None and (
                type(row["stock_id"]) is not int or row["stock_id"] < 0
            ):
                raise ValueError(f"Invalid stock ID for {key}")
            if not row["civilization_ids"]:
                raise ValueError(f"Missing civilization context for {key}")
            self._objects[key] = row
            for civ in row["civilization_ids"]:
                reference = (row["legacy_id"], civ)
                if reference in self._legacy:
                    raise ValueError(f"Duplicate legacy reference: {reference}")
                self._legacy[reference] = row

    def legacy(self, object_id: int, civilization_id: int) -> ObjectMapping:
        return self._legacy[object_id, civilization_id]

    def stock(self, key: str) -> int:
        row = self._objects[key]
        identifier = row["stock_id"]
        if row["status"] != "verified" or identifier is None:
            raise ValueError(f"Stock mapping must be verified before generation: {key}")
        return identifier

    def map_stock(self, key: str) -> int:
        """Resolve a reviewed map identity without approving gameplay behavior."""
        from importlib.metadata import version

        from AoE2ScenarioParser.datasets.buildings import (
            BuildingInfo,
        )
        from AoE2ScenarioParser.datasets.heroes import (
            HeroInfo,
        )
        from AoE2ScenarioParser.datasets.other import (
            OtherInfo,
        )
        from AoE2ScenarioParser.datasets.support.info_dataset_base import InfoDatasetBase
        from AoE2ScenarioParser.datasets.units import (
            UnitInfo,
        )

        row = self._objects[key]
        identifier = row["stock_id"]
        if row["status"] not in {"reviewed", "verified"} or identifier is None:
            raise ValueError(f"Map mapping must be reviewed before generation: {key}")
        identity = row.get("map_identity")
        datasets: dict[str, type[InfoDatasetBase]] = {
            "BuildingInfo": BuildingInfo,
            "OtherInfo": OtherInfo,
            "UnitInfo": UnitInfo,
            "HeroInfo": HeroInfo,
        }
        if identity is None or identity["parser_version"] != version("AoE2ScenarioParser"):
            raise ValueError(f"Map identity parser version mismatch: {key}")
        try:
            member = datasets[identity["dataset"]].from_id(identifier)
        except (KeyError, ValueError) as error:
            raise ValueError(f"Invalid stock map identity: {key}") from error
        if member.name != identity["name"]:
            raise ValueError(f"Invalid stock map identity: {key}")
        return identifier

    def register(self, kind: str, key: str, identifier: int) -> None:
        if kind not in {"trigger", "variable", "object"}:
            raise ValueError(f"Unknown reference kind: {kind}")
        if type(identifier) is not int or identifier < 0:
            raise ValueError(f"Invalid reference ID: {identifier}")
        reference = (kind, key)
        if reference in self._references:
            raise ValueError(f"Duplicate named reference: {reference}")
        self._references[reference] = identifier

    def resolve(self, kind: str, key: str) -> int:
        return self._references[kind, key]
