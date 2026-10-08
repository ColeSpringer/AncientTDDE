"""Snapshot the installed DE data the balance model reads into content/balance/stock.json.

Usage: uv run python tools/dat/stock_stats.py <empires2_x2_p1.dat> content/balance/stock.json

The data file's Gaia table supplies every unit the model needs, the wave schedule's enemies in
game.json beside the output included; each civilization's technology tree says which of the
watched technologies it can never research. Pass the game's CivTechTrees directory as a third
argument to cross-check tower availability against the game's own trees.
"""

import json
import sys
from functools import cache
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.heroes import HeroInfo
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.units import UnitInfo
from genieutils.datfile import DatFile
from genieutils.effect import EffectCommand
from genieutils.tech import Tech
from genieutils.unit import Unit

from ancienttdde.common.data import write_json
from ancienttdde.common.hashing import hash_file
from ancienttdde.game.config import load_balance
from ancienttdde.game.stock import (
    MELEE_CLASS,
    PIERCE_CLASS,
    REQUIRED_UNITS,
    RESOURCE_NAMES,
    TOWER_CLASS,
    WATCHED_TECHNOLOGIES,
    class_amount,
)

# Effect command types and the attributes the tower summary reads.
ATTRIBUTE_SET, ATTRIBUTE_ADD, ATTRIBUTE_MULTIPLY, DISABLE_TECH = 0, 4, 5, 102
HIT_POINTS, ARMOR, ATTACK, MAXIMUM_RANGE, MINIMUM_RANGE = 0, 8, 9, 12, 20
WATCH_TOWER = BuildingInfo["WATCH_TOWER"].ID
RELIC_GOLD_PRODUCTION_RATE = 191
TREE_NAMES = {"GUARD_TOWER": "Guard Tower", "KEEP": "Keep", "BOMBARD_TOWER": "Bombard Tower"}
# Tree files named differently from the data file's civilization names.
TREE_FILES = {
    "British": "BRITONS",
    "French": "FRANKS",
    "Byzantine": "BYZANTINES",
    "Mayan": "MAYANS",
    "Hindustanis": "INDIANS",
    "Magyars": "MAGYAR",
}


def tree_file(civilization: str) -> str:
    """The CivTechTrees file stem for a data file civilization name."""
    return TREE_FILES.get(civilization, civilization.upper())


def unit_id(name: str) -> int:
    for dataset in (UnitInfo, HeroInfo, BuildingInfo, OtherInfo):
        if name in dataset.__members__:
            return dataset[name].ID
    raise ValueError(f"Unknown unit: {name}")


def resource_name(kind: int) -> str | None:
    return RESOURCE_NAMES[kind] if 0 <= kind < len(RESOURCE_NAMES) else None


def number(value: float) -> float:
    rounded = round(value, 5)
    return int(rounded) if rounded == int(rounded) else rounded


def unit_record(unit: Unit) -> dict[str, object]:
    combat = unit.type_50
    creatable = unit.creatable
    cost: dict[str, int] = {}
    build_time = 0
    if creatable is not None:
        for entry in creatable.resource_costs:
            name = resource_name(entry.type)
            if name is not None and entry.flag == 1 and entry.amount > 0:
                cost[name] = int(entry.amount)
        times = [t.train_time for t in creatable.train_locations if t.train_time > 0]
        build_time = times[0] if times else 0
    storage = max((int(s.amount) for s in unit.resource_storages if s.amount > 0), default=0)
    return {
        "id": unit.id,
        "class": unit.class_,
        "hit_points": unit.hit_points,
        "attack": [[a.class_, number(a.amount)] for a in combat.attacks] if combat else [],
        "armor": [[a.class_, number(a.amount)] for a in combat.armours] if combat else [],
        "reload": number(combat.reload_time) if combat else 0,
        "range": number(combat.max_range) if combat else 0,
        "min_range": number(combat.min_range) if combat else 0,
        "accuracy": combat.accuracy_percent if combat else 100,
        "speed": number(unit.speed or 0.0),
        "line_of_sight": number(unit.line_of_sight),
        "cost": cost,
        "build_time": build_time,
        "work_rate": number(unit.bird.work_rate) if unit.bird else 0,
        "storage": storage,
    }


def applies_to_watch_tower(command: EffectCommand) -> bool:
    return command.a == WATCH_TOWER or (command.a == -1 and command.b == TOWER_CLASS)


