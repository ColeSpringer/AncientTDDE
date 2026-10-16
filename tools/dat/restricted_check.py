"""Check the restriction tables against the installed DE data.

Usage: uv run python tools/dat/restricted_check.py <empires2_x2_p1.dat>

Prints the units a lane could still train at the buildings it keeps (its market, dock,
monasteries, mills, camps and a bought castle) that restricted.OBJECTS does not list, the
technologies that enable or upgrade into a listed object or turn villagers into something
else that restricted.TECHNOLOGIES does not list, the age forms restricted.AGE_UPGRADES
misses, and the research a lane's buildings offer that touches nothing a lane can own but
is missing from restricted.POINTLESS, or listed there although it touches something. An empty
report means the tables match the data file.
"""

import sys
from pathlib import Path

from AoE2ScenarioParser.datasets.techs import TechInfo
from genieutils.datfile import DatFile
from genieutils.effect import EffectCommand

from ancienttdde.game.config import RULED_OUT, TOWER_RANGE, Balance, load_balance
from ancienttdde.game.restricted import AGE_UPGRADES, OBJECTS, POINTLESS, TECHNOLOGIES
from ancienttdde.game.script import LANE_CLASSES

ENABLE_UNIT, UPGRADE_UNIT = 2, 3
AGES = {101: "FEUDAL_AGE", 102: "CASTLE_AGE", 103: "IMPERIAL_AGE"}
# Units a lane may still train: traders (the loaded cart included) and mule carts.
ALLOWED = frozenset({128, 204, 17, 1808})
# The buildings a lane keeps or may buy, every age form included: market, dock, monastery,
# mill, lumber camp, mining camp, Folwark and castle.
TRAINERS = frozenset(
    {84, 116, 137, 45, 133, 47, 51, 1189, 104, 30, 31, 32, 1806, 68, 129, 130, 131, 1734, 1711}
    | {1720, 562, 563, 564, 565, 584, 585, 586, 587, 82, 2418}
)
VILLAGERS = frozenset({83, 293, 118, 120, 122, 123, 124, 156})
# The buildings whose research a lane can see: the trainers plus its blacksmith and
# university, every age form included.
RESEARCHERS = TRAINERS | {103, 105, 18, 19, 209, 210}
# What else a lane owns: Kings, monks, relics, trebuchets packed and not, farms, life
# Outposts, the towers and Accursed Towers, the castle, blacksmith, university and yurts.
LANE_UNITS = frozenset(
    {434, 125, 285, 42, 331, 50, 598, 684, 79, 234, 235, 236, 82, 2418, 103, 105, 18, 19, 209}
    | {210, 718, 719}
)
# Effect commands that change a unit or class (set, add, multiply), enable or upgrade one,
# or spawn one at a building: the free villagers some civilizations' research brings appear
# at a Town Center, which no lane has. The team, enemy and neutral variants add tens to
# these, and the clamped attribute variants two hundred.
ATTRIBUTE_SET, ATTRIBUTE_ADD, ATTRIBUTE_MULTIPLY, SPAWN_UNIT = 0, 4, 5, 7


def base_command(kind: int) -> int:
    if 10 <= kind < 50:
        return kind % 10
    if 200 <= kind < 210:
        return kind - 200
    return kind


AGES_AND_STARTS = {101, 102, 103}


def ownable(dat: DatFile, balance: Balance) -> tuple[set[int], set[int]]:
    """The units a lane can own, and their classes: villagers of every task, the trainable
    units, its buildings, the raiders the game sells, everything LANE_UNITS lists, and the
    projectiles those units fire, with every form a technology upgrades them into."""
    raiders = balance.interaction.raiders
    sold = set(raiders.land.line_ids) | set(raiders.naval.line_ids)
    units = set(VILLAGERS) | set(ALLOWED) | set(TRAINERS) | set(LANE_UNITS) | sold
    gaia = [u for u in dat.civs[0].units if u is not None]
    units |= {u.id for u in gaia if u.class_ == 4}
    projectiles: set[int] = set()
    for unit in gaia:
        if unit.id in units:
            if unit.type_50 is not None and unit.type_50.projectile_unit_id >= 0:
                projectiles.add(unit.type_50.projectile_unit_id)
            if unit.creatable is not None and unit.creatable.secondary_projectile_unit >= 0:
                projectiles.add(unit.creatable.secondary_projectile_unit)
    upgrades = [
        (command.a, command.b)
        for tech in dat.techs
        if tech.effect_id >= 0
        for command in dat.effects[tech.effect_id].effect_commands
        if command.type == UPGRADE_UNIT
    ]
    grown = True
    while grown:
        grown = False
        for source, target in upgrades:
            if source in projectiles and target not in projectiles:
                projectiles.add(target)
                grown = True
    units |= projectiles
    classes = {u.class_ for u in gaia if u.id in units}
    return units, classes


def touches_a_lane(
    commands: list[EffectCommand], units: set[int], classes: set[int], *, hidden: bool = False
) -> bool:
    """Whether any effect command could change something a lane owns or its resources. A
    hidden technology (one no building offers, as civilization bonuses are) counts only by
    what it does to units: its resource changes are the counters of its own bonus."""
    for command in commands:
        kind, a, b = base_command(command.type), command.a, command.b
        if kind in (ATTRIBUTE_SET, ATTRIBUTE_ADD, ATTRIBUTE_MULTIPLY):
            if (a >= 0 and a in units) or (a < 0 and b in classes):
                return True
        elif kind in (ENABLE_UNIT, UPGRADE_UNIT):
            if a in units:
                return True
        elif kind != SPAWN_UNIT and not hidden:
            return True
    return False


