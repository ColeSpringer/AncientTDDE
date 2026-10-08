"""Worker: construct one isolated stock-DE arena for a probe definition."""

import sys
from collections.abc import Callable
from pathlib import Path

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.common.data import asset_text
from ancienttdde.common.worker import capture_stdout_for_errors
from ancienttdde.probes import (
    damage,
    income,
    payments,
    raiders,
    scripts_enemy,
    siege,
    towers,
    trade,
)
from ancienttdde.probes.arena import Arena
from ancienttdde.probes.catalog import TEST_SETTINGS, select_probes
from ancienttdde.probes.models import ProbeDefinition, ProbeId
from ancienttdde.scenario.settings import (
    disable_automatic_victory,
    embed_passive_ai,
    lock_lobby_options,
    reset_player,
)
from ancienttdde.scenario.triggers import TriggerHandle, effect
from ancienttdde.scenario.xs import check_xs, xs_checker


def initialize(arena: Arena) -> TriggerHandle:
    scenario = arena.scenario
    scenario.player_manager.active_players = 8
    for player in scenario.player_manager.players[1:]:
        human = player.player_id == 1
        reset_player(
            player,
            human=human,
            civilization="BRITONS",
            lock_personality=not human,
            starting_age=StartingAge.DARK_AGE,
        )
        diplomacy: list[int] = [DiplomacyState.ENEMY] * 16
        diplomacy[player.player_id - 1] = DiplomacyState.ALLY
        if player.player_id in (1, 2):
            diplomacy[:2] = [DiplomacyState.ALLY, DiplomacyState.ALLY]
        player.diplomacy = diplomacy
        player.initial_player_view_x = 16
        player.initial_player_view_y = 16
    disable_automatic_victory(scenario)
    lock_lobby_options(scenario)
    scenario.xs_manager.script_name = ""
    init = arena.trigger("probe.initialize", looping=False)
    arena.resources(init, 0)
    effect(
        init,
        "modify_resource",
        source_player=1,
        tribute_list=Attribute.POPULATION_HEADROOM,
        quantity=200,
        operation=Operation.SET,
    )
    effect(
        init,
        "change_diplomacy",
        source_player=1,
        target_player=8,
        diplomacy=DiplomacyState.ENEMY,
        mutual_diplomacy=True,
    )
    effect(
        init,
        "change_diplomacy",
        source_player=1,
        target_player=2,
        diplomacy=DiplomacyState.ALLY,
        mutual_diplomacy=True,
    )
    return init


def populate_unused_players(arena: Arena, init: TriggerHandle) -> None:
    # A King counts as a unit for the engine's defeat check but cannot attack, build, gather
    # or be converted, so one protected King keeps a slot in the game without side effects.
    occupied = set(arena.owners().values())
    markers: list[int] = []
    for player in arena.scenario.player_manager.players[1:]:
        if player.active and player.player_id not in occupied:
            markers.append(
                arena.unit(
                    f"probe.player.{player.player_id}",
                    "king",
                    player.player_id,
                    61,
                    2 * player.player_id,
                    f"Start marker: P{player.player_id}; keeps this slot in the game",
                )
            )
    arena.protect(init, markers)


BUILDERS: dict[ProbeId, Callable[[Arena, TriggerHandle], None]] = {
    ProbeId.PAYMENTS: payments.build,
    ProbeId.TOWERS: towers.build,
    ProbeId.TRADE: trade.build,
    ProbeId.TRADE_GAIA: trade.build_gaia,
    ProbeId.RAIDERS: raiders.build,
    ProbeId.SIEGE: siege.build,
    ProbeId.SCRIPTS_ENEMY: scripts_enemy.build,
    ProbeId.TRADE_INCOME: income.build,
    ProbeId.TOWER_DAMAGE: damage.build,
}


def construct_probe(root: Path, definition: ProbeDefinition, destination: Path) -> None:
    scenario = AoE2DEScenario.from_file(str(root / "content/maps/format-seed.aoe2scenario"))
    if scenario.scenario_version != "1.59":
        raise ValueError("Probe format seed must use scenario version 1.59")
    if (
        scenario.unit_manager.get_all_units()
        or scenario.trigger_manager.triggers
        or (scenario.trigger_manager.variables)
    ):
        raise ValueError("Probe format seed must be empty")
    if (
        scenario.xs_manager.script_name
        or scenario.sections["Files"].script_file_content
        or (scenario.sections["Files"].ai_files)
    ):
        raise ValueError("Probe format seed must contain no gameplay scripts or AI files")
    arena = Arena(scenario)
    init = initialize(arena)
    if definition.id == ProbeId.RAIDERS:
        scenario.xs_manager.add_script(xs_string=asset_text("probe-raider-purchases.xs"))
    BUILDERS[definition.id](arena, init)
    populate_unused_players(arena, init)
    embed_passive_ai(scenario, range(1, 8))
    if definition.id == ProbeId.SCRIPTS_ENEMY:
        scenario.xs_manager.add_script(xs_string=asset_text("probe-heartbeat.xs"))
    arena.objective(definition.title, definition.setup)
    scenario.sections["FileHeader"].creator_name = "Ancient TD DE mechanic probes"
    scenario.message_manager.instructions = (
        definition.title
        + "\r"
        + TEST_SETTINGS
        + "\r"
        + definition.setup
        + "\r"
        + "\r".join(f"{c.id}: {c.action} Expected: {c.expected}" for c in definition.cases)
    )
    scenario.message_manager.history = "Based on Ancient TD v5.3 by DRAX6869 / DRAX."
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
        scenario.write_to_file(str(destination))
    # Validate the serialized script calls too, rather than trusting only the source file.
    check_xs(AoE2DEScenario.from_file(str(destination)))


if __name__ == "__main__":
    with capture_stdout_for_errors():
        if "--check-xs" in sys.argv[4:]:
            check_xs(AoE2DEScenario.from_file(sys.argv[3]))
        else:
            construct_probe(Path(sys.argv[1]), select_probes([sys.argv[2]])[0], Path(sys.argv[3]))
