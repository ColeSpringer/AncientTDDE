"""Bind named scenario variables and validated content to the shared XS engine."""

from enum import IntEnum
from pathlib import Path

from ancienttdde.engine.config import Balance, EngineLane


class State(IntEnum):
    INITIALIZATION = 0
    SETUP = 1
    PREPARATION = 2
    WAVE = 3
    BOSS = 4
    ELIMINATION = 5
    VICTORY = 6
    SUDDEN_DEATH = 7
    DEFEAT = 8


GLOBAL_VARIABLES = (
    "phase",
    "participants",
    "survivors",
    "winner",
    "wave",
    "elapsed",
    "remaining",
    "batches",
    "spawn_clock",
    "income_clock",
    "resume_phase",
    "sudden_round",
    "configured",
)
LANE_VARIABLES = ("active", "lives", "initialized", "spawn", "income", "cleanup", "count")


def variable_names() -> tuple[str, ...]:
    return tuple(f"game.{name}" for name in GLOBAL_VARIABLES) + tuple(
        f"lane.p{p}.{name}" for p in range(1, 8) for name in LANE_VARIABLES
    )


def camel(name: str) -> str:
    return "".join(word.title() for word in name.split("_"))


def table(name: str, values: list[int]) -> str:
    cases = "\n".join(f"    if (index == {i}) return ({value});" for i, value in enumerate(values))
    return f"int {name}(int index = 0) {{\n{cases}\n    return (0);\n}}\n"


def render_xs(root: Path, balance: Balance, lanes: tuple[EngineLane, ...]) -> str:
    constants: dict[str, int] = {f"v{camel(n)}": i for i, n in enumerate(GLOBAL_VARIABLES)}
    constants.update({f"f{camel(n)}": i for i, n in enumerate(LANE_VARIABLES)})
    constants.update({f"s{camel(s.name.lower())}": s.value for s in State})
    constants.update(
        cLaneBase=len(GLOBAL_VARIABLES),
        cLaneStride=len(LANE_VARIABLES),
        cLives=balance.lives,
        cSetup=balance.setup_seconds,
        cPreparation=balance.preparation_seconds,
        cIntermission=balance.intermission_seconds,
        cIncomeInterval=balance.income_interval,
        cEnemyCap=balance.max_enemies_per_lane,
        cSuddenInterval=balance.sudden_death_interval,
        cSuddenDamage=balance.sudden_death_damage,
        cWaveCount=len(balance.waves),
    )
    tables: dict[str, list[int]] = {
        "waveUnit": [w.object_id for w in balance.waves],
        "waveCount": [w.count for w in balance.waves],
        "waveBatches": [w.batches for w in balance.waves],
        "waveInterval": [w.interval for w in balance.waves],
        "waveDuration": [w.duration for w in balance.waves],
        "waveBoss": [int(w.boss) for w in balance.waves],
        "laneSpawnX": [0] + [lane.spawn_x for lane in lanes],
        "laneExitX": [0] + [lane.exit_x for lane in lanes],
        "laneY": [0] + [lane.center_y for lane in lanes],
        "laneLowY": [0] + [lane.path[1] for lane in lanes],
        "laneHighY": [0] + [lane.path[3] for lane in lanes],
        "enemyType": sorted({w.object_id for w in balance.waves}),
    }
    constants["cEnemyTypes"] = len(tables["enemyType"])
    return (
        "\n".join(f"const int {name} = {value};" for name, value in constants.items())
        + "\n"
        + "\n".join(table(name, values) for name, values in tables.items())
        + (root / "src/ancienttdde/engine/runtime.xs").read_text(encoding="utf-8")
    )
