"""The built game's run options, difficulty, endless growth, PvP, siege and restrictions."""

import json
import math
from functools import cache
from typing import Any

import pytest
from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.units import UnitInfo
from conftest import (
    ROOT,
    WATCH_TOWER,
    GameBuild,
    attr_int,
    attr_list,
    attr_number,
    cached_json,
    effects,
    triggers_by_name,
    variables_by_name,
)
from conftest import tiles as map_tiles

from ancienttdde.game.config import Balance
from ancienttdde.scenario.snapshot import MapUnit, ScenarioSnapshot, TriggerRecord

PLAYERS = range(1, 8)
SET, ADD, SUBTRACT = 1, 2, 3
EQUAL, LESS, LARGER_OR_EQUAL = 0, 1, 4
HIT_POINTS, SPEED, ARMOR, MAX_RANGE = 0, 5, 8, 12
TOTAL_MISSILES, MAX_TOTAL_MISSILES = 102, 107
PIERCE, ENEMY, MOVE = 3, 3, 3
OUTPOST, KING = 598, 434
TREBUCHET, PACKED_TREBUCHET = 42, 331
TOWERS = (79, 234, 235, 236)


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


def test_the_xs_alone_configures_the_waves_enemies(game_build: GameBuild) -> None:
    """The enemy may hold any player number, so no native trigger sets a wave unit's hit points
    or armor for a fixed player: the XS sets them on the enemy's definitions (see the wave and
    endless cases in test_game_script.py). The only native changes to the enemy's units hold
    slot 8's keeper King in place and keep its keeper tower from firing, whatever its type."""
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    assert not [
        name for name in triggers if ".configure" in name or name.startswith("game.endless.")
    ]
    assert "game.configured" not in variables and "game.endless_request" not in variables
    assert "game.enemy" in variables
    wave_units = {wave.object_id for wave in balance().waves}
    for trigger in data["triggers"]:
        for change in effects(trigger, "modify_attribute"):
            unit = attr_int(change, "object_list_unit_id")
            assert unit not in wave_units, trigger["name"]
            if change["source_player"] == 8:
                assert trigger["name"] == "game.initialize" and unit in (KING, *TOWERS)


