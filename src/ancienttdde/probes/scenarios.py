"""Construct isolated stock-DE arenas with explicit native object operations."""

import contextlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.trigger_lists.secondary_game_mode import SecondaryGameMode
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit
from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.probes.catalog import TEST_SETTINGS, select_probes
from ancienttdde.probes.models import AiMode, ProbeDefinition, ProbeId
from ancienttdde.probes.native import Arena, Region, TriggerHandle, condition, effect, stock
from ancienttdde.probes.xs import check_xs, xs_checker


def initialize(arena: Arena) -> TriggerHandle:
    scenario = arena.scenario
    scenario.player_manager.active_players = 8
    for player in scenario.player_manager.players[1:]:
        player.human = player.player_id == 1
        player.civilization = "BRITONS"
        player.lock_civ = False
        player.lock_personality = not player.human
        player.starting_age = StartingAge.DARK_AGE
        player.population_cap = 200
        player.allied_victory = False
        player.food = player.wood = player.gold = player.stone = 0
        diplomacy: list[int] = [DiplomacyState.ENEMY] * 16
        diplomacy[player.player_id - 1] = DiplomacyState.ALLY
        if player.player_id in (1, 2):
            diplomacy[:2] = [DiplomacyState.ALLY, DiplomacyState.ALLY]
        player.diplomacy = diplomacy
        player.initial_player_view_x = 16
        player.initial_player_view_y = 16
    scenario.option_manager.victory_condition = VictoryCondition.CUSTOM
    scenario.option_manager.victory_custom_conditions_required = False
    victory = scenario.sections["GlobalVictory"]
    victory.conquest_required = 0
    victory.ruins = 0
    victory.artifacts_required = 0
    victory.discovery = 0
    victory.explored_percent_of_map_required = 0
    victory.gold_required = 0
    scenario.option_manager.lock_teams = True
    scenario.option_manager.allow_players_choose_teams = False
    scenario.option_manager.random_start_points = False
    scenario.option_manager.secondary_game_modes = SecondaryGameMode.NONE
    scenario.option_manager.legacy_execution_order = False
    scenario.sections["Options"].all_techs = 0
    scenario.xs_manager.script_name = ""
    init = arena.trigger("probe.initialize")
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
    occupied = set(arena.owners.values())
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


def payments(arena: Arena, init: TriggerHandle) -> None:
    pad = arena.pad("shop.open", 10, 10, "3 Kings = 100 gold")
    closed = arena.pad("shop.closed", 22, 10, "Closed: payment is never consumed")
    arena.kings("payment", 1, 18, 8, 20)
    purchase = arena.trigger("shop.purchase", looping=True)
    condition(purchase, "timer", timer=1)
    arena.on_pad(purchase, pad, price=3)
    arena.pay(purchase, pad, 1, 3)
    effect(
        purchase,
        "modify_resource",
        source_player=1,
        tribute_list=Attribute.GOLD_STORAGE,
        quantity=100,
        operation=Operation.ADD,
    )
    effect(purchase, "send_chat", source_player=1, message="Purchase: 3 Kings consumed; +100 gold.")
    rejected = arena.trigger("shop.rejected", looping=True)
    condition(rejected, "timer", timer=5)
    arena.on_pad(rejected, closed)
    effect(rejected, "send_chat", source_player=1, message="Closed shop: no Kings consumed.")