def check_pointless(dat: DatFile, root: Path) -> list[str]:
    """Research a lane's buildings offer that changes nothing a lane owns, by itself or
    through the technologies that require it and are not withheld, must be listed in
    POINTLESS, and nothing else may be."""
    balance = load_balance(root / "content/balance/game.json")
    units, classes = ownable(dat, balance)
    starting = {TechInfo[n].ID for n in balance.economy.starting_technologies}
    ruled = {TechInfo[n].ID for n in RULED_OUT + TOWER_RANGE}
    withheld = set(TECHNOLOGIES) | ruled | set(POINTLESS)

    def touches(tech_id: int, seen: set[int]) -> bool:
        tech = dat.techs[tech_id]
        commands = dat.effects[tech.effect_id].effect_commands if tech.effect_id >= 0 else []
        hidden = not any(r.location_id >= 0 for r in tech.research_locations)
        if touches_a_lane(list(commands), units, classes, hidden=hidden):
            return True
        seen.add(tech_id)
        for other_id, other in enumerate(dat.techs):
            if other_id in seen or other_id in withheld or tech_id not in other.required_techs:
                continue
            if touches(other_id, seen):
                return True
        return False

    lines: list[str] = []
    for tech_id, tech in enumerate(dat.techs):
        locations = {r.location_id for r in tech.research_locations}
        if not locations & RESEARCHERS:
            continue
        if tech_id in TECHNOLOGIES or tech_id in ruled or tech_id in starting:
            continue
        if tech_id in AGES_AND_STARTS:
            continue
        pointless = not touches(tech_id, set())
        name = (tech.name or "").strip()
        if pointless and tech_id not in POINTLESS:
            lines.append(f"pointless but not restricted: {tech_id} {name}")
        elif not pointless and tech_id in POINTLESS:
            lines.append(f"restricted as pointless but changes a lane: {tech_id} {name}")
    lines += [
        f"restricted as pointless but not researchable at a lane building: {t} {n}"
        for t, n in POINTLESS.items()
        if not {r.location_id for r in dat.techs[t].research_locations} & RESEARCHERS
    ]
    return lines


def check(dat_path: Path, root: Path) -> list[str]:
    dat = DatFile.parse(dat_path)
    names = {u.id: (u.name or "").strip() for u in dat.civs[0].units if u is not None}
    lines: list[str] = []
    trainable: set[int] = set()
    for civ in dat.civs[1:]:
        for unit in civ.units:
            if unit is None or unit.creatable is None or unit.id in ALLOWED or unit.id in OBJECTS:
                continue
            if any(t.unit_id in TRAINERS for t in unit.creatable.train_locations):
                trainable.add(unit.id)
    for unit_id in sorted(trainable):
        lines.append(f"trainable but not restricted: {unit_id} {names.get(unit_id, '')}")
    missing: set[tuple[int, str, int]] = set()
    age_gaps: set[tuple[str, int, str]] = set()
    for tech_id, tech in enumerate(dat.techs):
        if tech.effect_id < 0:
            continue
        for command in dat.effects[tech.effect_id].effect_commands:
            if command.type == ENABLE_UNIT and command.b != 0 and command.a in OBJECTS:
                target = command.a
            elif command.type == UPGRADE_UNIT and command.b in OBJECTS:
                target = command.b
            elif command.type == UPGRADE_UNIT and command.a in VILLAGERS:
                # A technology that turns villagers into something else.
                target = command.b
            else:
                continue
            if tech_id in AGES:
                age = AGES[tech_id]
                forms = OBJECTS if age == "FEUDAL_AGE" else AGE_UPGRADES[age]
                if target not in forms:
                    age_gaps.add((age, target, names.get(target, "")))
            elif tech_id not in TECHNOLOGIES:
                missing.add((tech_id, (tech.name or "").strip(), target))
    lines += [
        f"technology not restricted: {t} {name} -> {target}" for t, name, target in sorted(missing)
    ]
    lines += [
        f"age form not re-disabled: {age} {target} {name}" for age, target, name in sorted(age_gaps)
    ]
    return lines + check_pointless(dat, root) + check_lane_classes(dat, root)


def check_lane_classes(dat: DatFile, root: Path) -> list[str]:
    """Every unit a lane can own belongs to a class the lane's cleanup queries."""
    balance = load_balance(root / "content/balance/game.json")
    units, _ = ownable(dat, balance)
    names = {u.id: (u.name or "").strip() for u in dat.civs[0].units if u is not None}
    classes = {u.id: u.class_ for u in dat.civs[0].units if u is not None}
    # Projectiles are nobody's to clean up, and relics stay Gaia's wherever they lie.
    missed = sorted(
        (classes[u], u, names[u])
        for u in units
        if u in classes and classes[u] not in LANE_CLASSES and "Projectile" not in names[u]
        if u != 285
    )
    return [f"class not cleaned up: {c} ({n}, {u})" for c, u, n in missed]


if __name__ == "__main__":
    report = check(Path(sys.argv[1]), Path(__file__).resolve().parents[2])
    print("\n".join(report) if report else "The restriction tables match the data file.")
    sys.exit(1 if report else 0)
