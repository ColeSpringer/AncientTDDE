"""Typed views of an inspected scenario, its references and its gameplay digests."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, TypedDict

from ancienttdde.common.data import JSONValue
from ancienttdde.common.hashing import hash_json

type ReferenceKind = Literal["object", "instance", "technology", "trigger", "variable"]


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


class MapSnapshot(TypedDict):
    width: int
    height: int
    terrain_counts: dict[str, int]
    # Inspected only on request (--terrain).
    tiles: NotRequired[list[list[int]]]


class PlayerSnapshot(TypedDict):
    player_id: int
    civilization: str
    active: bool
    human: bool
    lock_civ: bool
    # Inspected only on request (--game-settings).
    lock_personality: NotRequired[bool]
    starting_age: int
    population_cap: int | None
    allied_victory: bool | None
    diplomacy: list[int] | None
    food: int
    wood: int
    gold: int
    stone: int
    color: int
    architecture_set: str
    base_priority: int | None
    initial_camera_x: int | None
    initial_camera_y: int | None
    initial_player_view_x: int
    initial_player_view_y: int
    string_table_name_id: int | None
    tribe_name: str | None
    disabled_units: list[int] | None
    disabled_buildings: list[int] | None
    disabled_techs: list[int] | None


class DependencySnapshot(TypedDict):
    external_xs: str
    embedded_xs: str
    ai_files: int
    cinematics: list[str]
    background_image: str


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


class AiSnapshot(TypedDict):
    player_id: int
    name: str
    script: str
    type: int


class ComponentRecord(TypedDict):
    """A trigger condition or effect: named attributes and every stored field."""

    type: str
    type_id: int
    attributes: dict[str, JSONValue]
    raw: dict[str, JSONValue]


class TriggerRecord(TypedDict):
    id: int
    name: str
    description: str
    short_description: str
    enabled: int
    looping: int
    display_as_objective: int
    display_on_screen: int
    description_order: int
    header: int
    mute_objectives: int
    # Inspected only on request (--game-settings).
    execute_on_load: NotRequired[int]
    condition_order: list[int]
    effect_order: list[int]
    conditions: list[ComponentRecord]
    effects: list[ComponentRecord]


class VariableRecord(TypedDict):
    variable_id: int
    name: str


class ReferenceOccurrence(TypedDict):
    kind: ReferenceKind
    id: int
    path: str
    player_id: int | None


class ReferenceIndex(TypedDict):
    object_ids: list[int]
    instance_ids: list[int]
    technology_ids: list[int]
    trigger_ids: list[int]
    variable_ids: list[int]
    occurrences: list[ReferenceOccurrence]


class ScenarioSnapshot(TypedDict):
    """Every field the inspection worker emits for a scenario."""

    scenario_version: str
    next_unit_id: int
    victory_condition: int
    options: ScenarioOptionsSnapshot
    global_victory: GlobalVictorySnapshot
    map: MapSnapshot
    players: list[PlayerSnapshot]
    units: list[MapUnit]
    variables: list[VariableRecord]
    messages: dict[str, JSONValue]
    trigger_display_order: list[int]
    triggers: list[TriggerRecord]
    references: ReferenceIndex
    external_xs: str
    dependencies: DependencySnapshot
    embedded_ai: list[AiSnapshot]


def references(
    triggers: Sequence[Mapping[str, Any]],
    units: Sequence[Mapping[str, Any]],
    players: Sequence[Mapping[str, Any]],
) -> ReferenceIndex:
    """Index the IDs a scenario refers to, as the worker extracts them from parser rows.

    Object, placed-instance, technology, trigger and variable IDs are separate namespaces.
    """
    occurrences: list[ReferenceOccurrence] = []

    def add(kind: ReferenceKind, identifier: object, path: str, owner: int | None = None) -> None:
        if type(identifier) is int and identifier >= 0:
            occurrences.append(
                ReferenceOccurrence(kind=kind, id=identifier, path=path, player_id=owner)
            )

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

    def ids(kind: ReferenceKind) -> list[int]:
        return sorted({o["id"] for o in occurrences if o["kind"] == kind})

    return ReferenceIndex(
        object_ids=ids("object"),
        instance_ids=ids("instance"),
        technology_ids=ids("technology"),
        trigger_ids=ids("trigger"),
        variable_ids=ids("variable"),
        occurrences=occurrences,
    )


def validate_references(scenario: ScenarioSnapshot) -> list[dict[str, JSONValue]]:
    """Return referenced trigger, placed-instance and variable IDs the scenario lacks."""
    index = scenario["references"]
    known: tuple[tuple[str, list[int], set[int]], ...] = (
        ("trigger", index["trigger_ids"], {t["id"] for t in scenario["triggers"]}),
        ("instance", index["instance_ids"], {u["reference_id"] for u in scenario["units"]}),
        ("variable", index["variable_ids"], {v["variable_id"] for v in scenario["variables"]}),
    )
    return [
        {"kind": kind, "id": identifier}
        for kind, used, available in known
        for identifier in used
        if identifier not in available
    ]


def scenario_digest(snapshot: ScenarioSnapshot) -> str:
    # Scenario headers can carry save metadata; gameplay-relevant content is stable.
    terrain = snapshot["map"]
    if "tiles" not in terrain:
        raise ValueError("A scenario digest needs the inspected terrain tiles")
    return hash_json(
        {
            "version": snapshot["scenario_version"],
            "next_unit_id": snapshot["next_unit_id"],
            "victory_condition": snapshot["victory_condition"],
            "map": {
                "width": terrain["width"],
                "height": terrain["height"],
                "tiles": terrain["tiles"],
            },
            "units": sorted(snapshot["units"], key=lambda u: u["reference_id"]),
            "players": snapshot["players"],
            "dependencies": snapshot["dependencies"],
            "triggers": snapshot["triggers"],
            "variables": snapshot["variables"],
        }
    )


def content_digest(snapshot: ScenarioSnapshot) -> str:
    """Digest the scenario plus embedded AI, messages, options and victory settings."""
    return hash_json(
        {
            "scenario": scenario_digest(snapshot),
            "embedded_ai": snapshot["embedded_ai"],
            "messages": snapshot["messages"],
            "options": snapshot["options"],
            "global_victory": snapshot["global_victory"],
        }
    )