def towers(arena: Arena, init: TriggerHandle) -> None:
    arena.resources(init, 10000)
    arena.research(init, "FEUDAL_AGE")
    arena.unit("tower.original", "watch-tower", 1, 32, 18)
    arena.unit("tower.comparison", "bombard-tower", 1, 38, 18)
    arena.unit("tower.scout", "scout", 1, 40, 22)
    arena.unit("tower.builder", "villager", 1, 28, 22)
    arena.unit("tower.builder.2", "villager", 1, 29, 22)
    arena.unit("tower.town", "town-center", 1, 24, 28)
    arena.unit("tower.control", "king", 1, 8, 16)
    bonus_pad = arena.pad("tower.bonus.pad", 8, 8, "+4 arrow tower pierce attack")
    castle_pad = arena.pad("tower.castle.pad", 16, 8, "Castle Age + Guard Tower")
    imperial_pad = arena.pad("tower.imperial.pad", 24, 8, "Imperial Age + Keep")
    bonus = arena.trigger("tower.bonus")
    arena.on_pad(bonus, bonus_pad)
    # Modify type definitions so future construction and upgrades are part of the experiment.
    for kind in ("watch-tower", "guard-tower", "keep"):
        effect(
            bonus,
            "modify_attribute",
            source_player=1,
            object_list_unit_id=stock(kind),
            object_attributes=ObjectAttribute.ATTACK,
            operation=Operation.ADD,
            armour_attack_class=3,
            armour_attack_quantity=4,
        )
    effect(
        bonus,
        "send_chat",
        source_player=1,
        message="Arrow tower definitions: +4 attack applied once.",
    )
    castle = arena.trigger("tower.castle")
    arena.on_pad(castle, castle_pad)
    arena.research(castle, "CASTLE_AGE")
    arena.research(castle, "GUARD_TOWER")
    imperial = arena.trigger("tower.imperial")
    arena.on_pad(imperial, imperial_pad)
    arena.research(imperial, "CASTLE_AGE")
    arena.research(imperial, "GUARD_TOWER")
    arena.research(imperial, "IMPERIAL_AGE")
    arena.research(imperial, "KEEP")


def trade_routes(arena: Arena, init: TriggerHandle, partner_player: Literal[0, 2]) -> None:
    arena.terrain((0, 30, 63, 63), 1)
    endpoints: list[int] = []
    start = arena.trigger("trade.start")
    condition(start, "timer", timer=2)
    partner_name = "Gaia" if partner_player == 0 else "P2"
    for kind, trader, y in (("market", "cart", 12), ("dock", "cog", 44)):
        key = f"trade.{trader}"
        endpoints.append(arena.unit(f"{key}.home", kind, 1, 8, y, f"P1 home {kind}"))
        partner = arena.unit(
            f"{key}.partner",
            kind,
            partner_player,
            54,
            y,
            f"{partner_name} partner {kind}",
            capture_flag=CaptureFlag.NEVER,
        )
        endpoints.append(partner)
        unit = arena.unit(f"{key}.trader", trader, 1, 14, y)
        effect(
            start,
            "task_object",
            source_player=1,
            selected_object_ids=[unit],
            location_object_reference=partner,
            action_type=ActionType.DEFAULT,
        )
    arena.protect(init, endpoints)
    pad = arena.pad("trade.attack.pad", 8, 4, "Start endpoint attack test")
    arena.unit("trade.control", "king", 1, 8, 22, "Endpoint attack control")
    attack = arena.trigger("trade.attack.endpoints")
    arena.on_pad(attack, pad)
    for kind, y, target in (("scout", 12, "trade.cart.home"), ("galley", 44, "trade.cog.home")):
        attacker = arena.unit(f"trade.attack.{kind}", kind, 8, 18, y)
        effect(
            init,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[attacker],
            attack_stance=AttackStance.NO_ATTACK_STANCE,
        )
        effect(
            attack,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[attacker],
            attack_stance=AttackStance.STAND_GROUND,
        )
        effect(
            attack,
            "task_object",
            source_player=8,
            selected_object_ids=[attacker],
            location_object_reference=arena.registry.resolve("object", target),
        )
    effect(attack, "send_chat", source_player=1, message="Endpoint attack test started.")


def trade(arena: Arena, init: TriggerHandle) -> None:
    trade_routes(arena, init, 2)


def trade_gaia(arena: Arena, init: TriggerHandle) -> None:
    trade_routes(arena, init, 0)


