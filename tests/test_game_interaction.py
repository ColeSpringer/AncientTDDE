"""The built game's run options, difficulty, endless growth, PvP, siege and restrictions."""

import json
import math
from functools import cache
from typing import Any

import pytest
from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.units import UnitInfo
from conftest import (
    ROOT,
    GameBuild,
    attr_int,
    attr_list,
    attr_number,
    cached_json,
    effects,
    triggers_by_name,
    variables_by_name,
)

from ancienttdde.game.config import Balance
from ancienttdde.scenario.snapshot import MapUnit, ScenarioSnapshot, TriggerRecord

PLAYERS = range(1, 8)
SET, ADD, SUBTRACT = 1, 2, 3
LESS, LARGER_OR_EQUAL = 1, 4
HIT_POINTS, SPEED, ARMOR, MAX_RANGE = 0, 5, 8, 12
TOTAL_MISSILES, MAX_TOTAL_MISSILES = 102, 107
PIERCE, ENEMY, MOVE = 3, 3, 3
OUTPOST, KING = 598, 434


def snapshot(build: GameBuild) -> ScenarioSnapshot:
    output, _ = build
    return cached_json(output / "scenario.json")


def anchors(build: GameBuild) -> dict[str, Any]:
    output, _ = build
    return cached_json(output / "map.json")["anchors"]


@cache
def balance() -> Balance:
    from ancienttdde.game.config import load_balance

    return load_balance(ROOT / "content/balance/game.json")


def conditions(trigger: TriggerRecord, kind: str) -> list[dict[str, Any]]:
    return [c["attributes"] for c in trigger["conditions"] if c["type"] == kind]


def requested(trigger: TriggerRecord, variable: int) -> int | None:
    for attributes in conditions(trigger, "variable_value"):
        if attributes["variable"] == variable:
            return attr_int(attributes, "quantity")
    return None


def sets(trigger: TriggerRecord, variable: int) -> list[tuple[int, int]]:
    return [
        (attr_int(e, "quantity"), attr_int(e, "operation"))
        for e in effects(trigger, "change_variable")
        if e["variable"] == variable
    ]


def tile(point: list[float]) -> tuple[int, int]:
    return math.floor(point[0]), math.floor(point[1])


