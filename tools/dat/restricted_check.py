"""Check the restriction tables against the installed DE data.

Usage: uv run python tools/dat/restricted_check.py <empires2_x2_p1.dat>

Prints the units a lane could still train at the buildings it keeps (its market, dock,
monasteries, mills, camps and a bought castle) that restricted.OBJECTS does not list, the
technologies that enable or upgrade into a listed object or turn villagers into something
else that restricted.TECHNOLOGIES does not list, and the age forms restricted.AGE_UPGRADES
misses. An empty report means the tables match the data file.
"""

import sys
from pathlib import Path

from genieutils.datfile import DatFile

from ancienttdde.game.restricted import AGE_UPGRADES, OBJECTS, TECHNOLOGIES

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


def check(dat_path: Path) -> list[str]:
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
    return lines


if __name__ == "__main__":
    report = check(Path(sys.argv[1]))
    print("\n".join(report) if report else "The restriction tables match the data file.")
    sys.exit(1 if report else 0)