def raiders(arena: Arena, init: TriggerHandle) -> None:
    arena.resources(init, 10000)
    arena.research(init, "FEUDAL_AGE")
    arena.terrain((0, 34, 63, 60), 1)
    # A closed stock-blocker ring keeps land combat separate from the shop controls.
    perimeter = {(x, y) for x in range(4, 60) for y in (4, 23)} | {
        (x, y) for y in range(5, 23) for x in (4, 59)
    }
    for x, y in sorted(perimeter):
        arena.unit(f"raider.boundary.{x}.{y}", "blocker", 0, x, y)
    endpoints: list[int] = []
    start = arena.trigger("raider.trade.start")
    condition(start, "timer", timer=2)
    for kind, trader, y in (("market", "cart", 10), ("dock", "cog", 44)):
        home = arena.unit(f"raider.{trader}.home", kind, 1, 8, y)
        partner = arena.unit(f"raider.{trader}.partner", kind, 8, 54, y)
        endpoints.extend([home, partner])
        for player, x, target in ((1, 14, partner), (8, 48, home)):
            unit = arena.unit(f"raider.{trader}.p{player}", trader, player, x, y)
            effect(
                start,
                "task_object",
                source_player=player,
                selected_object_ids=[unit],
                location_object_reference=target,
            )
    arena.protect(init, endpoints)
    arena.kings("raider.payment", 1, 24, 30, 27)
    for name, kind, pad_x, spawn_y in (("land", "scout", 8, 16), ("naval", "galley", 18, 50)):
        pad = arena.pad(f"raider.{name}.pad", pad_x, 27, f"{name}: 3 Kings; living cap 2")
        enemy = arena.unit(f"raider.{name}.enemy", kind, 8, 42, spawn_y)
        effect(
            init,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[enemy],
            attack_stance=AttackStance.STAND_GROUND,
        )
        purchase = arena.trigger(f"raider.{name}.purchase", looping=True)
        condition(purchase, "timer", timer=1)
        arena.on_pad(purchase, pad, price=3)
        x1, y1, x2, y2 = pad
        effect(
            purchase,
            "script_call",
            message=(
                f"void ancientBuy{name.title()}Raider() {{ "
                f"ancientPurchaseRaider(1, {stock(kind)}, {stock('king')}, 2, "
                f'{x1}, {y1}, {x2 + 1}, {y2 + 1}, 18.5, {spawn_y + 0.5}, "{name}"); }}'
            ),
        )


SIEGE_WARNING, SIEGE_ACTIVE = 1, 2
SIEGE_WARNING_SECONDS, SIEGE_ACTIVE_SECONDS = 10, 60
SIEGE_SHARED_COOLDOWN, SIEGE_BUYER_COOLDOWN = 60, 120


def countdown(trigger: TriggerHandle, seconds: int, message: str, slot: int) -> None:
    effect(
        trigger,
        "display_timer",
        display_time=seconds,
        time_unit=TimeUnit.SECONDS,
        message=message,
        reset_timer=1,
        timer=slot,
    )


