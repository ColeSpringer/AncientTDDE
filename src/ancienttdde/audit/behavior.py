"""Extract observations from trigger data without correcting the legacy logic."""

import heapq
import re
from collections.abc import Mapping, Sequence
from typing import Any

from ancienttdde.audit.models import Purchase, Region, Wave


def of_type(components: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [c["attributes"] for c in components if c["type"] == kind]


def timer(trigger: Mapping[str, Any]) -> int | None:
    timers = of_type(trigger["conditions"], "timer")
    return timers[0]["timer"] if len(timers) == 1 else None


def region(attributes: dict[str, Any]) -> Region | None:
    coordinates = [attributes.get(key, -1) for key in ("area_x1", "area_y1", "area_x2", "area_y2")]
    return Region(*coordinates) if all(v is not None and v >= 0 for v in coordinates) else None


def activation_times(
    triggers: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, int], dict[int, int]]:
    """Earliest timer-chain times; guarded activations remain unknown.

    These are scheduled game-seconds, excluding engine tick granularity. This
    is not a simulation of looping triggers or object/research conditions.
    """
    by_id = {t["id"]: t for t in triggers}
    enabled_at: dict[int, int] = {}
    fires_at: dict[int, int] = {}
    queue = [(0, t["id"]) for t in triggers if t["enabled"]]
    heapq.heapify(queue)
    while queue:
        activation, identifier = heapq.heappop(queue)
        if identifier in enabled_at:
            continue
        enabled_at[identifier] = activation
        row = by_id[identifier]
        if any(
            c["type"] != "timer" or c["attributes"].get("inverted", 0) == 1
            for c in row["conditions"]
        ):
            continue
        delay = timer(row) or 0
        fires_at[identifier] = activation + delay
        for effect in of_type(row["effects"], "activate_trigger"):
            target = effect["trigger_id"]
            if target in by_id:
                heapq.heappush(queue, (activation + delay, target))
    return enabled_at, fires_at


def extract_waves(triggers: Sequence[Mapping[str, Any]]) -> list[Wave]:
    enabled_at, fires_at = activation_times(triggers)
    result: list[Wave] = []
    for row in triggers:
        regular = re.fullmatch(r"lvl (\d+-[A-E])", row["name"], re.IGNORECASE)
        boss = re.fullmatch(r"Boss (\d+)", row["name"])
        if boss is not None:
            key = f"boss-{boss[1]}"
        elif regular is not None:
            key = regular[1].upper()
        else:
            continue
        parents = [
            t
            for t in triggers
            if any(a["trigger_id"] == row["id"] for a in of_type(t["effects"], "activate_trigger"))
        ]
        starters = [t for t in parents if t["name"].lower().startswith("start ")]
        start = starters[0] if starters else None
        stops = [
            t
            for t in triggers
            if any(
                a["trigger_id"] == row["id"] for a in of_type(t["effects"], "deactivate_trigger")
            )
        ]
        stop = stops[0] if len(stops) == 1 else None
        start_seconds = fires_at.get(row["id"]) if boss else enabled_at.get(row["id"])
        duration = (
            fires_at[stop["id"]] - start_seconds
            if stop and stop["id"] in fires_at and start_seconds is not None
            else None
        )
        modifications: list[dict[str, Any]] = []
        activated: list[int] = []
        for source in ([start] if start else []) + [row]:
            modifications.extend(
                c
                for c in source["effects"]
                if c["type"] in {"change_object_hp", "damage_object", "change_object_attack"}
            )
            activated.extend(
                a["trigger_id"] for a in of_type(source["effects"], "activate_trigger")
            )
        spawns = tuple(
            {
                "object_id": a["object_list_unit_id"],
                "owner": a["source_player"],
                "x": a["location_x"],
                "y": a["location_y"],
            }
            for a in of_type(row["effects"], "create_object")
        )
        result.append(
            Wave(
                key=key,
                kind="boss" if boss else "regular",
                trigger_id=row["id"],
                start_trigger_id=start["id"] if start else None,
                stop_trigger_id=stop["id"] if stop else None,
                start_seconds=start_seconds,
                first_spawn_seconds=fires_at.get(row["id"]),
                duration_seconds=duration,
                interval_seconds=timer(row) if row["looping"] else None,
                spawns=spawns,
                modifications=tuple(modifications),
                activated_trigger_ids=tuple(activated),
            )
        )
    return result


def extract_purchases(
    triggers: Sequence[Mapping[str, Any]], purchase_ids: set[int]
) -> list[Purchase]:
    by_id = {t["id"]: t for t in triggers}
    result: list[Purchase] = []
    for identifier in sorted(purchase_ids):
        row = by_id[identifier]
        area_conditions = of_type(row["conditions"], "objects_in_area")
        if not area_conditions:
            raise ValueError(f"Purchase {identifier} has no area condition")
        condition = area_conditions[0]
        removal = of_type(row["effects"], "remove_object")
        payment = [
            a
            for a in removal
            if a.get("source_player") == condition["source_player"]
            and (a.get("object_group") in {59, -1, None})
        ]
        group = condition.get("object_group")
        result.append(
            Purchase(
                trigger_id=identifier,
                name=row["name"],
                player_id=condition["source_player"],
                required_kings=condition["quantity"],
                initially_enabled=bool(row["enabled"]),
                repeatable=bool(row["looping"]),
                condition_object_group=group if group is not None and group >= 0 else None,
                condition_region=region(condition),
                removal_regions=tuple(map(region, payment)),
                payment_policy="all_matching_objects_in_removal_regions",
                conditions=tuple(row["conditions"]),
                effects=tuple(row["effects"]),
                linked_triggers=tuple(
                    by_id[a["trigger_id"]] for a in of_type(row["effects"], "activate_trigger")
                ),
            )
        )
    return result
