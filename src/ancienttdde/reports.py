"""Readable report views over the complete machine-readable evidence."""

from ancienttdde.inspection.behavior import of_type


def cell(value) -> str:
    return (
        str(value if value is not None else "unknown")
        .replace("\x00", "")
        .replace("|", "\\|")
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
    )


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def brief(component: dict) -> str:
    attrs = {k: v for k, v in component["attributes"].items() if v not in (-1, None, "", [])}
    return f"{component['type']}: {attrs}"


def render_reports(scenario: dict, dat: dict, behavior: dict, summary: dict) -> dict[str, str]:
    objects = {obj["id"]: obj for obj in dat["objects"]}
    enemy = next(
        (
            c["id"]
            for c in dat["civilizations"]
            if c["name"].casefold() == scenario["players"][8]["civilization"].casefold()
        ),
        8,
    )

    def name(uid):
        definition = objects[uid]["civilizations"].get(str(enemy))
        return definition["definition"]["Name"] if definition else str(uid)

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
                    f"{uid} / {name(uid)}" for uid in sorted({s["object_id"] for s in w["spawns"]})
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
    mechanics = "# Keep / replace / drop inventory\n\n" + table(
        ["Mechanic", "Decision", "Reason", "Migration", "Evidence trigger IDs"],
        [
            [m["key"], m["disposition"], m["reason"], m["migration"], m["trigger_ids"]]
            for m in behavior["mechanics"]
        ],
    )
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
    instructions = "# Displayed instructions (claims, not behavior)\n\n"
    for key in ("instructions", "hints", "victory", "loss", "history", "scouts"):
        instructions += f"## {key}\n\n" + scenario["messages"][key].replace("\r", "\n") + "\n\n"
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
    return {
        "README.md": index,
        "waves.md": waves,
        "shop.md": shop,
        "mechanics.md": mechanics,
        "civilizations.md": civs,
        "objects.md": object_report,
        "instructions.md": instructions,
        "triggers.md": triggers,
    }