def test_each_scheduled_wave_is_configured_once_per_difficulty(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    for number, wave in enumerate(balance().waves, 1):
        assert f"game.wave.{number}.configure" not in triggers
        for level, difficulty in enumerate(balance().difficulty.levels):
            trigger = triggers[f"game.wave.{number}.configure.{difficulty.key}"]
            assert not trigger["looping"]
            assert requested(trigger, variables["game.wave"]) == number - 1
            assert requested(trigger, variables["game.difficulty"]) == level
            [hit_points] = [
                e for e in effects(trigger, "modify_attribute") if e["object_attributes"] == 0
            ]
            assert (hit_points["source_player"], hit_points["object_list_unit_id"]) == (
                8,
                wave.object_id,
            )
            assert hit_points["quantity"] == min(32767, balance().hit_points(number - 1, level))
            armor = [
                e for e in effects(trigger, "modify_attribute") if e["object_attributes"] == ARMOR
            ]
            if wave.pierce_armor is None:
                assert not armor
            else:
                [set_armor] = armor
                assert (set_armor["operation"], set_armor["armour_attack_class"]) == (SET, PIERCE)
                assert set_armor["armour_attack_quantity"] == wave.pierce_armor
            assert sets(trigger, variables["game.configured"]) == [(number, SET)]


def test_endless_levels_set_every_template_to_its_grown_hit_points(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    endless = balance().endless
    units = [balance().waves[t].object_id for t in endless.templates]
    assert len(set(units)) == len(units)
    for level in range(1, balance().endless_levels + 1):
        for index, difficulty in enumerate(balance().difficulty.levels):
            trigger = triggers[f"game.endless.{level}.{difficulty.key}"]
            assert trigger["looping"]
            assert requested(trigger, variables["game.endless_request"]) == level
            assert requested(trigger, variables["game.difficulty"]) == index
            grown = {
                attr_int(e, "object_list_unit_id"): attr_int(e, "quantity")
                for e in effects(trigger, "modify_attribute")
            }
            assert grown == {
                unit: balance().endless_hit_points(level, position, index)
                for position, unit in enumerate(units)
            }
            assert all(
                (e["source_player"], e["object_attributes"], e["operation"]) == (8, HIT_POINTS, SET)
                for e in effects(trigger, "modify_attribute")
            )
            assert sets(trigger, variables["game.endless_request"]) == [(0, SET)]


def test_endless_armor_arrives_one_step_at_a_time(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)["game.endless.armor"]
    variables = variables_by_name(data)
    assert trigger["looping"]
    [request] = conditions(trigger, "variable_value")
    assert (request["variable"], request["quantity"], request["comparison"]) == (
        variables["game.armor_request"],
        1,
        LARGER_OR_EQUAL,
    )
    units = {balance().waves[t].object_id for t in balance().endless.templates}
    armor = effects(trigger, "modify_attribute")
    assert {attr_int(e, "object_list_unit_id") for e in armor} == units
    for change in armor:
        assert (change["source_player"], change["object_attributes"], change["operation"]) == (
            8,
            ARMOR,
            ADD,
        )
        assert change["armour_attack_class"] == PIERCE
        assert change["armour_attack_quantity"] == balance().endless.armor_step
    assert sets(trigger, variables["game.armor_request"]) == [(1, SUBTRACT)]


def test_status_shows_the_wave_number_beyond_the_schedule(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    variables = variables_by_name(data)
    status = triggers_by_name(data)["game.status"]["short_description"]
    assert status == (
        f"Wave <Variable {variables['game.display_wave']}>: "
        f"<Variable {variables['game.countdown']}> s"
    )


@pytest.mark.parametrize(
    ("objective", "reveal", "variables", "words"),
    [
        ("practice", {"game.mode": 2, "game.locked": 1}, [], "assisted"),
        ("endless", {"game.mode": 1, "game.locked": 1}, [], "Endless"),
        ("sudden", {"game.stage": 2}, ["game.drain"], "Sudden death"),
        (
            "siege",
            {"game.pvp": 1},
            ["game.siege_owner", "game.siege_left", "game.siege_cooldown"],
            "Siege",
        ),
        ("result", {"game.phase": 6}, ["game.cleared"], "Result"),
    ],
)
def test_objectives_appear_when_they_apply(
    game_build: GameBuild,
    objective: str,
    reveal: dict[str, int],
    variables: list[str],
    words: str,
) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    ids = variables_by_name(data)
    shown = triggers[f"game.objective.{objective}"]
    assert shown["display_as_objective"] and not shown["enabled"]
    assert not shown["effects"] and words in shown["short_description"]
    assert all(f"<Variable {ids[name]}>" in shown["short_description"] for name in variables)
    revealing = [
        t
        for t in data["triggers"]
        if any(e["trigger_id"] == shown["id"] for e in effects(t, "activate_trigger"))
    ]
    assert revealing
    for trigger in revealing:
        assert not trigger["looping"]
        assert {name: requested(trigger, ids[name]) for name in reveal} == reveal or (
            objective == "result" and requested(trigger, ids["game.phase"]) in (6, 8)
        )
        if objective == "siege":
            # For sale from the first wave, not from the choice that switched PvP on.
            [wave] = [
                c
                for c in conditions(trigger, "variable_value")
                if c["variable"] == ids["game.wave"]
            ]
            assert (attr_int(wave, "quantity"), attr_int(wave, "comparison")) == (
                0,
                LARGER_OR_EQUAL,
            )


def test_only_display_objectives_are_ever_activated(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    by_id = {t["id"]: t for t in data["triggers"]}
    for trigger in data["triggers"]:
        assert not effects(trigger, "deactivate_trigger")
        for activation in effects(trigger, "activate_trigger"):
            target = by_id[activation["trigger_id"]]
            assert target["display_as_objective"] and not target["effects"]


def control_units(build: GameBuild) -> dict[str, MapUnit]:
    from ancienttdde.game.controls import CONTROLS

    spots = anchors(build)
    points = [
        tile(p) for p in spots["controls.run"]["points"] + spots["controls.practice"]["points"]
    ]
    units = {
        (math.floor(u["x"]), math.floor(u["y"])): u
        for u in snapshot(build)["units"]
        if u["player_id"] == 0 and u["unit_const"] == OUTPOST
    }
    return {control.key: units[point] for control, point in zip(CONTROLS, points, strict=True)}


def test_run_controls_are_named_protected_outposts_below_the_shop(game_build: GameBuild) -> None:
    from ancienttdde.game.controls import control_captions

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    controls = control_units(game_build)
    captions = control_captions(balance())
    names = {
        attr_list(e, "selected_object_ids")[0]: e["message"]
        for e in effects(triggers["game.labels"], "change_object_name")
    }
    for key, unit in controls.items():
        assert names[unit["reference_id"]] == captions[key]
    assert captions["endless"].startswith("Run option: Endless")
    assert captions["kings"] == "Practice: 5 more Kings"
    protected = {
        ref
        for e in effects(triggers["game.initialize"], "disable_unit_attackable")
        if e["source_player"] == 0
        for ref in attr_list(e, "selected_object_ids")
    }
    assert {u["reference_id"] for u in controls.values()} <= protected


@pytest.mark.parametrize("player", PLAYERS)
def test_each_new_selection_of_a_control_is_recorded_once(
    game_build: GameBuild, player: int
) -> None:
    from ancienttdde.game.controls import CONTROLS, MODES, control_code

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    control = variables[f"lane.p{player}.control"]
    held = variables[f"lane.p{player}.control_held"]
    units = control_units(game_build)
    for item in CONTROLS:
        code = control_code(item.key)
        trigger = triggers[f"lane.p{player}.control.{item.key}"]
        assert trigger["looping"]
        assert requested(trigger, variables[f"lane.p{player}.active"]) == 1
        # Run options act until they are fixed, practice controls only in Practice runs.
        if item.group == "run":
            assert requested(trigger, variables["game.locked"]) == 0
        else:
            assert requested(trigger, variables["game.mode"]) == MODES.index("practice")
        # Holding a control selected records it once; selecting it again records it again.
        [holding] = [c for c in conditions(trigger, "variable_value") if c["variable"] == held]
        assert (attr_int(holding, "quantity"), bool(holding["inverted"])) == (code, True)
        [selected] = conditions(trigger, "object_selected_multiplayer")
        assert (selected["unit_object"], selected["source_player"]) == (
            units[item.key]["reference_id"],
            player,
        )
        assert not selected["inverted"]
        assert sets(trigger, held) == [(code, SET)] and sets(trigger, control) == [(code, SET)]
    none = triggers[f"lane.p{player}.control.none"]
    [holding] = [c for c in conditions(none, "variable_value") if c["variable"] == held]
    assert (attr_int(holding, "quantity"), attr_int(holding, "comparison")) == (
        1,
        LARGER_OR_EQUAL,
    )
    unselected = conditions(none, "object_selected_multiplayer")
    assert {c["unit_object"] for c in unselected} == {u["reference_id"] for u in units.values()}
    assert all(c["inverted"] and c["source_player"] == player for c in unselected)
    assert len(unselected) == len(CONTROLS)
    # Letting go forgets the held control; a selection waiting for the XS stays recorded.
    assert sets(none, held) == [(0, SET)] and not sets(none, control)


def removed(trigger: TriggerRecord) -> set[int]:
    return {
        ref
        for e in effects(trigger, "remove_object")
        if e["source_player"] == 0
        for ref in attr_list(e, "selected_object_ids")
    }


def test_controls_that_no_longer_apply_go_once_the_options_are_fixed(
    game_build: GameBuild,
) -> None:
    from ancienttdde.game.controls import MODES, controls

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    units = control_units(game_build)
    run = triggers["game.controls.run.remove"]
    assert not run["looping"]
    assert requested(run, variables["game.locked"]) == 1
    assert removed(run) == {units[c.key]["reference_id"] for c in controls("run")}
    practice = triggers["game.controls.practice.remove"]
    assert not practice["looping"]
    assert requested(practice, variables["game.locked"]) == 1
    [mode] = conditions(practice, "variable_value")[1:]
    assert mode["variable"] == variables["game.mode"]
    assert (attr_int(mode, "quantity"), attr_int(mode, "comparison")) == (
        MODES.index("practice"),
        LESS,
    )
    assert removed(practice) == {units[c.key]["reference_id"] for c in controls("practice")}


def test_the_original_selectors_are_gone_and_the_keeper_stands_alone(
    game_build: GameBuild,
) -> None:
    data = snapshot(game_build)
    spots = anchors(game_build)
    lives = {spots[f"lane.p{p}.life"]["reference_id"] for p in PLAYERS}
    outposts = {
        u["reference_id"] for u in data["units"] if u["unit_const"] == OUTPOST and u["player_id"]
    }
    assert outposts == lives
    [keeper] = [u for u in data["units"] if u["player_id"] == 8]
    assert keeper["unit_const"] == KING
    assert [keeper["x"], keeper["y"]] == spots["enemy.keeper"]["point"]


def test_pvp_makes_every_defense_slot_an_enemy_at_the_first_wave(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)["game.pvp"]
    variables = variables_by_name(data)
    assert not trigger["looping"]
    assert requested(trigger, variables["game.pvp"]) == 1
    wave_id = variables["game.wave"]
    [wave] = [c for c in conditions(trigger, "variable_value") if c["variable"] == wave_id]
    assert (attr_int(wave, "quantity"), attr_int(wave, "comparison")) == (0, LARGER_OR_EQUAL)
    pairs = {
        (attr_int(e, "source_player"), attr_int(e, "target_player"))
        for e in effects(trigger, "change_diplomacy")
        if e["diplomacy"] == ENEMY
    }
    assert pairs == {(p, q) for p in PLAYERS for q in PLAYERS if p != q}
    assert len(effects(trigger, "change_diplomacy")) == len(pairs)


@pytest.mark.parametrize("player", PLAYERS)
def test_bought_raiders_walk_clear_of_their_arrival(game_build: GameBuild, player: int) -> None:
    triggers = triggers_by_name(snapshot(game_build))
    spots = anchors(game_build)
    for medium, kind in (
        ("land", balance().interaction.raiders.land),
        ("naval", balance().interaction.raiders.naval),
    ):
        arrival, walk = (tile(p) for p in spots[f"lane.p{player}.raiders.{medium}"]["points"])
        [order] = effects(triggers[f"lane.p{player}.buy.{medium}_raider"], "task_object")
        assert (order["source_player"], order["object_list_unit_id"]) == (player, kind.unit_id)
        assert (order["area_x1"], order["area_y1"], order["area_x2"], order["area_y2"]) == (
            *arrival,
            *arrival,
        )
        assert (order["location_x"], order["location_y"]) == walk
    siege = triggers[f"lane.p{player}.buy.siege"]
    assert not effects(siege, "create_object") and not effects(siege, "task_object")
    [chat] = effects(siege, "send_chat")
    assert chat["message"] == "Bought Siege power-up."


def test_siege_and_endless_waves_are_counted_down(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    siege = balance().interaction.siege
    for code, seconds in (
        (1, siege.warning_seconds),
        (2, siege.active_seconds),
        (3, siege.shared_cooldown),
    ):
        trigger = triggers[f"game.siege.display.{code}"]
        assert trigger["looping"]
        assert requested(trigger, variables["game.siege_display"]) == code
        [timer] = effects(trigger, "display_timer")
        assert (timer["display_time"], timer["timer"]) == (seconds, 1) and "%d" in timer["message"]
        assert sets(trigger, variables["game.siege_display"]) == [(0, SET)]
    clear = triggers["game.wave.timer.clear"]
    assert clear["looping"] and requested(clear, variables["game.wave_display"]) == 2
    assert [attr_int(e, "timer") for e in effects(clear, "clear_timer")] == [0]
    assert sets(clear, variables["game.wave_display"]) == [(0, SET)]
    endless = triggers["game.wave.endless.warning"]
    assert requested(endless, variables["game.wave_display"]) == 1
    [timer] = effects(endless, "display_timer")
    assert (timer["display_time"], timer["timer"]) == (balance().intermission_seconds, 0)
    assert sets(endless, variables["game.wave_display"]) == [(0, SET)]


@pytest.mark.parametrize("player", PLAYERS)
def test_kings_cannot_be_attacked(game_build: GameBuild, player: int) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)[f"lane.p{player}.kings.protect"]
    assert trigger["looping"]
    assert conditions(trigger, "timer")
    assert requested(trigger, variables_by_name(data)[f"lane.p{player}.active"]) == 1
    [protect] = effects(trigger, "disable_unit_attackable")
    assert (protect["source_player"], protect["object_list_unit_id"]) == (player, KING)
    assert protect["area_x1"] == -1 and not attr_list(protect, "selected_object_ids")


def raider_ground(build: GameBuild) -> dict[str, set[tuple[int, int]]]:
    """Where land and naval raiders can stand, from the first lane's arrivals."""
    from ancienttdde.map.geometry import flood, footprint

    output, _ = build
    data = json.loads((output / "map.json").read_text())
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    width = data["map"]["width"]
    ground: dict[str, set[tuple[int, int]]] = {}
    for medium, terrain in (("land", "land_terrain"), ("naval", "water_terrain")):
        walkable = {
            (i % width, i // width)
            for i, t in enumerate(data["map"]["tiles"])
            if t[0] in config[terrain]
        } - blocked
        start = tile(data["anchors"][f"lane.p1.raiders.{medium}"]["points"][0])
        ground[medium] = flood({start}, walkable)
    return ground


def test_raiders_reach_nothing_of_a_lane_but_its_traders(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    protected = {
        ref
        for trigger in data["triggers"]
        for e in effects(trigger, "disable_unit_attackable")
        for ref in attr_list(e, "selected_object_ids")
    }
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    traders = {UnitInfo["TRADE_CART_EMPTY"].ID, UnitInfo["TRADE_COG"].ID}
    # Flags, which nobody can select or attack.
    markers = {600, 601, 602, 720, 837}
    # Land raiders strike only what touches their field; fire galleys reach 2.5 tiles.
    margins = {"land": 1.0, "naval": 3.0}
    for medium, ground in raider_ground(game_build).items():
        for unit in data["units"]:
            if not 1 <= unit["player_id"] <= 7 or unit["unit_const"] in traders | markers:
                continue
            half = sizes.get(unit["unit_const"], 0) / 2
            gap = min(
                math.hypot(
                    max(x - unit["x"] - half, unit["x"] - half - x - 1, 0),
                    max(y - unit["y"] - half, unit["y"] - half - y - 1, 0),
                )
                for x, y in ground
            )
            if gap <= margins[medium]:
                assert unit["reference_id"] in protected, (medium, unit)


# Read from DE's data: what villagers build and docks, monasteries and castles train.
DISABLED = [
    BuildingInfo[name].ID
    for name in (
        "BARRACKS",
        "ARCHERY_RANGE",
        "STABLE",
        "SIEGE_WORKSHOP",
        "CASTLE",
        "KREPOST",
        "DONJON",
        "DOCK",
        "MONASTERY",
    )
] + [
    UnitInfo[name].ID
    for name in (
        "TRANSPORT_SHIP",
        "GALLEY",
        "FIRE_GALLEY",
        "DEMOLITION_RAFT",
        "FISHING_SHIP",
        "MONK",
        "MISSIONARY",
        "TREBUCHET_PACKED",
        "PETARD",
        "LONGBOWMAN",
        "JANISSARY",
        "CONQUISTADOR",
    )
]
# The Town Center villagers place, the age forms of barracks and docks, and the forms the
# ages give houses, markets, blacksmiths and universities.
AGE_FORMS = [
    621,
    617,
    484,
    597,
    498,
    132,
    20,
    133,
    47,
    51,
    463,
    464,
    465,
    116,
    137,
    105,
    18,
    19,
    210,
]
# Villagers build towers and economy buildings; population comes from the shop.
ALLOWED = [
    BuildingInfo[name].ID
    for name in (
        "WATCH_TOWER",
        "GUARD_TOWER",
        "KEEP",
        "BOMBARD_TOWER",
        "MILL",
        "LUMBER_CAMP",
        "MINING_CAMP",
        "FARM",
        "FOLWARK",
        "PASTURE",
    )
] + [
    UnitInfo[name].ID
    for name in ("TRADE_COG", "TRADE_CART_EMPTY", "VILLAGER_MALE", "VILLAGER_FEMALE", "KING")
]
NOT_BUILT = [
    BuildingInfo[name].ID
    for name in (
        "HOUSE",
        "OUTPOST",
        "MARKET",
        "BLACKSMITH",
        "UNIVERSITY",
        "PALISADE_WALL",
        "STONE_WALL",
        "FORTIFIED_WALL",
        "GATE",
        "PALISADE_GATE",
    )
]
# Technologies that would make restricted objects available again when an age is reached:
# castles, monks, Town Centers, monasteries, fire ships, trebuchets, Kreposts and Donjons,
# and the dock upgrades, the Dragon Ship included.
DISABLED_TECHNOLOGIES = [137, 157, 187, 210, 243, 256, 695, 775, 34, 1010]
# Castle technologies and the Saxon bonus that would multiply every tower's output, and the
# technologies that would bring back the buildings villagers may not raise and the newest
# civilizations' unique units.
TOWER_MULTIPLIERS = [TechInfo[name].ID for name in ("YASAMA", "STRONGHOLD")] + [1493]
RETURNING = [148, 150, 189, 194, 281, 332, 523, 1114, 1124, 1134, 1288, 1300, 1325, 1461]
KEPT_TECHNOLOGIES = [
    TechInfo[name].ID
    for name in ("FEUDAL_AGE", "CASTLE_AGE", "IMPERIAL_AGE", "GUARD_TOWER", "KEEP", "BOMBARD_TOWER")
]


@pytest.mark.parametrize("player", PLAYERS)
def test_lane_setup_closes_ways_around_the_combat_areas(game_build: GameBuild, player: int) -> None:
    init = triggers_by_name(snapshot(game_build))[f"lane.p{player}.initialize"]
    toggles = effects(init, "enable_disable_object")
    disabled = {attr_int(e, "object_list_unit_id") for e in toggles if e["enabled"] == 0}
    assert all(e["source_player"] == player for e in toggles)
    assert set(DISABLED + AGE_FORMS + NOT_BUILT) <= disabled
    assert not set(ALLOWED) & disabled
    techs = {
        attr_int(e, "technology")
        for e in effects(init, "enable_disable_technology")
        if e["enabled"] == 0 and e["source_player"] == player
    }
    assert techs >= {
        TechInfo[name].ID
        for name in ("ATONEMENT", "REDEMPTION", "BLOCK_PRINTING", "CRENELLATIONS", "GREEK_FIRE")
    }
    assert set(DISABLED_TECHNOLOGIES + TOWER_MULTIPLIERS + RETURNING) <= techs
    assert {2705, 2569, 2101, 2703, 2565, 2417} <= disabled
    assert not set(KEPT_TECHNOLOGIES) & techs
    # The lane's age is set first, so its upgrades cannot undo the restrictions.
    kinds = [e["type"] for e in init["effects"]]
    research = max(i for i, kind in enumerate(kinds) if kind == "research_technology")
    assert research < kinds.index("enable_disable_object")
    settings = {
        (attr_int(e, "object_list_unit_id"), attr_int(e, "object_attributes")): attr_number(
            e, "quantity"
        )
        for e in effects(init, "modify_attribute")
        if e["source_player"] == player and e["operation"] == SET
    }
    castle, monk = BuildingInfo["CASTLE"].ID, UnitInfo["MONK"].ID
    trebuchets = (UnitInfo["TREBUCHET"].ID, UnitInfo["TREBUCHET_PACKED"].ID)
    assert settings[(castle, MAX_RANGE)] == 0
    assert settings[(castle, TOTAL_MISSILES)] == settings[(castle, MAX_TOTAL_MISSILES)] == 0
    assert settings[(monk, MAX_RANGE)] == 0
    assert all(settings[(unit, SPEED)] == 0 for unit in trebuchets)


@pytest.mark.parametrize("player", PLAYERS)
def test_castles_and_monks_stay_out_of_reach_whatever_is_researched(
    game_build: GameBuild, player: int
) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)[f"lane.p{player}.restrict.reach"]
    assert trigger["looping"] and conditions(trigger, "timer")
    assert requested(trigger, variables_by_name(data)[f"lane.p{player}.active"]) == 1
    castle, monk = BuildingInfo["CASTLE"].ID, UnitInfo["MONK"].ID
    settings = {
        (attr_int(e, "object_list_unit_id"), attr_int(e, "object_attributes")): attr_number(
            e, "quantity"
        )
        for e in effects(trigger, "modify_attribute")
        if e["source_player"] == player and e["operation"] == SET
    }
    # Technologies add range and arrows back; every second takes them away again.
    assert settings == {
        (castle, MAX_RANGE): 0,
        (castle, TOTAL_MISSILES): 0,
        (castle, MAX_TOTAL_MISSILES): 0,
        (monk, MAX_RANGE): 0,
    }


def test_competitive_games_rule_out_towers_that_reach_the_next_lane(
    game_build: GameBuild,
) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)["game.restrict.competitive"]
    assert not trigger["looping"]
    [rivals] = conditions(trigger, "variable_value")
    assert rivals["variable"] == variables_by_name(data)["game.participants"]
    assert (attr_int(rivals, "quantity"), attr_int(rivals, "comparison")) == (2, LARGER_OR_EQUAL)
    disabled = {
        (e["source_player"], attr_int(e, "technology"))
        for e in effects(trigger, "enable_disable_technology")
        if e["enabled"] == 0
    }
    # Eupseong and Artillery add two tiles to towers already reaching eleven.
    assert disabled == {
        (p, TechInfo[name].ID) for p in PLAYERS for name in ("EUPSEONG", "ARTILLERY")
    }


def test_lane_yurts_cannot_be_attacked(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    init = triggers_by_name(data)["game.initialize"]
    protected = {
        ref
        for e in effects(init, "disable_unit_attackable")
        for ref in attr_list(e, "selected_object_ids")
    }
    yurts = {BuildingInfo["YURT_G"].ID, BuildingInfo["YURT_H"].ID}
    placed = {
        u["reference_id"]
        for u in data["units"]
        if u["unit_const"] in yurts and 1 <= u["player_id"] <= 7
    }
    assert len(placed) == 56 and placed <= protected


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize(
    ("age", "targets"),
    [
        ("CASTLE_AGE", [10, 31, 47, 86, 132, 484]),
        ("IMPERIAL_AGE", [14, 20, 32, 51, 153, 597]),
    ],
)
def test_reaching_an_age_disables_the_buildings_it_upgrades(
    game_build: GameBuild, player: int, age: str, targets: list[int]
) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)[f"lane.p{player}.restrict.{age.lower()}"]
    assert not trigger["looping"]
    assert requested(trigger, variables_by_name(data)[f"lane.p{player}.active"]) == 1
    [state] = conditions(trigger, "technology_state")
    assert (state["technology"], state["quantity"], state["source_player"]) == (
        TechInfo[age].ID,
        3,
        player,
    )
    disabled = {
        attr_int(e, "object_list_unit_id")
        for e in effects(trigger, "enable_disable_object")
        if e["enabled"] == 0 and e["source_player"] == player
    }
    assert set(targets) <= disabled