def tower_effects(commands: list[EffectCommand]) -> dict[str, object]:
    """What the technology does to the Watch Tower, which stands for the family."""
    effects: dict[str, object] = {}
    attack = range_ = melee = pierce = 0
    hit_points_percent = 0
    for command in commands:
        if not applies_to_watch_tower(command):
            continue
        if command.type == ATTRIBUTE_ADD and command.c == ATTACK:
            damage_class, amount = class_amount(command.d)
            if damage_class == PIERCE_CLASS:
                attack += int(amount)
        elif command.type == ATTRIBUTE_ADD and command.c == ARMOR:
            damage_class, amount = class_amount(command.d)
            if damage_class == MELEE_CLASS:
                melee += int(amount)
            elif damage_class == PIERCE_CLASS:
                pierce += int(amount)
        elif command.type == ATTRIBUTE_ADD and command.c == MAXIMUM_RANGE:
            range_ += int(command.d)
        elif command.type == ATTRIBUTE_MULTIPLY and command.c == HIT_POINTS:
            hit_points_percent += round((command.d - 1) * 100)
        elif command.type == ATTRIBUTE_SET and command.c == MINIMUM_RANGE and command.d == 0:
            effects["minimum_range_removed"] = True
    for key, value in (
        ("attack", attack),
        ("range", range_),
        ("hit_points_percent", hit_points_percent),
        ("melee_armor", melee),
        ("pierce_armor", pierce),
    ):
        if value:
            effects[key] = value
    return effects


def technology_record(dat: DatFile, tech: Tech, identifier: int) -> dict[str, object]:
    cost: dict[str, int] = {}
    for entry in tech.resource_costs:
        name = resource_name(entry.type)
        if name is not None and entry.flag == 1 and entry.amount > 0:
            cost[name] = int(entry.amount)
    times = [r.research_time for r in tech.research_locations if r.research_time > 0]
    commands = dat.effects[tech.effect_id].effect_commands if tech.effect_id >= 0 else []
    return {
        "id": identifier,
        "cost": cost,
        "time": times[0] if times else 0,
        "towers": tower_effects(commands),
    }


def lacking(dat: DatFile, tech_tree_effect: int) -> list[str]:
    """Watched technologies the tree disables, directly or through what they require."""
    disabled = {
        int(c.d) for c in dat.effects[tech_tree_effect].effect_commands if c.type == DISABLE_TECH
    }

    @cache
    def reachable(identifier: int) -> bool:
        if identifier in disabled:
            return False
        tech = dat.techs[identifier]
        needed = [t for t in tech.required_techs if t >= 0]
        met = sum(reachable(t) for t in needed)
        return met >= min(tech.required_tech_count, len(needed))

    return sorted(name for name, tech in WATCHED_TECHNOLOGIES.items() if not reachable(tech))


def tree_lacks(trees: Path, civilization: str) -> set[str] | None:
    """The tower technologies the game's own tree screen withholds, when the tree exists: nodes
    marked unavailable, and towers the screen does not list at all."""
    path = trees / f"{tree_file(civilization)}.json"
    if not path.is_file():
        print(f"{civilization}: no tree file {path.name}; tree screen not checked")
        return None
    status = {
        str(node.get("Name")): node.get("Node Status")
        for node in find_nodes(json.loads(path.read_text(encoding="utf-8")))
    }
    return {key for key, label in TREE_NAMES.items() if status.get(label) != "ResearchedCompleted"}


def find_nodes(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, dict):
        node = cast(dict[str, object], value)
        if "Node Status" in node:
            found.append(node)
        for child in node.values():
            found.extend(find_nodes(child))
    elif isinstance(value, list):
        for child in cast(list[object], value):
            found.extend(find_nodes(child))
    return found


def snapshot(dat_path: Path, trees: Path | None, wanted: set[str]) -> dict[str, object]:
    dat = DatFile.parse(dat_path)
    gaia = dat.civs[0]
    units = {
        name: unit_record(cast(Unit, gaia.units[unit_id(name)]))
        for name in sorted(REQUIRED_UNITS | wanted)
    }
    technologies = {
        name: technology_record(dat, dat.techs[identifier], identifier)
        for name, identifier in WATCHED_TECHNOLOGIES.items()
    }
    civilizations: list[dict[str, object]] = []
    for identifier, civilization in enumerate(dat.civs):
        if identifier == 0:
            continue
        lacks = lacking(dat, civilization.tech_tree_id)
        if trees is not None:
            expected = tree_lacks(trees, civilization.name)
            if expected is not None and expected != {n for n in lacks if n in TREE_NAMES}:
                # The data file decides what the game researches; the tree screen may omit it.
                withheld = sorted(expected)
                print(f"{civilization.name}: tree screen withholds {withheld}, data says {lacks}")
        civilizations.append({"id": identifier, "name": civilization.name, "lacks": lacks})
    return {
        "schema_version": 1,
        "source": {
            "file": dat_path.name,
            "version": dat.version,
            "sha256": hash_file(dat_path),
            "civilizations": len(dat.civs),
        },
        "relic_gold_per_minute": int(gaia.resources[RELIC_GOLD_PRODUCTION_RATE]),
        "civilizations": civilizations,
        "units": units,
        "technologies": technologies,
    }


def wave_units(output: Path) -> set[str]:
    """The enemies the wave schedule beside the output names; the output belongs beside it."""
    schedule = output.with_name("game.json")
    if not schedule.is_file():
        raise ValueError(f"The snapshot belongs beside the wave schedule; no {schedule}")
    return {wave.unit for wave in load_balance(schedule).waves}


if __name__ == "__main__":
    trees_directory = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    output_path = Path(sys.argv[2])
    write_json(output_path, snapshot(Path(sys.argv[1]), trees_directory, wave_units(output_path)))
