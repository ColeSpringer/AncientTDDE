"""Embedded XS and a passive enemy: no installed files, and triggers drive player 8."""

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType

from ancienttdde.probes.arena import Arena
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

DEFINITION = ProbeDefinition(
    ProbeId.SCRIPTS_ENEMY,
    "Embedded XS and passive enemy",
    "Observe the heartbeat objective/chat and the enemy arena. Player 8 uses "
    "embedded passive AI. At 10 seconds triggers create two enemy spearmen and "
    "task them toward your guard. No AI or XS files need to be installed.",
    (
        ProbeCase(
            "scripts-enemy.heartbeat",
            "Run for 30 game-seconds with only the scenario installed.",
            "Embedded XS reports increasing heartbeat values without external-file errors.",
        ),
        ProbeCase(
            "scripts-enemy.passive",
            "Watch player 8 before and after the triggered spawn.",
            "It builds/trains nothing autonomously; triggered enemies follow the given task.",
        ),
        ProbeCase(
            "scripts-enemy.save-load",
            "Save at 20 seconds, reload and watch the counter/enemies.",
            "Heartbeat continues; initialization and the enemy spawn do not run twice.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    variable = arena.variable("xs.heartbeat")
    if variable != 0:
        raise ValueError("The heartbeat script requires trigger variable zero")
    arena.set_value(init, "xs.heartbeat", 0)
    arena.unit("enemy.guard", "spearman", 1, 30, 38)
    arena.unit("enemy.observer", "king", 1, 12, 16)
    spawn = arena.trigger("enemy.scripted.spawn", looping=False)
    condition(spawn, "timer", timer=10)
    for x in (30, 32):
        effect(
            spawn,
            "create_object",
            source_player=8,
            object_list_unit_id=arena.stock("spearman"),
            location_x=x,
            location_y=8,
        )
    effect(
        spawn,
        "task_object",
        source_player=8,
        object_list_unit_id=arena.stock("spearman"),
        location_x=30,
        location_y=38,
        action_type=ActionType.ATTACK_MOVE,
    )
    effect(
        spawn, "send_chat", source_player=1, message="Scenario spawned and tasked two P8 spearmen."
    )