def test_status_shows_the_wave_number_beyond_the_schedule(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    variables = variables_by_name(data)
    triggers = triggers_by_name(data)
    wave = f"<Variable {variables['game.display_wave']}>"
    countdown = f"<Variable {variables['game.countdown']}>"
    assert triggers["game.status.next"]["short_description"] == (
        f"Wave {wave} arrives in {countdown} s"
    )
    # Reads right at 0 too, through each wave's tail and after the finale.
    assert triggers["game.status.spawning"]["short_description"] == (
        f"Wave {wave}: {countdown} s of spawning left"
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
        ("stopped", {"game.phase": 7}, [], "stopped"),
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
        for activation in effects(trigger, "activate_trigger"):
            target = by_id[activation["trigger_id"]]
            assert target["display_as_objective"] and not target["effects"]
        # Only a cleared lane's cleanup, the hiding of finished objectives and the wave
        # triggers switching the status line end triggers.
        if effects(trigger, "deactivate_trigger"):
            name = trigger["name"]
            assert name.startswith(("game.hide.", "game.wave.")) or name.endswith(".cleanup"), name


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


# The condition each kind of lobby holds on the human-lane count the script publishes.
LOBBY_CONDITIONS = {"solo": (1, EQUAL), "competitive": (2, LARGER_OR_EQUAL)}


def lobby_condition(trigger: TriggerRecord, variables: dict[str, int]) -> tuple[int, int]:
    [held] = [
        c
        for c in conditions(trigger, "variable_value")
        if c["variable"] == variables["game.participants"]
    ]
    return attr_int(held, "quantity"), attr_int(held, "comparison")


def test_each_control_applies_to_its_lobby() -> None:
    from ancienttdde.game.controls import CONTROLS, LOBBIES, controls, ruled_out

    standard, _, _, pvp_on = CONTROLS[:4]
    assert standard.applies("solo") and standard.applies("competitive")
    assert pvp_on.applies("competitive") and not pvp_on.applies("solo")
    assert [c.key for c in controls("run", "solo")] == ["standard", "endless", "practice"]
    assert [c.key for c in controls("run", "competitive")] == ["standard", "pvp_on"]
    assert controls("practice", "solo") == controls("practice")
    assert controls("practice", "competitive") == ()
    assert [c.key for c in ruled_out("solo")] == ["pvp_on"]
    assert [c.key for c in ruled_out("competitive")] == [
        "endless",
        "practice",
        "next_wave",
        "kings",
        "resources",
        "lives",
    ]
    for lobby in LOBBIES:
        kept = controls("run", lobby) + controls("practice", lobby)
        assert sorted(kept + ruled_out(lobby), key=CONTROLS.index) == list(CONTROLS)


def test_controls_the_lobby_rules_out_leave_the_row_at_once(game_build: GameBuild) -> None:
    """The script counts the human lanes in the first second; a solo run then loses PvP on,
    a competitive game the solo modes and the practice controls."""
    from ancienttdde.game.controls import LOBBIES, ruled_out

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    units = control_units(game_build)
    for lobby in LOBBIES:
        trim = triggers[f"game.controls.{lobby}.trim"]
        assert not trim["looping"] and trim["enabled"]
        assert len(conditions(trim, "variable_value")) == 1
        assert lobby_condition(trim, variables) == LOBBY_CONDITIONS[lobby]
        assert removed(trim) == {units[c.key]["reference_id"] for c in ruled_out(lobby)}
        assert len(trim["effects"]) == 1


def test_controls_that_no_longer_apply_go_once_the_options_are_fixed(
    game_build: GameBuild,
) -> None:
    """Each lobby removes only the controls it kept, so no Remove Object effect selects an
    object that is already gone."""
    from ancienttdde.game.controls import LOBBIES, MODES, controls

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    units = control_units(game_build)
    for lobby in LOBBIES:
        run = triggers[f"game.controls.run.remove.{lobby}"]
        assert not run["looping"]
        assert requested(run, variables["game.locked"]) == 1
        assert lobby_condition(run, variables) == LOBBY_CONDITIONS[lobby]
        assert removed(run) == {units[c.key]["reference_id"] for c in controls("run", lobby)}
    practice = triggers["game.controls.practice.remove"]
    assert not practice["looping"]
    assert requested(practice, variables["game.locked"]) == 1
    assert lobby_condition(practice, variables) == LOBBY_CONDITIONS["solo"]
    [mode] = [
        c for c in conditions(practice, "variable_value") if c["variable"] == variables["game.mode"]
    ]
    assert (attr_int(mode, "quantity"), attr_int(mode, "comparison")) == (
        MODES.index("practice"),
        LESS,
    )
    assert removed(practice) == {units[c.key]["reference_id"] for c in controls("practice")}
    # Over a run, each lobby removes every control once.
    every = sorted(u["reference_id"] for u in units.values())
    removals = {
        "solo": (
            "game.controls.solo.trim",
            "game.controls.run.remove.solo",
            "game.controls.practice.remove",
        ),
        "competitive": ("game.controls.competitive.trim", "game.controls.run.remove.competitive"),
    }
    for keys in removals.values():
        assert sorted(ref for key in keys for ref in removed(triggers[key])) == every


def test_option_lines_name_the_lobby_controls_and_leave_once_locked(
    game_build: GameBuild,
) -> None:
    """A line appears once the script has counted the human lanes and never completes. DE
    keeps a fired objective listed, struck through; a deactivated one leaves the box."""
    from ancienttdde.game.controls import MODES, control_labels

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    labels = control_labels(balance())

    def listing(*keys: str) -> str:
        return ", ".join(labels[key] for key in keys)

    lines = {
        "game.objective.options.solo": (
            "solo",
            "Run options below the shop, left to right: "
            + listing("standard", "endless", "practice"),
            "game.hide.options",
        ),
        "game.objective.options.competitive": (
            "competitive",
            "Run options below the shop, left to right: " + listing("standard", "pvp_on"),
            "game.hide.options",
        ),
        "game.objective.practice_controls": (
            "solo",
            "Practice controls (Practice runs) to their right: "
            + listing("next_wave", "kings", "resources", "lives"),
            "game.hide.practice_controls",
        ),
    }
    for key, (lobby, text, hider_key) in lines.items():
        line = triggers[key]
        assert line["display_as_objective"] and not line["enabled"] and not line["effects"]
        assert line["short_description"] == text
        assert requested(line, variables["game.phase"]) == -1
        # Revealed only while the options are open: a reveal after the lock would stick.
        reveal = triggers[key.replace("objective", "reveal")]
        assert not reveal["looping"] and len(reveal["conditions"]) == 2
        assert lobby_condition(reveal, variables) == LOBBY_CONDITIONS[lobby]
        assert requested(reveal, variables["game.locked"]) == 0
        assert [e["trigger_id"] for e in effects(reveal, "activate_trigger")] == [line["id"]]
        hider = triggers[hider_key]
        assert not hider["looping"]
        assert requested(hider, variables["game.locked"]) == 1
        assert line["id"] in [e["trigger_id"] for e in effects(hider, "deactivate_trigger")]
    assert triggers["game.objective.options.solo"]["description"] == (
        "The first human lane selects one; Standard is taken after 60 game seconds."
    )
    assert triggers["game.objective.options.competitive"]["description"] == (
        "The first human lane selects one; Standard with PvP off is taken after 60 game seconds."
    )
    assert len(effects(triggers["game.hide.options"], "deactivate_trigger")) == 2
    assert len(conditions(triggers["game.hide.options"], "variable_value")) == 1
    [_, mode] = conditions(triggers["game.hide.practice_controls"], "variable_value")
    assert mode["variable"] == variables["game.mode"]
    assert (attr_int(mode, "quantity"), attr_int(mode, "inverted")) == (MODES.index("practice"), 1)


def test_the_original_selectors_are_gone_and_the_keeper_holds_its_islet(
    game_build: GameBuild,
) -> None:
    """The enemy's islet holds its King and a tower, both unattackable and undeletable from
    the start: a lobby's Standard victory counts an opponent destroyed once it has no
    villagers, soldiers, ships or buildings, and a King is none of them."""
    data = snapshot(game_build)
    spots = anchors(game_build)
    lives = {spots[f"lane.p{p}.life"]["reference_id"] for p in PLAYERS}
    outposts = {
        u["reference_id"] for u in data["units"] if u["unit_const"] == OUTPOST and u["player_id"]
    }
    assert outposts == lives
    held_by_enemy = [u for u in data["units"] if u["player_id"] == 8]
    assert sorted(u["unit_const"] for u in held_by_enemy) == sorted([KING, WATCH_TOWER])
    enemy = {u["unit_const"]: u for u in held_by_enemy}
    assert [enemy[KING]["x"], enemy[KING]["y"]] == spots["enemy.keeper"]["point"]
    assert [enemy[WATCH_TOWER]["x"], enemy[WATCH_TOWER]["y"]] == spots["enemy.keeper.tower"][
        "point"
    ]

    def footprint(unit: MapUnit) -> tuple[int, int]:
        return int(unit["x"] // 1), int(unit["y"] // 1)

    assert [u for u in data["units"] if footprint(u) == footprint(enemy[WATCH_TOWER])] == [
        enemy[WATCH_TOWER]
    ]
    init = triggers_by_name(data)["game.initialize"]
    held = sorted(u["reference_id"] for u in enemy.values())
    for protection in ("disable_unit_attackable", "disable_object_deletion"):
        protected = [e for e in effects(init, protection) if e["source_player"] == 8]
        assert [sorted(e["selected_object_ids"]) for e in protected] == [held]
    # The King cannot walk off its tile and the tower cannot shoot whatever type a free upgrade
    # makes it: a human in slot 8 is an enemy of a lane slot's computer by the scenario's
    # diplomacy, and the cleared lanes' Kings stand beside it.
    frozen = [
        (e["object_list_unit_id"], e["object_attributes"], e["quantity"], e["operation"])
        for e in effects(init, "modify_attribute")
        if e["source_player"] == 8
    ]
    assert sorted(frozen) == sorted(
        [(KING, ObjectAttribute.MOVEMENT_SPEED, 0, SET)]
        + [(tower, ObjectAttribute.MAXIMUM_RANGE, 0, SET) for tower in TOWERS]
    )


def test_pvp_makes_every_two_playing_lanes_enemies_at_the_first_wave(game_build: GameBuild) -> None:
    """One trigger per ordered pair of lanes, each gated on both lanes playing: the enemy's own
    cleared lane and closed lanes stay out of it."""
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    assert "game.pvp" not in triggers
    pairs = {(p, q) for p in PLAYERS for q in PLAYERS if p != q}
    for source, target in pairs:
        trigger = triggers[f"game.pvp.p{source}.p{target}"]
        assert not trigger["looping"]
        assert requested(trigger, variables["game.pvp"]) == 1
        assert requested(trigger, variables[f"lane.p{source}.active"]) == 1
        assert requested(trigger, variables[f"lane.p{target}.active"]) == 1
        wave_id = variables["game.wave"]
        [wave] = [c for c in conditions(trigger, "variable_value") if c["variable"] == wave_id]
        assert (attr_int(wave, "quantity"), attr_int(wave, "comparison")) == (0, LARGER_OR_EQUAL)
        [change] = effects(trigger, "change_diplomacy")
        assert (change["source_player"], change["target_player"], change["diplomacy"]) == (
            source,
            target,
            ENEMY,
        )
    assert len([name for name in triggers if name.startswith("game.pvp.p")]) == len(pairs)


# Each PvP pad's gate: the open column of its Hay Stack box, opposite its King.
GATES = {
    "naval_raider": {(166, y) for y in range(20, 23)},
    "siege": {(166, y) for y in range(24, 34)},
    "land_raider": {(166, y) for y in range(36, 39)},
}
HAY_STACK = 857
# The beach-side Hay Stack line every PvP box ends at.
BEACH = 171


def test_pvp_pads_stay_sealed_with_hay_until_pvp_is_switched_on(game_build: GameBuild) -> None:
    output, _ = game_build
    data = snapshot(game_build)
    variables = variables_by_name(data)
    gates = {spot for spots in GATES.values() for spot in spots}
    hay: dict[tuple[int, int], MapUnit] = {}
    for u in data["units"]:
        spot = (math.floor(u["x"]), math.floor(u["y"]))
        if spot in gates:
            assert (u["unit_const"], u["player_id"]) == (HAY_STACK, 0), spot
            assert spot not in hay, spot
            hay[spot] = u
    assert hay.keys() == gates
    # The build adds the gates; the map has none.
    original = {u["reference_id"] for u in cached_json(output / "map.json")["units"]}
    assert not original & {u["reference_id"] for u in hay.values()}
    opened = triggers_by_name(data)["game.pvp.open"]
    assert not opened["looping"] and opened["enabled"]
    assert [
        (attr_int(c, "variable"), attr_int(c, "quantity"))
        for c in conditions(opened, "variable_value")
    ] == [(variables["game.pvp"], 1)]
    [removal] = effects(opened, "remove_object")
    assert removal["source_player"] == 0
    assert sorted(attr_list(removal, "selected_object_ids")) == sorted(
        hay[tile]["reference_id"] for tile in gates
    )
    assert len(opened["effects"]) == 1


def test_opening_the_pvp_pads_needs_their_gates() -> None:
    """A Remove Object effect that selects nothing would clear every Gaia object, so the build
    refuses to open pads it never gated."""
    from conftest import new_scenario

    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.interaction import open_pvp_pads
    from ancienttdde.game.triggers import Game

    spots = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    families = [name for name, _ in balance().towers.families]
    shop = load_shop(ROOT / "content/balance/shop.json", spots, families)
    with pytest.raises(ValueError, match="No PvP pad gates to open"):
        open_pvp_pads(Game(new_scenario()), shop)


def test_the_gates_cut_only_the_pvp_pads_off_from_the_kings(game_build: GameBuild) -> None:
    """Every lane's Kings reach every pad from their rally point, except the PvP pads while
    their gates stand."""
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.map.geometry import cells, flood, footprint

    data = snapshot(game_build)
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {row["stock_id"]: row.get("blocking_size", 0) for row in config["objects"]}
    width = data["map"]["width"]
    land = {
        (i % width, i // width)
        for i, t in enumerate(map_tiles(data))
        if t[0] in config["land_terrain"]
    }
    [removal] = effects(triggers_by_name(data)["game.pvp.open"], "remove_object")
    gates = set(attr_list(removal, "selected_object_ids"))
    spots = anchors(game_build)
    rallies = {tile(spots[f"lane.p{p}.kings"]["points"][1]) for p in PLAYERS}

    def reached(units: list[MapUnit]) -> set[tuple[int, int]]:
        blocked = {c for u in units for c in footprint(u, sizes.get(u["unit_const"], 0))}
        return flood(rallies, land - blocked)

    gated = reached(data["units"])
    opened = reached([u for u in data["units"] if u["reference_id"] not in gates])
    families = [name for name, _ in balance().towers.families]
    shop = load_shop(ROOT / "content/balance/shop.json", spots, families)
    for purchase in shop.purchases:
        pad = cells(purchase.pad_region)
        assert bool(pad & gated) == (purchase.key not in GATES), purchase.key
        assert pad & opened, purchase.key


def test_pvp_pad_gates_close_their_hay_stack_boxes(game_build: GameBuild) -> None:
    """Each gate stands in its pad's first column, where its box's Hay Stack rows begin: the
    rows run unbroken from there to the beach-side line, nothing of the box lies beyond, and
    the three boxes share that column."""
    data = snapshot(game_build)
    hay = {
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in data["units"]
        if u["unit_const"] == HAY_STACK
    }
    spots = anchors(game_build)
    assert len({x for gate in GATES.values() for x, _ in gate}) == 1
    for key, gate in GATES.items():
        x1, y1, _, y2 = spots[f"shop.{key}"]["region"]
        assert gate == {(x1, y) for y in range(y1, y2 + 1)}, key
        for row in (y1 - 1, y2 + 1):
            assert {(x, row) for x in range(x1, BEACH + 1)} <= hay, (key, row)
            assert (x1 - 1, row) not in hay, (key, row)


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
    assert chat["message"] == "Bought Siege power-up for 20 Kings."


def test_siege_and_endless_waves_are_counted_down(game_build: GameBuild) -> None:
    from ancienttdde.game.waves import CHOICE_TIMER, SIEGE_TIMER, WAVE_TIMER

    # Reset Timer keeps a running timer's text, so each countdown that may overlap another
    # has its own timer.
    assert len({WAVE_TIMER, SIEGE_TIMER, CHOICE_TIMER}) == 3
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
        assert (timer["display_time"], timer["timer"]) == (seconds, SIEGE_TIMER)
        assert "%d" in timer["message"]
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


@pytest.mark.parametrize("player", PLAYERS)
def test_siege_trebuchets_cannot_be_attacked(game_build: GameBuild, player: int) -> None:
    """The towers of both lanes beside the islets reach the trebuchets, so while a lane holds
    the siege its trebuchets, packed or not, are made unattackable on every pass of the
    triggers, with no timer: the pass that creates them protects them."""
    data = snapshot(game_build)
    variables = variables_by_name(data)
    trigger = triggers_by_name(data)[f"lane.p{player}.siege.protect"]
    assert trigger["looping"]
    assert not conditions(trigger, "timer")
    assert requested(trigger, variables["game.siege_owner"]) == player
    # Not during the warning, when no trebuchet exists yet.
    from ancienttdde.game.script import SIEGE_PHASE_ACTIVE

    assert requested(trigger, variables["game.siege_phase"]) == SIEGE_PHASE_ACTIVE
    assert len(trigger["conditions"]) == 2
    protected = effects(trigger, "disable_unit_attackable")
    assert sorted((e["source_player"], e["object_list_unit_id"]) for e in protected) == sorted(
        [(player, TREBUCHET), (player, PACKED_TREBUCHET)]
    )
    for protect in protected:
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
] + [UnitInfo[name].ID for name in ("VILLAGER_MALE", "VILLAGER_FEMALE", "KING")]
# Markets and docks still train traders; DE itself refuses them at the population limit.
TRAINED = [UnitInfo[name].ID for name in ("TRADE_COG", "TRADE_CART_EMPTY")]
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
    assert not set(TRAINED) & disabled
    assert not set(ALLOWED) & disabled
    techs = {
        attr_int(e, "technology")
        for e in effects(init, "enable_disable_technology")
        if e["enabled"] == 0 and e["source_player"] == player
    }
    assert techs >= {
        TechInfo[name].ID
        for name in (
            "ATONEMENT",
            "REDEMPTION",
            "BLOCK_PRINTING",
            "CRENELLATIONS",
            "GREEK_FIRE",
            "SIEGE_ENGINEERS",
        )
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
    # Enough to outlast the volley a tower row can land before the protection reaches them,
    # and under the 16-bit ceiling after the Celts' Furor Celtica multiplies it by 1.4.
    from ancienttdde.game.config import MAX_HIT_POINTS
    from ancienttdde.game.restrictions import TREBUCHET_HIT_POINTS

    assert all(settings[(unit, HIT_POINTS)] == TREBUCHET_HIT_POINTS for unit in trebuchets)
    assert 11000 < TREBUCHET_HIT_POINTS and TREBUCHET_HIT_POINTS * 1.4 <= MAX_HIT_POINTS


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
