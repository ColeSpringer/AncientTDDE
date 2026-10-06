"""Readable report views over the complete machine-readable evidence."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ancienttdde.audit.behavior import of_type


def cell(value: object) -> str:
    return (
        str(value if value is not None else "unknown")
        .replace("\x00", "")
        .replace("|", "\\|")
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
    )


def table(headers: list[str], rows: Sequence[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def brief(component: dict[str, Any]) -> str:
    attrs = {k: v for k, v in component["attributes"].items() if v not in (-1, None, "", [])}
    return f"{component['type']}: {attrs}"


def enemy_table(scenario: Mapping[str, Any], dat: Mapping[str, Any]) -> int:
    """Return the DAT civilization table of the enemy slot, player 8."""
    return next(
        (
            c["id"]
            for c in dat["civilizations"]
            if c["name"].casefold() == scenario["players"][8]["civilization"].casefold()
        ),
        8,
    )


def enemy_name(objects: Mapping[int, Mapping[str, Any]], enemy: int, uid: int) -> str:
    """Return an object's name in the enemy's DAT table, or its ID when that table lacks it."""
    obj = objects.get(uid)
    if obj is None:
        raise ValueError(f"DAT has no object {uid}")
    definition = obj["civilizations"].get(str(enemy))
    return definition["definition"]["Name"] if definition else str(uid)


def index_report(summary: Mapping[str, Any]) -> str:
    index = "# Original behavior audit\n\n"
    index += table(["Observation", "Value"], [[k, v] for k, v in summary.items()])
    index += (
        "\nSee `waves.md`, `shop.md`, `mechanics.md`, `civilizations.md`, `objects.md`, "
        "`triggers.md` and `instructions.md`. Complete raw evidence is in `scenario.json`, "
        "`dat.json` and `behavior.json`; `manifest.json` records all inputs and artifacts.\n\n"
        "This is static inspection. Timer chains exclude engine tick granularity. Native "
        "civilization differences and legacy DAT changes cannot be separated without a "
        "version-matched stock baseline. Migration decisions are in `migration.json`.\n"
    )
    return index


def waves_report(
    behavior: Mapping[str, Any], objects: Mapping[int, Mapping[str, Any]], enemy: int
) -> str:
    waves = "# Complete wave schedule\n\n" + behavior["timing_note"] + "\n\n"
    waves += table(
        [
            "Wave",
            "Spawn trigger",
            "Start s",
            "First spawn s",
            "Duration s",
            "Interval s",
            "Object IDs / enemy DAT names",
            "Spawns per lane",
        ],
        [
            [
                w["key"],
                w["trigger_id"],
                w["start_seconds"],
                w["first_spawn_seconds"],
                w["duration_seconds"],
                w["interval_seconds"],
                ", ".join(
                    f"{uid} / {enemy_name(objects, enemy, uid)}"
                    for uid in sorted({s["object_id"] for s in w["spawns"]})
                ),
                len(w["spawns"]) // 7,
            ]
            for w in behavior["waves"]
        ],
    )
    for w in behavior["waves"]:
        waves += (
            f"\n## {w['key']}\n\nStart trigger: {w['start_trigger_id']}; "
            f"stop trigger: {w['stop_trigger_id']}; "
            f"activated IDs: {w['activated_trigger_ids']}.\n\n"
        )
        waves += table(
            ["Owner", "Object", "X", "Y"],
            [[s["owner"], s["object_id"], s["x"], s["y"]] for s in w["spawns"]],
        )
        waves += "\n" + "\n".join(brief(c) for c in w["modifications"]) + "\n"
    return waves


def shop_report(behavior: Mapping[str, Any]) -> str:
    shop = (
        "# Complete shop catalog\n\nThresholds are condition quantities. Original removal "
        "effects consume every matching object in their regions, with no exact payment cap. "
        "The condition and removal regions can differ. Unfiltered conditions are preserved.\n\n"
    )
    shop += table(
        [
            "Trigger",
            "Purchase",
            "Player",
            "King threshold",
            "Repeated",
            "Enabled",
            "Condition group",
            "Condition region",
            "Removal regions",
            "Activated triggers",
        ],
        [
            [
                p["trigger_id"],
                p["name"],
                p["player_id"],
                p["required_kings"],
                p["repeatable"],
                p["initially_enabled"],
                p["condition_object_group"],
                p["condition_region"],
                p["removal_regions"],
                [t["id"] for t in p["linked_triggers"]],
            ]
            for p in behavior["purchases"]
        ],
    )
    for p in behavior["purchases"]:
        if p["player_id"] != 1:
            continue
        shop += f"\n## {p['name']} (trigger {p['trigger_id']})\n\n"
        shop += table(
            ["Effect", "Observed attributes"], [[c["type"], brief(c)] for c in p["effects"]]
        )
        for linked in p["linked_triggers"]:
            shop += f"\nLinked trigger {linked['id']}: {linked['name']}\n\n"
            shop += table(
                ["Condition / effect", "Observed attributes"],
                [[c["type"], brief(c)] for c in linked["conditions"] + linked["effects"]],
            )
    return shop


def mechanics_report(behavior: Mapping[str, Any]) -> str:
    mechanics = "# Keep / replace / drop inventory\n\n" + table(
        ["Mechanic", "Decision", "Reason", "Migration", "Evidence trigger IDs"],
        [
            [m["key"], m["disposition"], m["reason"], m["migration"], m["trigger_ids"]]
            for m in behavior["mechanics"]
        ],
    )
    return mechanics


def civilizations_report(
    scenario: Mapping[str, Any], dat: Mapping[str, Any], behavior: Mapping[str, Any], enemy: int
) -> str:
    civs = (
        "# Civilization and enemy definitions\n\nGaia uses DAT table 0. The enemy slot "
        f"uses DAT table {enemy}. Human and Gaia definitions must not be conflated. "
        "Tech tree and team bonus IDs refer to DAT effects, not technologies.\n\n"
    )
    civs += table(
        [
            "DAT table",
            "Civilization",
            "Tech-tree effect",
            "Team-bonus effect",
            "Units",
            "Civilization tech IDs",
        ],
        [
            [
                c["id"],
                c["name"],
                c["tech_tree_id"],
                c["team_bonus_id"],
                c["unit_count"],
                c["civilization_technology_ids"],
            ]
            for c in dat["civilizations"]
        ],
    )
    civs += "\n## Scenario adjustments\n\n"
    civ_ids = {
        i
        for m in behavior["mechanics"]
        if m["key"] == "civilization_adjustments"
        for i in m["trigger_ids"]
    }
    for t in scenario["triggers"]:
        if t["id"] in civ_ids and (
            not of_type(t["conditions"], "research_technology")
            or of_type(t["conditions"], "research_technology")[0].get("source_player") == 1
        ):
            civs += f"\n### {t['id']}: {t['name']}\n\n"
            civs += table(
                ["Condition / effect", "Attributes"],
                [[c["type"], brief(c)] for c in t["conditions"] + t["effects"]],
            )
    return civs


def objects_report(dat: Mapping[str, Any], enemy: int) -> str:
    object_report = (
        "# Object and graphics dependencies\n\nEvery referenced type is inspected "
        "in all legacy civilization tables in `dat.json`. The table summarizes "
        "Gaia and enemy identities and graphics supplied by the original package.\n\n"
    )
    object_report += table(
        [
            "ID",
            "Gaia name",
            "Gaia HP",
            "Enemy name",
            "Enemy HP",
            "Supplied graphic IDs across civs",
        ],
        [
            [
                o["id"],
                o["civilizations"]["0"]["definition"]["Name"],
                o["civilizations"]["0"]["definition"]["HitPoints"],
                o["civilizations"][str(enemy)]["definition"]["Name"],
                o["civilizations"][str(enemy)]["definition"]["HitPoints"],
                sorted({gid for d in o["civilizations"].values() for gid in d["custom_graphics"]}),
            ]
            for o in dat["objects"]
        ],
    )
    object_report += "\n## Supplied graphic definitions\n\n" + table(
        ["DAT graphic", "Original asset", "DAT name"],
        [[g["id"], g["asset"], g["definition"].get("Name", "")] for g in dat["custom_graphics"]],
    )
    return object_report


def instructions_report(scenario: Mapping[str, Any]) -> str:
    instructions = "# Displayed instructions (claims, not behavior)\n\n"
    for key in ("instructions", "hints", "victory", "loss", "history", "scouts"):
        instructions += f"## {key}\n\n" + scenario["messages"][key].replace("\r", "\n") + "\n\n"
    return instructions


def triggers_report(scenario: Mapping[str, Any]) -> str:
    triggers = (
        "# Trigger evidence\n\nIDs are storage IDs; display and effect order are "
        "retained in `scenario.json`. Sentinel values are retained in the JSON raw fields.\n"
    )
    for t in scenario["triggers"]:
        triggers += (
            f"\n## {t['id']}: {cell(t['name'])}\n\n"
            f"Enabled: {t['enabled']}; looping: {t['looping']}.\n\n"
        )
        triggers += table(
            ["Condition / effect", "Observed attributes"],
            [[c["type"], brief(c)] for c in t["conditions"] + t["effects"]],
        )
    return triggers


@dataclass(frozen=True)
class ReportInputs:
    scenario: Mapping[str, Any]
    dat: Mapping[str, Any]
    behavior: Mapping[str, Any]
    summary: Mapping[str, Any]
    enemy: int
    # The DAT objects by ID, indexed once for every report.
    objects: Mapping[int, Mapping[str, Any]]


# Every report's file name and renderer; the audit publishes exactly these files.
RENDERERS: dict[str, Callable[[ReportInputs], str]] = {
    "README.md": lambda r: index_report(r.summary),
    "waves.md": lambda r: waves_report(r.behavior, r.objects, r.enemy),
    "shop.md": lambda r: shop_report(r.behavior),
    "mechanics.md": lambda r: mechanics_report(r.behavior),
    "civilizations.md": lambda r: civilizations_report(r.scenario, r.dat, r.behavior, r.enemy),
    "objects.md": lambda r: objects_report(r.dat, r.enemy),
    "instructions.md": lambda r: instructions_report(r.scenario),
    "triggers.md": lambda r: triggers_report(r.scenario),
}
REPORTS = tuple(RENDERERS)


def render_reports(
    scenario: Mapping[str, Any],
    dat: Mapping[str, Any],
    behavior: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, str]:
    objects = {o["id"]: o for o in dat["objects"]}
    inputs = ReportInputs(scenario, dat, behavior, summary, enemy_table(scenario, dat), objects)
    return {name: render(inputs) for name, render in RENDERERS.items()}
