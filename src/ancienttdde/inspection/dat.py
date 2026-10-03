"""Inspect the complete C++ genieutils export without loading incompatible DATs."""

import json
from pathlib import Path

from ancienttdde.provenance import project_path


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Invalid JSON reference {path}; regenerate it from the original DAT"
        ) from error


def graphic_ids(value, key="") -> set[int]:
    """Collect graphic references including moving, combat, building and deltas."""
    if isinstance(value, dict):
        result = set()
        for name, child in value.items():
            result.update(graphic_ids(child, name if "graphic" in name.lower() else key))
        return result
    if isinstance(value, list):
        return set().union(*(graphic_ids(child, key) for child in value))
    if type(value) is int and value >= 0 and "graphic" in key.lower():
        # Coordinates/displacements are not IDs.
        if not any(word in key.lower() for word in ("displacement", "angle", "damagegraphics")):
            return {value}
    return set()


LINKED_UNITS = {
    "DeadUnitID",
    "BloodUnitID",
    "ProjectileUnitID",
    "SecondaryProjectileUnit",
    "StackUnitID",
    "HeadUnit",
    "TransformUnit",
    "PileUnit",
    "UnitID",
}


def linked_units(value) -> set[int]:
    if isinstance(value, dict):
        result = {v for k, v in value.items() if k in LINKED_UNITS and type(v) is int and v >= 0}
        for child in value.values():
            result.update(linked_units(child))
        return result
    if isinstance(value, list):
        return set().union(*(linked_units(child) for child in value))
    return set()


def inspect_dat(
    directory: Path, object_ids: set[int], technology_ids: set[int], graphics_directory: Path
) -> dict:
    manifest = read_json(directory / "manifest.json")
    index = read_json(directory / "civilizations.json")
    graphics = read_json(directory / "graphics.json")
    technologies = read_json(directory / "technologies.json")
    effects = read_json(directory / "effects.json")
    assets = {p.stem.casefold(): p.name for p in graphics_directory.glob("*.smx")}
    by_graphic = {i: value for i, value in enumerate(graphics)}
    custom = {
        i: assets[g["FileName"].casefold()]
        for i, g in by_graphic.items()
        if g.get("FileName", "").casefold() in assets
    }

    def expand_graphics(seeds):
        seen = set()
        pending = list(seeds)
        while pending:
            identifier = pending.pop()
            if identifier in seen or identifier not in by_graphic:
                continue
            seen.add(identifier)
            pending.extend(
                d["GraphicID"]
                for d in by_graphic[identifier].get("Deltas", [])
                if d.get("GraphicID", -1) >= 0
            )
        return seen

    objects = {i: {"id": i, "civilizations": {}} for i in sorted(object_ids)}
    civs = []
    all_techs = set(technology_ids)
    for entry in index:
        civ = read_json(project_path(directory, entry["file"]))
        cid = entry["index"]
        tree, team = civ["TechTreeID"], civ["TeamBonusID"]
        civs.append(
            {
                "id": cid,
                "name": entry["name"],
                "source": entry["file"],
                "tech_tree_id": tree,
                "team_bonus_id": team,
                "resources": civ["Resources"],
                "unit_count": len(civ["Units"]),
                "civilization_technology_ids": [
                    i for i, t in enumerate(technologies) if t.get("Civ") == cid
                ],
            }
        )
        for i in object_ids:
            if i >= len(civ["Units"]):
                raise ValueError(f"Object {i} is missing from civilization {cid}")
            unit = civ["Units"][i]
            pending = list(linked_units(unit))
            linked = set()
            seeds = graphic_ids(unit)
            while pending:
                uid = pending.pop()
                if uid in linked or uid == i:
                    continue
                if uid >= len(civ["Units"]):
                    raise ValueError(f"Linked object {uid} is missing from civilization {cid}")
                linked.add(uid)
                child = civ["Units"][uid]
                seeds.update(graphic_ids(child))
                pending.extend(linked_units(child) - linked)
            gids = expand_graphics(seeds)
            objects[i]["civilizations"][str(cid)] = {
                "definition": unit,
                "graphic_ids": sorted(gids),
                "custom_graphics": sorted(gids & custom.keys()),
                "linked_object_ids": sorted(linked),
            }
        all_techs.update(i for i, t in enumerate(technologies) if t.get("Civ") == cid)
    if any(i >= len(technologies) for i in all_techs):
        raise ValueError("Scenario references a missing DAT technology")
    effect_ids = {technologies[i]["EffectID"] for i in all_techs}
    # Civilization TechTreeID and TeamBonusID refer directly to effects, not techs.
    effect_ids.update(c[field] for c in civs for field in ("tech_tree_id", "team_bonus_id"))
    effect_ids.discard(-1)
    if any(i < 0 or i >= len(effects) for i in effect_ids):
        raise ValueError("Civilization references a missing DAT effect")
    return {
        "format": manifest.get("format"),
        "file_version": manifest["source_file_version"],
        "game_version": manifest["game_version"],
        "civilizations": civs,
        "objects": list(objects.values()),
        "technologies": [{"id": i, "definition": value} for i, value in enumerate(technologies)],
        "effects": [{"id": i, "definition": value} for i, value in enumerate(effects)],
        "custom_graphics": [
            {"id": i, "asset": custom[i], "definition": by_graphic[i]} for i in sorted(custom)
        ],
        "comparison_note": "Civilization variants are observations, not a diff against stock DE.",
    }
