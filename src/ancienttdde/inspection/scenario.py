"""Isolate parser state: each input is parsed in its own Python process."""

import contextlib
import json
import math
import os
import subprocess
import sys
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class ScenarioOptionsSnapshot(TypedDict):
    lock_teams: bool
    allow_players_choose_teams: bool
    random_start_points: bool
    secondary_game_modes: int | None
    legacy_execution_order: bool | None
    all_techs: bool
    victory_custom_conditions_required: bool
    computer_personalities_locked: bool | None


class GlobalVictorySnapshot(TypedDict):
    conquest_required: int
    ruins: int
    artifacts_required: int
    discovery: int
    explored_percent_of_map_required: int
    gold_required: int


class EffectRecordQuantity(Protocol):
    @property
    def quantity_float(self) -> object: ...


def inspect_scenario(
    path: Path, *, include_terrain: bool = False, include_game_settings: bool = False
) -> dict[str, Any]:
    arguments = [sys.executable, "-m", "ancienttdde.inspection.scenario", str(path.resolve())]
    if include_terrain:
        arguments.append("--terrain")
    if include_game_settings:
        arguments.append("--game-settings")
    process = subprocess.run(
        arguments,
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


def stored_float_quantity(stored: EffectRecordQuantity | None) -> float | None:
    """Return the float quantity an effect record holds, or None when the field is unused.

    Effects store float attribute values, such as movement speed, in a separate field that
    exists since scenario version 1.55; an unused field holds NaN. The parser raises KeyError
    for a field the scenario version does not define.
    """
    if stored is None:
        return None
    try:
        value = stored.quantity_float
    except AttributeError, KeyError:
        return None
    return value if isinstance(value, float) and math.isfinite(value) else None


def component(
    obj: Any, dataset: Any, kind: str, stored: EffectRecordQuantity | None = None
) -> dict[str, Any]:
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
        float_quantity = stored_float_quantity(stored)
        raw["_quantity_float"] = float_quantity
        if "quantity_float" in fields:
            attributes["quantity_float"] = float_quantity
        # The parser reads a float-valued quantity back as `float or int`, which turns a
        # stored 0.0 into the unused marker -1; the stored field is authoritative.
        if float_quantity is not None and not isinstance(obj._quantity_float, bytes):
            attributes["quantity"] = float_quantity
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


def load_scenario(
    path: Path, *, include_terrain: bool = False, include_game_settings: bool = False
) -> dict[str, Any]:
    # The pinned parser exposes no py.typed marker or type stubs.
    from AoE2ScenarioParser.datasets import (
        conditions,
        effects,
    )
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import (
        AoE2DEScenario,
    )

    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        scenario = AoE2DEScenario.from_file(str(path))
        triggers: list[dict[str, Any]] = []
        # Trigger and effect objects mirror the stored records in order; the records keep
        # field values the object layer merges away.
        stored_triggers = scenario.sections["Triggers"].trigger_data
        for trigger, stored in zip(scenario.trigger_manager.triggers, stored_triggers, strict=True):
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
            if include_game_settings:
                fields += ("execute_on_load",)
            triggers.append(
                {
                    "id": trigger.trigger_id,
                    **{f: scalar(getattr(trigger, f)) for f in fields},
                    "condition_order": list(trigger.condition_order),
                    "effect_order": list(trigger.effect_order),
                    "conditions": [
                        component(c, conditions, "condition_type") for c in trigger.conditions
                    ],
                    "effects": [
                        component(e, effects, "effect_type", stored=record)
                        for e, record in zip(trigger.effects, stored.effect_data, strict=True)
                    ],
                }
            )
        players: list[dict[str, Any]] = []
        for player in scenario.player_manager.players:
            # Raw inspection uses the parser's internal Gaia/non-Gaia field inventory.
            fields = player._object_attributes + player._object_attributes_non_gaia  # pyright: ignore[reportPrivateUsage]
            if include_game_settings:
                fields += ["lock_personality"]
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
        xs_manager = scenario.xs_manager
        option_manager = scenario.option_manager
        version: tuple[int, ...] = tuple(int(part) for part in scenario.scenario_version.split("."))
        secondary_modes = option_manager.secondary_game_modes if version >= (1, 42) else None
        if isinstance(secondary_modes, bytes):
            secondary_modes = int.from_bytes(secondary_modes, byteorder="little")
        options: ScenarioOptionsSnapshot = {
            "lock_teams": option_manager.lock_teams,
            "allow_players_choose_teams": option_manager.allow_players_choose_teams,
            "random_start_points": option_manager.random_start_points,
            "secondary_game_modes": secondary_modes,
            "legacy_execution_order": (
                option_manager.legacy_execution_order if version >= (1, 55) else None
            ),
            "all_techs": bool(scenario.sections["Options"].all_techs),
            "victory_custom_conditions_required": option_manager.victory_custom_conditions_required,
            "computer_personalities_locked": (
                all(
                    player.lock_personality
                    for player in scenario.player_manager.players[1:]
                    if not player.human
                )
                if version >= (1, 53)
                else None
            ),
        }
        global_victory = scenario.sections["GlobalVictory"]
        victory: GlobalVictorySnapshot = {
            "conquest_required": global_victory.conquest_required,
            "ruins": global_victory.ruins,
            "artifacts_required": global_victory.artifacts_required,
            "discovery": global_victory.discovery,
            "explored_percent_of_map_required": global_victory.explored_percent_of_map_required,
            "gold_required": global_victory.gold_required,
        }
        return {
            "scenario_version": scenario.scenario_version,
            "next_unit_id": scenario.sections["DataHeader"].next_unit_id_to_place,
            "victory_condition": scalar(scenario.option_manager.victory_condition),
            "options": options,
            "global_victory": victory,
            "map": {
                "width": scenario.map_manager.map_width,
                "height": scenario.map_manager.map_height,
                "terrain_counts": {str(k): v for k, v in sorted(terrain.items())},
                **(
                    {
                        "tiles": [
                            [tile.terrain_id, tile.elevation, tile.layer]
                            for tile in scenario.map_manager.terrain
                        ]
                    }
                    if include_terrain
                    else {}
                ),
            },
            "players": players,
            "units": units,
            "variables": variables,
            "messages": messages,
            "trigger_display_order": list(scenario.trigger_manager.trigger_display_order),
            "triggers": triggers,
            "references": references(triggers, units, players),
            "external_xs": xs_manager.script_name,
            "dependencies": {
                "external_xs": xs_manager.script_name,
                "embedded_xs": scalar(scenario.sections["Files"].script_file_content),
                "ai_files": len(scenario.sections["Files"].ai_files),
                "cinematics": [
                    scalar(getattr(scenario.sections["Cinematics"], field))
                    for field in ("ascii_pregame", "ascii_victory", "ascii_loss")
                ],
                "background_image": scalar(scenario.sections["BackgroundImage"].ascii_filename),
            },
            "embedded_ai": [
                {
                    "player_id": slot + 1,
                    "name": scenario.sections["PlayerDataTwo"].ai_names[slot],
                    "script": scenario.sections["PlayerDataTwo"].ai_files[slot].ai_per_file_text,
                    "type": scenario.sections["PlayerDataTwo"].ai_type[slot],
                }
                for slot in range(8)
            ],
        }


if __name__ == "__main__":
    json.dump(
        load_scenario(
            Path(sys.argv[1]),
            include_terrain="--terrain" in sys.argv[2:],
            include_game_settings="--game-settings" in sys.argv[2:],
        ),
        sys.stdout,
        ensure_ascii=False,
        allow_nan=False,
    )
