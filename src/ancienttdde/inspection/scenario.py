"""Isolate parser state: each input is parsed in its own Python process."""

import contextlib
import json
import os
import subprocess
import sys
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, cast

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


def inspect_scenario(path: Path) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, "-m", "ancienttdde.inspection.scenario", str(path.resolve())],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if process.returncode:
        raise ValueError(f"Scenario inspection failed for {path}: {process.stderr.strip()}")
    return json.loads(process.stdout)


def scalar(value: object) -> JSONValue:
    if isinstance(value, Enum):
        return value.value if isinstance(value.value, int) else value.name
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [scalar(v) for v in cast(list[object] | tuple[object, ...], value)]
    if isinstance(value, dict):
        return {str(k): scalar(v) for k, v in cast(dict[object, object], value).items()}
    raise TypeError(f"Unexpected parser value: {type(value).__name__}")


def component(obj: Any, dataset: Any, kind: str) -> dict[str, Any]:
    identifier = getattr(obj, kind)
    enum = dataset.EffectId if kind == "effect_type" else dataset.ConditionId
    try:
        name = enum(identifier).name.lower()
    except ValueError:
        name = f"unknown_{identifier}"
    fields: list[str] | None = dataset.attributes.get(identifier)
    values = vars(cast(object, obj))
    if fields is None:
        fields = [key for key in values if not key.startswith("_")]
    attributes = {key: scalar(getattr(obj, key, None)) for key in fields if key != kind}
    raw = {
        key: scalar(value)
        for key, value in values.items()
        if key not in {"_uuid", "_instance_number_history"}
    }
    if kind == "effect_type":
        raw["_quantity_int"] = scalar(obj._quantity_int)
    return {"type": name, "type_id": int(identifier), "attributes": attributes, "raw": raw}


def references(
    triggers: list[dict[str, Any]], units: list[dict[str, Any]], players: list[dict[str, Any]]
) -> dict[str, Any]:
    occurrences: list[dict[str, Any]] = []

    def add(kind: str, identifier: object, path: str, owner: int | None = None) -> None:
        if type(identifier) is int and identifier >= 0:
            occurrences.append({"kind": kind, "id": identifier, "path": path, "player_id": owner})

    for unit in units:
        path = f"units[{unit['reference_id']}]"
        add("object", unit["unit_const"], path, unit["player_id"])
        add("instance", unit["garrisoned_in_id"], path + ".garrisoned_in_id")
    for player in players:
        for field in ("disabled_units", "disabled_buildings", "disabled_techs"):
            kind = "technology" if field == "disabled_techs" else "object"
            player_ids: list[int] = player.get(field) or []
            for identifier in player_ids:
                add(
                    kind, identifier, f"players[{player['player_id']}].{field}", player["player_id"]
                )
    for trigger in triggers:
        for collection in ("conditions", "effects"):
            for index, entry in enumerate(trigger[collection]):
                attrs = entry["attributes"]
                path = f"triggers[{trigger['id']}].{collection}[{index}]"
                owner = attrs.get("source_player")
                for field in ("object_list", "object_list_unit_id", "object_list_unit_id_2"):
                    add("object", attrs.get(field), path + "." + field, owner)
                for field in (
                    "unit_object",
                    "next_object",
                    "location_object_reference",
                    "legacy_location_object_reference",
                ):
                    add("instance", attrs.get(field), path + "." + field)
                selected_ids: list[int] = attrs.get("selected_object_ids") or []
                for identifier in selected_ids:
                    add("instance", identifier, path + ".selected_object_ids")
                add("technology", attrs.get("technology"), path + ".technology", owner)
                add("trigger", attrs.get("trigger_id"), path + ".trigger_id")
                for field in ("variable", "variable2"):
                    add("variable", attrs.get(field), path + "." + field)
    result: dict[str, Any] = {
        f"{kind}_ids": sorted({o["id"] for o in occurrences if o["kind"] == kind})
        for kind in ("object", "instance", "technology", "trigger", "variable")
    }
    result["occurrences"] = occurrences
    return result


def load_scenario(path: Path) -> dict[str, Any]:
    # The pinned parser exposes no py.typed marker or type stubs.
    from AoE2ScenarioParser.datasets import (  # pyright: ignore[reportMissingTypeStubs]
        conditions,
        effects,
    )
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import (  # pyright: ignore[reportMissingTypeStubs]
        AoE2DEScenario,
    )

    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        scenario = AoE2DEScenario.from_file(str(path))
        triggers: list[dict[str, Any]] = []
        for trigger in scenario.trigger_manager.triggers:
            fields = (
                "name",
                "description",
                "short_description",
                "enabled",
                "looping",
                "display_as_objective",
                "display_on_screen",
                "description_order",
                "header",
                "mute_objectives",
            )
            triggers.append(
                {
                    "id": trigger.trigger_id,
                    **{f: scalar(getattr(trigger, f)) for f in fields},
                    "condition_order": list(trigger.condition_order),
                    "effect_order": list(trigger.effect_order),
                    "conditions": [
                        component(c, conditions, "condition_type") for c in trigger.conditions
                    ],
                    "effects": [component(e, effects, "effect_type") for e in trigger.effects],
                }
            )
        players: list[dict[str, Any]] = []
        for player in scenario.player_manager.players:
            # Raw inspection uses the parser's internal Gaia/non-Gaia field inventory.
            fields = player._object_attributes + player._object_attributes_non_gaia  # pyright: ignore[reportPrivateUsage]
            players.append({f: scalar(getattr(player, f, None)) for f in fields})
        units = [
            {
                "player_id": owner,
                **{k: scalar(v) for k, v in vars(unit).items() if not k.startswith("_")},
            }
            for owner, row in enumerate(scenario.unit_manager.units)
            for unit in row
        ]
        variables = [
            {"variable_id": v.variable_id, "name": v.name}
            for v in scenario.trigger_manager.variables
        ]
        messages = {
            k: scalar(v) for k, v in vars(scenario.message_manager).items() if not k.startswith("_")
        }
        terrain = Counter(tile.terrain_id for tile in scenario.map_manager.terrain)
        xs_manager: Any = scenario.xs_manager
        return {
            "scenario_version": scenario.scenario_version,
            "map": {
                "width": scenario.map_manager.map_width,
                "height": scenario.map_manager.map_height,
                "terrain_counts": {str(k): v for k, v in sorted(terrain.items())},
            },
            "players": players,
            "units": units,
            "variables": variables,
            "messages": messages,
            "trigger_display_order": list(scenario.trigger_manager.trigger_display_order),
            "triggers": triggers,
            "references": references(triggers, units, players),
            "external_xs": xs_manager.script_name,
        }


if __name__ == "__main__":
    json.dump(load_scenario(Path(sys.argv[1])), sys.stdout, ensure_ascii=False, allow_nan=False)
