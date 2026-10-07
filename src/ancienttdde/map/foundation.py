"""Translate legacy map data without sharing parser objects across versions."""

import copy
import math
from collections import Counter

from AoE2ScenarioParser.datasets.terrains import TerrainId

from ancienttdde.map.geometry import bounds, cells, check_connectivity
from ancienttdde.map.models import FoundationConfig, MapDocument, MapValidation
from ancienttdde.registry import NameTable, ObjectMappings


def validate_structure(data: MapDocument, config: FoundationConfig) -> None:
    if data["schema_version"] != 1 or config["schema_version"] != 1:
        raise ValueError("Unsupported map schema")
    map_data = data["map"]
    width, height = map_data["width"], map_data["height"]
    if type(width) is not int or type(height) is not int or width != height or width <= 0:
        raise ValueError("The foundation must be a nonempty square map")
    if len(map_data["tiles"]) != width * height:
        raise ValueError("Terrain tile count does not match map dimensions")
    terrain_ids = {int(terrain) for terrain in TerrainId}
    if not set(config["land_terrain"] + config["water_terrain"]).issubset(terrain_ids):
        raise ValueError("Unknown stock terrain in passability definitions")
    for tile in map_data["tiles"]:
        if len(tile) != 3 or any(type(v) is not int for v in tile):
            raise ValueError(f"Invalid terrain/elevation/layer record: {tile}")
        if not (tile[0] in terrain_ids and 0 <= tile[1] <= 7 and tile[2] >= -1):
            raise ValueError(f"Invalid terrain/elevation/layer record: {tile}")
    identifiers = [u["reference_id"] for u in data["units"]]
    if any(type(i) is not int or i < 0 for i in identifiers) or len(set(identifiers)) != len(
        identifiers
    ):
        raise ValueError("Placed instances need unique nonnegative reference IDs")
    units = {u["reference_id"]: u for u in data["units"]}
    for unit in units.values():
        if type(unit["player_id"]) is not int or not 0 <= unit["player_id"] <= 8:
            raise ValueError("Invalid placement owner")
        if not (
            math.isfinite(unit["x"])
            and math.isfinite(unit["y"])
            and 0 <= unit["x"] < width
            and 0 <= unit["y"] < height
        ):
            raise ValueError(f"Placement outside map: {unit['reference_id']}")
        if unit["garrisoned_in_id"] >= 0 and unit["garrisoned_in_id"] not in units:
            raise ValueError(f"Dangling garrison reference: {unit['reference_id']}")
    for key, anchor in config["anchors"].items():
        positions = ([anchor["point"]] if "point" in anchor else []) + anchor.get("points", [])
        if not key or not (positions or "region" in anchor):
            raise ValueError(f"Anchor needs a point or region: {key}")
        for point in positions:
            if len(point) != 2 or not (0 <= point[0] < width and 0 <= point[1] < height):
                raise ValueError(f"Anchor outside map: {key}")
        if "region" in anchor:
            bounds(anchor["region"], width, height)
        if "reference_id" in anchor:
            unit = units.get(anchor["reference_id"])
            if unit is None:
                raise ValueError(f"Missing anchor instance: {key}")
            if anchor.get("point") != [unit["x"], unit["y"]]:
                raise ValueError(f"Anchor does not match its instance: {key}")
    for row in config["objects"]:
        size = row.get("blocking_size", 0)
        if type(size) is not int or not 0 <= size <= 4:
            raise ValueError(f"Invalid conservative footprint: {row['key']}")


def migrate_map(legacy: MapDocument, config: FoundationConfig) -> MapDocument:
    """Preserve placement IDs and geometry, then apply explicit reviewed map decisions."""
    validate_structure(legacy, config)
    mappings = ObjectMappings(config["objects"])
    identities = {row["key"]: mappings.map_stock(row["key"]) for row in config["objects"]}
    civilizations = {p["player_id"]: p["civilization_id"] for p in legacy["players"]}
    result = copy.deepcopy(legacy)
    result["anchors"] = copy.deepcopy(config["anchors"])
    overrides = {r["reference_id"]: r for r in config["placement_overrides"]}
    if len(overrides) != len(config["placement_overrides"]):
        raise ValueError("Duplicate placement override")
    if not overrides.keys() <= {u["reference_id"] for u in result["units"]}:
        raise ValueError("Missing placement override instance")
    replacements: Counter[str] = Counter()
    for unit in result["units"]:
        civilization = civilizations.get(unit["player_id"])
        row = (
            None if civilization is None else mappings.find_legacy(unit["unit_const"], civilization)
        )
        if row is None:
            raise ValueError(f"Unmapped placement: {unit['reference_id']}")
        key = row["key"]
        unit["unit_const"] = identities[key]
        unit["object_key"] = key
        override = overrides.get(unit["reference_id"])
        if override is not None:
            if "owner" in override:
                unit["player_id"] = override["owner"]
            if "caption" in override:
                unit["caption_string"] = override["caption"]
        replacements[key] += 1
    names = NameTable()
    for key, anchor in result["anchors"].items():
        if "reference_id" in anchor:
            names.register("object", key, anchor["reference_id"])
    tile_changes = 0
    patched: set[tuple[int, int]] = set()
    width, height = result["map"]["width"], result["map"]["height"]
    for patch in config["terrain_patches"]:
        region = bounds(patch["region"], width, height)
        for x, y in sorted(cells(region)):
            if (x, y) in patched:
                raise ValueError(f"Overlapping terrain patch: {patch['key']}")
            patched.add((x, y))
            tile = result["map"]["tiles"][y * width + x]
            if tile[0] not in patch["allowed_source_terrain"]:
                raise ValueError(f"Terrain patch would replace important geometry: {patch['key']}")
            tile[0] = patch["terrain_id"]
            tile_changes += 1
    result["migration"] = {
        "placements": dict(sorted(replacements.items())),
        "terrain_patch_tiles": tile_changes,
    }
    validate_structure(result, config)
    return result


def validate_map(data: MapDocument, config: FoundationConfig) -> MapValidation:
    validate_structure(data, config)
    mappings = ObjectMappings(config["objects"])
    stock = {mappings.map_stock(row["key"]) for row in config["objects"]}
    if any(u["unit_const"] not in stock for u in data["units"]):
        raise ValueError("Map contains an unreviewed stock object")
    if data.get("anchors") != config["anchors"]:
        raise ValueError("Map anchors differ from the current configuration")
    return check_connectivity(data, config)