def siege(arena: Arena, init: TriggerHandle) -> None:
    arena.terrain((0, 19, 63, 25), 1)
    # Every stage trigger stays enabled and looping and is gated by these variables. The
    # phase and elapsed seconds describe the current owner's stage; the cooldowns hold the
    # remaining seconds and are counted down by one-second clocks.
    for key in (
        "siege.owner",
        "siege.phase",
        "siege.elapsed",
        "siege.shared.cooldown",
        "siege.p1.cooldown",
        "siege.p8.cooldown",
    ):
        arena.variable(key)
        arena.set_value(init, key, 0)
    arena.clock("siege.clock", "siege.elapsed", Operation.ADD, while_positive="siege.phase")
    for key in ("siege.shared", "siege.p1", "siege.p8"):
        arena.clock(
            f"{key}.clock", f"{key}.cooldown", Operation.SUBTRACT, while_positive=f"{key}.cooldown"
        )
    pads: dict[int, Region] = {}
    positions = {1: (42, 46), 8: (18, 22)}
    lives: list[int] = []
    for player, x in ((1, 8), (8, 48)):
        lives.append(arena.unit(f"siege.p{player}.life", "life", player, x, 28))
        arena.unit(f"siege.p{player}.tower", "keep", player, x + 6, 29)
        pads[player] = arena.pad(f"siege.p{player}.pad", x, 8, f"P{player}: 25 Kings per siege")
        arena.kings(f"siege.p{player}.payment", player, 30 if player == 1 else 25, x, 8)
        for islet_x in positions[player]:
            arena.terrain((islet_x - 1, 22, islet_x + 1, 24), 0)
        for kind in ("trebuchet", "packed-trebuchet"):
            effect(
                init,
                "modify_attribute",
                source_player=player,
                object_list_unit_id=stock(kind),
                object_attributes=ObjectAttribute.MOVEMENT_SPEED,
                quantity=0,
                operation=Operation.SET,
            )
    # The engine walks a computer player's Kings into any garrisonable building it owns (here
    # the Keep) regardless of the AI script, which would carry P8's payment off its pad.
    effect(
        init,
        "modify_attribute",
        source_player=8,
        object_list_unit_id=stock("king"),
        object_attributes=ObjectAttribute.MOVEMENT_SPEED,
        quantity=0,
        operation=Operation.SET,
    )
    arena.protect(init, lives)
    arena.unit("siege.control", "king", 1, 28, 8)
    arena.kings("siege.p1.reserve", 1, 30, 28, 1)
    for player, x in ((1, 8), (8, 16)):
        pad = arena.pad(f"siege.p{player}.eliminate.pad", x, 14, f"Remove P{player} life marker")
        control = arena.trigger(f"siege.p{player}.eliminate.control")
        arena.on_pad(control, pad)
        effect(
            control,
            "remove_object",
            source_player=player,
            selected_object_ids=[arena.registry.resolve("object", f"siege.p{player}.life")],
        )
    for player in (1, 8):
        key = f"siege.p{player}"
        rival = 8 if player == 1 else 1
        purchase = arena.trigger(f"{key}.purchase", looping=True)
        condition(purchase, "timer", timer=1)
        arena.on_pad(purchase, pads[player], player=player, price=25)
        arena.value(purchase, "siege.owner", 0)
        arena.value(purchase, "siege.shared.cooldown", 0)
        arena.value(purchase, f"{key}.cooldown", 0)
        for alive in (player, rival):
            condition(
                purchase, "own_objects", source_player=alive, object_list=stock("life"), quantity=1
            )
        # Claim the shared lock before payment so a later request sees an occupied transaction.
        arena.set_value(purchase, "siege.owner", player)
        arena.set_value(purchase, "siege.phase", SIEGE_WARNING)
        arena.set_value(purchase, "siege.elapsed", 0)
        arena.pay(purchase, pads[player], player, 25)
        effect(
            purchase,
            "send_chat",
            source_player=1,
            message=f"P{player} owns siege. 10-second warning; other requests retain Kings.",
        )
        countdown(purchase, SIEGE_WARNING_SECONDS, f"P{player} siege warning: %d", 0)
        warning = arena.trigger(f"{key}.warning", looping=True)
        arena.value(warning, "siege.owner", player)
        arena.value(warning, "siege.phase", SIEGE_WARNING)
        arena.value(warning, "siege.elapsed", SIEGE_WARNING_SECONDS, Comparison.LARGER_OR_EQUAL)
        for x in positions[player]:
            # Unit 42 is the deployed Trebuchet, ready to fire; 331 is the packed form.
            effect(
                warning,
                "create_object",
                source_player=player,
                object_list_unit_id=stock("trebuchet"),
                location_x=x,
                location_y=23,
            )
        arena.set_value(warning, "siege.phase", SIEGE_ACTIVE)
        arena.set_value(warning, "siege.elapsed", 0)
        countdown(warning, SIEGE_ACTIVE_SECONDS, f"P{player} siege active: %d", 0)
        for ending in ("expiry", "eliminated", "defeated"):
            cleanup = arena.trigger(f"{key}.{ending}", looping=True)
            arena.value(cleanup, "siege.owner", player)
            if ending == "expiry":
                arena.value(cleanup, "siege.phase", SIEGE_ACTIVE)
                arena.value(
                    cleanup, "siege.elapsed", SIEGE_ACTIVE_SECONDS, Comparison.LARGER_OR_EQUAL
                )
            elif ending == "eliminated":
                arena.at_most(cleanup, player, "life", 0)
            else:
                condition(cleanup, "player_defeated", source_player=player)
            for kind in ("trebuchet", "packed-trebuchet"):
                effect(
                    cleanup, "remove_object", source_player=player, object_list_unit_id=stock(kind)
                )
            arena.set_value(cleanup, "siege.owner", 0)
            arena.set_value(cleanup, "siege.phase", 0)
            arena.set_value(cleanup, "siege.shared.cooldown", SIEGE_SHARED_COOLDOWN)
            arena.set_value(cleanup, f"{key}.cooldown", SIEGE_BUYER_COOLDOWN)
            effect(
                cleanup,
                "send_chat",
                source_player=1,
                message=f"P{player} siege removed; shared cooldown 60s, buyer cooldown 120s.",
            )
            countdown(cleanup, SIEGE_SHARED_COOLDOWN, "Shared siege cooldown: %d", 0)
            countdown(cleanup, SIEGE_BUYER_COOLDOWN, f"P{player} buyer cooldown: %d", 1)


def scripts_enemy(arena: Arena, init: TriggerHandle) -> None:
    variable = arena.variable("xs.heartbeat")
    if variable != 0:
        raise ValueError("The heartbeat script requires trigger variable zero")
    arena.set_value(init, "xs.heartbeat", 0)
    arena.unit("enemy.guard", "spearman", 1, 30, 38)
    arena.unit("enemy.observer", "king", 1, 12, 16)
    spawn = arena.trigger("enemy.scripted.spawn")
    condition(spawn, "timer", timer=10)
    for x in (30, 32):
        effect(
            spawn,
            "create_object",
            source_player=8,
            object_list_unit_id=stock("spearman"),
            location_x=x,
            location_y=8,
        )
    effect(
        spawn,
        "task_object",
        source_player=8,
        object_list_unit_id=stock("spearman"),
        location_x=30,
        location_y=38,
        action_type=ActionType.ATTACK_MOVE,
    )
    effect(
        spawn, "send_chat", source_player=1, message="Scenario spawned and tasked two P8 spearmen."
    )


BUILDERS: dict[ProbeId, Callable[[Arena, TriggerHandle], None]] = {
    ProbeId.PAYMENTS: payments,
    ProbeId.TOWERS: towers,
    ProbeId.TRADE: trade,
    ProbeId.TRADE_GAIA: trade_gaia,
    ProbeId.RAIDERS: raiders,
    ProbeId.SIEGE: siege,
    ProbeId.SCRIPTS_ENEMY: scripts_enemy,
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
        scenario.xs_manager.add_script(
            xs_string=(root / "src/ancienttdde/xs/probe-raider-purchases.xs").read_text(
                encoding="utf-8"
            )
        )
    BUILDERS[definition.id](arena, init)
    populate_unused_players(arena, init)
    passive = (root / "src/ancienttdde/ai/passive.per").read_text(encoding="utf-8")
    player_data = scenario.sections["PlayerDataTwo"]
    for slot in range(1, 8):
        player_data.ai_names[slot] = "Ancient TD Passive"
        player_data.ai_files[slot].ai_per_file_text = passive
        player_data.ai_type[slot] = AiMode.CUSTOM
    if definition.id == ProbeId.SCRIPTS_ENEMY:
        scenario.xs_manager.add_script(
            xs_string=(root / "src/ancienttdde/xs/probe-heartbeat.xs").read_text(encoding="utf-8")
        )
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
    scenario.message_manager.history = "Ancient Tower Defense original map by DRAX6869 / DRAX."
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
        scenario.write_to_file(str(destination))
    # Validate the serialized script calls too, rather than trusting only the source file.
    check_xs(AoE2DEScenario.from_file(str(destination)))


if __name__ == "__main__":
    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        if "--check-xs" in sys.argv[4:]:
            check_xs(AoE2DEScenario.from_file(sys.argv[3]))
        else:
            construct_probe(Path(sys.argv[1]), select_probes([sys.argv[2]])[0], Path(sys.argv[3]))
