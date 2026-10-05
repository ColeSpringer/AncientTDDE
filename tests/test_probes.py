import contextlib
import io
import json
import math
from pathlib import Path

import pytest
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.provenance import hash_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe_suite(tmp_path_factory):
    from ancienttdde.probes.build import build_probes

    directory = tmp_path_factory.mktemp("mechanics-probes")
    manifest = build_probes(ROOT, directory)
    return directory, manifest


def read_probe(directory, name):
    return inspect_scenario(directory / f"{name}.aoe2scenario", include_terrain=True)


def trigger(snapshot, name):
    return next(t for t in snapshot["triggers"] if t["name"] == name)


def test_suite_builds_self_contained_solo_scenarios(probe_suite):
    directory, manifest = probe_suite
    assert {p["id"] for p in manifest["probes"]} == {
        "payments",
        "towers",
        "trade",
        "trade-gaia",
        "raiders",
        "siege",
        "scripts-enemy",
    }
    for probe in manifest["probes"]:
        snapshot = read_probe(directory, probe["id"])
        assert snapshot["scenario_version"] == "1.59"
        assert snapshot["map"]["width"] == snapshot["map"]["height"] == 64
        assert snapshot["players"][1]["human"] is True
        assert all(p["human"] is False for p in snapshot["players"][2:])
        assert snapshot["victory_condition"] == 4
        assert snapshot["dependencies"]["external_xs"] == ""
        assert snapshot["embedded_ai"][7]["name"] == "Ancient TD Passive"
        assert "disable-self" in snapshot["embedded_ai"][7]["script"]
        assert all(ai["type"] == 0 for ai in snapshot["embedded_ai"][1:])
        assert snapshot["triggers"]
        ids = [u["reference_id"] for u in snapshot["units"]]
        assert len(ids) == len(set(ids))
        assert snapshot["next_unit_id"] > max(ids)
    results = json.loads((directory / "results.json").read_text())
    assert len(results["cases"]) >= 20
    assert all(c["runs"] == [] for c in results["cases"])
    assert (directory / "instructions.md").is_file()


def test_probes_disable_all_builtin_victory_conditions_after_reload(probe_suite):
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        with contextlib.redirect_stdout(io.StringIO()):
            scenario = AoE2DEScenario.from_file(str(directory / probe["scenario"]))
        assert scenario.option_manager.victory_condition == 4
        assert not scenario.option_manager.victory_custom_conditions_required
        victory = scenario.sections["GlobalVictory"]
        assert {
            field: getattr(victory, field)
            for field in (
                "conquest_required",
                "ruins",
                "artifacts_required",
                "discovery",
                "explored_percent_of_map_required",
                "gold_required",
            )
        } == {
            "conquest_required": 0,
            "ruins": 0,
            "artifacts_required": 0,
            "discovery": 0,
            "explored_percent_of_map_required": 0,
            "gold_required": 0,
        }


@pytest.mark.parametrize(
    "field", ["conquest_required", "artifacts_required", "explored_percent_of_map_required"]
)
def test_probe_inspection_rejects_automatic_victory_conditions(probe_suite, tmp_path, field):
    from ancienttdde.probes.build import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "automatic-victory.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(directory / "payments.aoe2scenario"))
        setattr(scenario.sections["GlobalVictory"], field, 1)
        scenario.write_to_file(str(path))
    with pytest.raises(ValueError, match="victory"):
        inspect_probe(path)


def test_probes_preserve_controlled_test_settings_after_reload(probe_suite):
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        with contextlib.redirect_stdout(io.StringIO()):
            scenario = AoE2DEScenario.from_file(str(directory / probe["scenario"]))
        options = scenario.option_manager
        assert {
            "lock_teams": options.lock_teams,
            "allow_players_choose_teams": options.allow_players_choose_teams,
            "random_start_points": options.random_start_points,
            "secondary_game_modes": options.secondary_game_modes,
            "legacy_execution_order": options.legacy_execution_order,
            "all_techs": bool(scenario.sections["Options"].all_techs),
        } == {
            "lock_teams": True,
            "allow_players_choose_teams": False,
            "random_start_points": False,
            "secondary_game_modes": 0,
            "legacy_execution_order": False,
            "all_techs": False,
        }
        for player in scenario.player_manager.players[1:]:
            assert player.starting_age == 2
            assert player.population_cap == 200
            assert player.civilization.name == "BRITONS"
            assert not player.allied_victory
            assert (player.food, player.wood, player.gold, player.stone) == (0, 0, 0, 0)
            if player.player_id != 1:
                assert player.lock_personality
        assert scenario.player_manager.players[1].diplomacy[:2] == [0, 0]
        assert scenario.player_manager.players[2].diplomacy[:2] == [0, 0]
        assert scenario.player_manager.players[1].diplomacy[7] == 3
        assert scenario.player_manager.players[8].diplomacy[0] == 3


# Objects the engine counts when deciding whether a player is still in the game. Towers
# (including Outposts), walls, gates, farms and trade units are ignored, so a player who
# owns only those is defeated at game start, which satisfies conquest for every enemy.
KING = 434
BARRACKS = 12
COUNTED_FOR_SURVIVAL = {KING, 83, 93, 448, 539, 42, 331, 84, 45, 109, BARRACKS}
# Stock footprints in tiles; even sizes are centered on tile corners, odd sizes on tiles.
FOOTPRINTS = {84: 4, 109: 4, 45: 3, BARRACKS: 3, 79: 1, 234: 1, 235: 1, 236: 1, 1776: 1, 819: 1}


def test_every_active_player_survives_game_start_and_unused_slots_cannot_act(probe_suite):
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        snapshot = read_probe(directory, probe["id"])
        active = {p["player_id"] for p in snapshot["players"][1:] if p["active"]}
        surviving = {
            u["player_id"] for u in snapshot["units"] if u["unit_const"] in COUNTED_FOR_SURVIVAL
        }
        assert active <= surviving, f"{probe['id']}: defeated at start {active - surviving}"
        markers = [
            u for u in snapshot["units"] if u.get("caption_string", "").startswith("Start marker:")
        ]
        expected = {2, 3, 4, 5, 6, 7}
        if probe["id"] == "trade":
            expected.remove(2)
        if probe["id"] in {"payments", "towers", "scripts-enemy"}:
            expected.add(8)
        assert {u["player_id"] for u in markers} == expected
        # A King cannot attack, build, gather or be converted, so no enclosure is needed.
        assert all(u["unit_const"] == KING for u in markers)
        pads = [
            c["attributes"]
            for t in snapshot["triggers"]
            for c in t["conditions"]
            if c["type"] == "objects_in_area" and c["attributes"]["object_list"] == KING
        ]
        for marker in markers:
            assert not any(
                pad["area_x1"] <= marker["x"] <= pad["area_x2"] + 1
                and pad["area_y1"] <= marker["y"] <= pad["area_y2"] + 1
                for pad in pads
            ), f"{probe['id']}: marker inside a King payment region"
        initialization = trigger(snapshot, "probe.initialize")
        for protection in ("disable_unit_attackable", "disable_object_deletion"):
            protected = {
                identifier
                for e in initialization["effects"]
                if e["type"] == protection
                for identifier in e["attributes"]["selected_object_ids"]
            }
            assert {u["reference_id"] for u in markers} <= protected
        towns = [u for u in snapshot["units"] if u["unit_const"] == 109]
        assert [u["player_id"] for u in towns] == ([1] if probe["id"] == "towers" else [])


def test_probe_inspection_rejects_empty_active_slots(probe_suite, tmp_path):
    from ancienttdde.probes.build import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "empty-player.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(directory / "payments.aoe2scenario"))
        scenario.unit_manager.units[2].extend(scenario.unit_manager.units[3])
        scenario.unit_manager.units[3].clear()
        for row in scenario.trigger_manager.triggers:
            for e in row.effects:
                if e.source_player == 3 and any(i >= 0 for i in e.selected_object_ids):
                    e.source_player = 2
        scenario.write_to_file(str(path))
    with pytest.raises(ValueError, match="defeat"):
        inspect_probe(path)


def test_probe_inspection_rejects_players_kept_only_by_objects_the_engine_ignores(
    probe_suite, tmp_path
):
    from ancienttdde.probes.build import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "tower-only-player.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(directory / "payments.aoe2scenario"))
        for unit in scenario.unit_manager.units[3]:
            unit.unit_const = 79
        scenario.write_to_file(str(path))
    with pytest.raises(ValueError, match="defeat"):
        inspect_probe(path)


def test_siege_life_markers_are_counted_objects_distinct_from_payment_kings(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    request = trigger(snapshot, "siege.p8.purchase")
    life = {
        c["attributes"]["object_list"]
        for c in request["conditions"]
        if c["type"] == "own_objects" and c["attributes"]["source_player"] == 8
    }
    assert life == {BARRACKS}
    kept = [u for u in snapshot["units"] if u["player_id"] == 8 and u["unit_const"] in life]
    assert len(kept) == 1
    # Nobody receives stockpile resources in this arena, so the Barracks cannot train units.
    grants = [
        e["attributes"]
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "modify_resource"
        and e["attributes"]["tribute_list"] in {0, 1, 2, 3}
        and e["attributes"]["quantity"] > 0
    ]
    assert grants == []
    stockpiles = {(p["food"], p["wood"], p["gold"], p["stone"]) for p in snapshot["players"][1:]}
    assert stockpiles == {(0, 0, 0, 0)}


def test_setup_instructions_stay_listed_as_an_open_objective(probe_suite):
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        snapshot = read_probe(directory, probe["id"])
        pinned = trigger(snapshot, "Probe instructions")
        assert pinned["enabled"] and pinned["display_as_objective"]
        assert pinned["display_on_screen"] and pinned["short_description"]
        assert pinned["description"] and not pinned["effects"]
        [condition] = pinned["conditions"]
        assert condition["type"] == "variable_value"
        variable = condition["attributes"]["variable"]
        assert not any(
            e["type"] == "change_variable" and e["attributes"]["variable"] == variable
            for t in snapshot["triggers"]
            for e in t["effects"]
        )
    heartbeat = read_probe(directory, "scripts-enemy")
    names = {v["variable_id"]: v["name"] for v in heartbeat["variables"]}
    assert names[0] == "xs.heartbeat"


def test_buildings_are_centered_on_their_footprints(probe_suite):
    directory, manifest = probe_suite
    checked = 0
    for probe in manifest["probes"]:
        snapshot = read_probe(directory, probe["id"])
        for unit in snapshot["units"]:
            size = FOOTPRINTS.get(unit["unit_const"])
            if size is None:
                continue
            checked += 1
            offset = 0.5 if size % 2 else 0.0
            assert (unit["x"] % 1, unit["y"] % 1) == (offset, offset), (probe["id"], unit)
    assert checked > 0


def test_probe_inspection_rejects_buildings_off_their_footprint_grid(probe_suite, tmp_path):
    from ancienttdde.probes.build import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "misaligned-market.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(directory / "trade.aoe2scenario"))
        market = next(u for u in scenario.unit_manager.units[1] if u.unit_const == 84)
        market.x += 0.5
        scenario.write_to_file(str(path))
    with pytest.raises(ValueError, match="footprint"):
        inspect_probe(path)


@pytest.mark.parametrize("name,partner_owner", [("trade", 2), ("trade-gaia", 0)])
def test_trade_comparisons_have_one_unambiguous_home_per_medium(probe_suite, name, partner_owner):
    directory, _ = probe_suite
    snapshot = read_probe(directory, name)
    for building, trader in ((84, 128), (45, 17)):
        endpoints = [u for u in snapshot["units"] if u["unit_const"] == building]
        assert sorted(u["player_id"] for u in endpoints) == sorted([1, partner_owner])
        home = next(u for u in endpoints if u["player_id"] == 1)
        partner = next(u for u in endpoints if u["player_id"] == partner_owner)
        assert home["x"] < partner["x"] and home["y"] == partner["y"]
        if partner_owner == 0:
            assert partner["capture_flag"] == 0
        traders = [u for u in snapshot["units"] if u["unit_const"] == trader]
        assert len(traders) == 1 and traders[0]["player_id"] == 1
        task = next(
            e["attributes"]
            for e in trigger(snapshot, "trade.start")["effects"]
            if e["type"] == "task_object"
            and e["attributes"]["selected_object_ids"] == [traders[0]["reference_id"]]
        )
        assert task["location_object_reference"] == partner["reference_id"]
        assert task["source_player"] == 1


@pytest.mark.parametrize("name", ["trade", "trade-gaia"])
def test_endpoint_attackers_wait_for_the_protection_control_pad(probe_suite, name):
    directory, _ = probe_suite
    snapshot = read_probe(directory, name)
    attack = trigger(snapshot, "trade.attack.endpoints")
    assert any(c["type"] == "objects_in_area" for c in attack["conditions"])
    assert not any(c["type"] == "timer" for c in attack["conditions"])
    initialization = trigger(snapshot, "probe.initialize")
    attackers = [
        u for u in snapshot["units"] if u["player_id"] == 8 and u["unit_const"] in {448, 539}
    ]
    idle = {
        i
        for e in initialization["effects"]
        if e["type"] == "change_object_stance" and e["attributes"]["attack_stance"] == 3
        for i in e["attributes"]["selected_object_ids"]
    }
    assert {u["reference_id"] for u in attackers} <= idle


def test_payment_trigger_consumes_only_the_price_and_preserves_rejected_kings(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "payments")
    purchase = trigger(snapshot, "shop.purchase")
    threshold = next(
        c["attributes"] for c in purchase["conditions"] if c["type"] == "objects_in_area"
    )
    payment = next(e["attributes"] for e in purchase["effects"] if e["type"] == "remove_object")
    assert threshold["quantity"] == payment["max_units_affected"] == 3
    assert threshold["object_list"] == payment["object_list_unit_id"] == 434
    assert threshold["source_player"] == payment["source_player"] == 1
    assert [threshold[f"area_{k}"] for k in ("x1", "y1", "x2", "y2")] == [
        payment[f"area_{k}"] for k in ("x1", "y1", "x2", "y2")
    ]
    assert purchase["looping"]
    rejected = trigger(snapshot, "shop.rejected")
    assert all(e["type"] not in {"remove_object", "modify_resource"} for e in rejected["effects"])


def test_tower_bonus_targets_explicit_types_and_upgrade_controls(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "towers")
    bonus = trigger(snapshot, "tower.bonus")
    changes = [e["attributes"] for e in bonus["effects"] if e["type"] == "modify_attribute"]
    assert {e["object_list_unit_id"] for e in changes} == {79, 234, 235}
    assert all(e["armour_attack_quantity"] == 4 and e["armour_attack_class"] == 3 for e in changes)
    assert not bonus["looping"]
    technologies = {
        e["attributes"]["technology"]
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "research_technology"
    }
    assert {101, 102, 103, 140, 63} <= technologies


@pytest.mark.parametrize("name", ["trade", "trade-gaia", "raiders"])
def test_trade_endpoints_are_protected_and_traders_remain_attackable(probe_suite, name):
    directory, _ = probe_suite
    snapshot = read_probe(directory, name)
    protected = {
        i
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "disable_unit_attackable"
        for i in e["attributes"]["selected_object_ids"]
    }
    assert protected
    units = {u["reference_id"]: u for u in snapshot["units"]}
    assert {units[i]["unit_const"] for i in protected} >= {84, 45}
    assert all(units[i]["unit_const"] not in {128, 17} for i in protected)


@pytest.mark.parametrize(
    "name", ["payments", "towers", "trade", "trade-gaia", "raiders", "siege", "scripts-enemy"]
)
def test_explicit_selected_units_use_their_real_owner_filter(probe_suite, name):
    directory, _ = probe_suite
    snapshot = read_probe(directory, name)
    owners = {u["reference_id"]: u["player_id"] for u in snapshot["units"]}
    for row in snapshot["triggers"]:
        for component in row["effects"]:
            attrs = component["attributes"]
            if "source_player" in attrs and attrs.get("selected_object_ids"):
                assert {owners[i] for i in attrs["selected_object_ids"]} == {attrs["source_player"]}


def test_raider_payment_gates_accept_three_owner_kings(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "raiders")
    for name in ("land", "naval"):
        purchase = trigger(snapshot, f"raider.{name}.purchase")
        payment = next(
            c["attributes"] for c in purchase["conditions"] if c["type"] == "objects_in_area"
        )
        assert payment["quantity"] == 3 and payment["object_list"] == KING
        assert payment["source_player"] == 1
    assert any(u["unit_const"] == 1776 for u in snapshot["units"])


def variables(snapshot):
    return {v["name"]: v["variable_id"] for v in snapshot["variables"]}


def variable_conditions(row, names):
    return {
        (names[c["attributes"]["variable"]], c["attributes"]["comparison"]): c["attributes"][
            "quantity"
        ]
        for c in row["conditions"]
        if c["type"] == "variable_value"
    }


def variable_effects(row, names):
    return {
        (names[e["attributes"]["variable"]], e["attributes"]["operation"]): e["attributes"][
            "quantity"
        ]
        for e in row["effects"]
        if e["type"] == "change_variable"
    }


EQUAL, LARGER, LARGER_OR_EQUAL = 0, 2, 4
SET, ADD, SUBTRACT = 1, 2, 3


def test_siege_claims_lock_before_payment_and_cleans_both_forms(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    names = {v: k for k, v in variables(snapshot).items()}
    for player in (1, 8):
        purchase = trigger(snapshot, f"siege.p{player}.purchase")
        assert purchase["effects"][0]["type"] == "change_variable"
        owner = purchase["effects"][0]["attributes"]
        assert owner["quantity"] == player and names[owner["variable"]] == "siege.owner"
        assert variable_conditions(purchase, names)[("siege.owner", EQUAL)] == 0
        assert (
            next(e["attributes"] for e in purchase["effects"] if e["type"] == "remove_object")[
                "max_units_affected"
            ]
            == 25
        )
        for ending in ("expiry", "eliminated", "defeated"):
            cleanup = trigger(snapshot, f"siege.p{player}.{ending}")
            removed = {
                e["attributes"]["object_list_unit_id"]
                for e in cleanup["effects"]
                if e["type"] == "remove_object"
            }
            assert {42, 331} <= removed
            assert variable_effects(cleanup, names)[("siege.owner", SET)] == 0


def test_siege_stage_timing_uses_variables_instead_of_reactivated_timers(probe_suite):
    # A Timer condition keeps its elapsed count while its trigger is disabled, so a one-shot
    # stage trigger that is activated again fires at once. Stages therefore stay enabled and
    # looping, and compare a seconds variable that a one-second clock advances.
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    names = {v: k for k, v in variables(snapshot).items()}
    assert not any(
        e["type"] in {"activate_trigger", "deactivate_trigger"}
        for t in snapshot["triggers"]
        for e in t["effects"]
    )
    for row in snapshot["triggers"]:
        if row["name"].startswith("siege.") and not row["name"].endswith(".control"):
            assert row["enabled"] and row["looping"], row["name"]
        for c in row["conditions"]:
            if c["type"] == "timer":
                assert c["attributes"]["timer"] == 1 and row["looping"], row["name"]
    clock = trigger(snapshot, "siege.clock")
    assert variable_conditions(clock, names) == {("siege.phase", LARGER): 0}
    assert variable_effects(clock, names) == {("siege.elapsed", ADD): 1}
    for player in (1, 8):
        purchase = trigger(snapshot, f"siege.p{player}.purchase")
        assert variable_effects(purchase, names) == {
            ("siege.owner", SET): player,
            ("siege.phase", SET): 1,
            ("siege.elapsed", SET): 0,
        }
        warning = trigger(snapshot, f"siege.p{player}.warning")
        assert variable_conditions(warning, names) == {
            ("siege.owner", EQUAL): player,
            ("siege.phase", EQUAL): 1,
            ("siege.elapsed", LARGER_OR_EQUAL): 10,
        }
        assert variable_effects(warning, names) == {
            ("siege.phase", SET): 2,
            ("siege.elapsed", SET): 0,
        }
        expiry = trigger(snapshot, f"siege.p{player}.expiry")
        assert variable_conditions(expiry, names) == {
            ("siege.owner", EQUAL): player,
            ("siege.phase", EQUAL): 2,
            ("siege.elapsed", LARGER_OR_EQUAL): 60,
        }
        assert variable_effects(expiry, names) == {
            ("siege.owner", SET): 0,
            ("siege.phase", SET): 0,
            ("siege.shared.cooldown", SET): 60,
            (f"siege.p{player}.cooldown", SET): 120,
        }


def test_siege_cooldowns_count_down_and_gate_the_next_purchase(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    names = {v: k for k, v in variables(snapshot).items()}
    for key in ("siege.shared", "siege.p1", "siege.p8"):
        clock = trigger(snapshot, f"{key}.clock")
        assert variable_conditions(clock, names) == {(f"{key}.cooldown", LARGER): 0}
        assert variable_effects(clock, names) == {(f"{key}.cooldown", SUBTRACT): 1}
    for player in (1, 8):
        purchase = trigger(snapshot, f"siege.p{player}.purchase")
        gates = variable_conditions(purchase, names)
        assert gates[("siege.shared.cooldown", EQUAL)] == 0
        assert gates[(f"siege.p{player}.cooldown", EQUAL)] == 0
        assert (f"siege.p{8 if player == 1 else 1}.cooldown", EQUAL) not in gates


def test_siege_cleanup_waits_until_the_owner_has_no_life_marker(probe_suite):
    # Own Fewer Objects is inclusive: it holds when the player owns at most the quantity, so
    # quantity 1 would hold while the single Barracks still stands and cancel every siege.
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    for player in (1, 8):
        eliminated = trigger(snapshot, f"siege.p{player}.eliminated")
        [marker] = [
            c["attributes"] for c in eliminated["conditions"] if c["type"] != "variable_value"
        ]
        assert marker["object_list"] == BARRACKS
        assert marker["source_player"] == player
        assert marker["quantity"] == 0


def test_siege_trebuchets_spawn_deployed(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    created = [
        e["attributes"]["object_list_unit_id"]
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "create_object"
    ]
    assert created and set(created) == {42}


def test_siege_rival_kings_cannot_walk_off_their_pad(probe_suite):
    # The engine walks a computer player's Kings into any garrisonable building it owns,
    # regardless of the AI script, so P8's payment Kings are made immobile while P1's stay
    # movable for the human tester.
    directory, _ = probe_suite
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(directory / "siege.aoe2scenario"))
    initialization = scenario.sections["Triggers"].trigger_data[0]
    frozen = {
        (e.source_player, e.object_list_unit_id): e.quantity_float
        for e in initialization.effect_data
        if e.effect_type == 51 and e.object_attributes == 5
    }
    assert frozen[(8, KING)] == 0.0
    assert (1, KING) not in frozen
    assert {frozen[(p, unit)] for p in (1, 8) for unit in (42, 331)} == {0.0}


def test_siege_islets_are_isolated_and_both_positions_can_reach_rival_towers(probe_suite):
    from ancienttdde.generation.geometry import flood

    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    land = {
        (i % 64, i // 64) for i, tile in enumerate(snapshot["map"]["tiles"]) if tile[0] in {0, 4}
    }
    for player, rival in ((1, 8), (8, 1)):
        target = next(
            u for u in snapshot["units"] if u["player_id"] == rival and u["unit_const"] == 235
        )
        warning = trigger(snapshot, f"siege.p{player}.warning")
        placements = [e["attributes"] for e in warning["effects"] if e["type"] == "create_object"]
        assert len(placements) == 2
        for placement in placements:
            x, y = placement["location_x"], placement["location_y"]
            assert math.dist((x, y), (target["x"], target["y"])) <= 15
            assert flood({(x, y)}, land) == {
                (px, py) for px in range(x - 1, x + 2) for py in range(y - 1, y + 2)
            }


def test_siege_reserve_payment_can_exercise_buyer_cooldown(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    request = trigger(snapshot, "siege.p1.purchase")
    pad = next(c["attributes"] for c in request["conditions"] if c["type"] == "objects_in_area")
    spare_kings = [
        u
        for u in snapshot["units"]
        if u["player_id"] == 1
        and u["unit_const"] == 434
        and not (
            pad["area_x1"] <= u["x"] < pad["area_x2"] + 1
            and pad["area_y1"] <= u["y"] < pad["area_y2"] + 1
        )
    ]
    assert len(spare_kings) >= 25


def test_siege_visible_countdowns_use_game_seconds(probe_suite):
    directory, _ = probe_suite
    snapshot = read_probe(directory, "siege")
    displayed = [
        e["attributes"]
        for row in snapshot["triggers"]
        for e in row["effects"]
        if e["type"] == "display_timer"
    ]
    assert displayed and all(d["time_unit"] == 2 for d in displayed)
    assert {d["display_time"] for d in displayed} == {10, 60, 120}
    # The buyer cooldown is shown beside the shared cooldown instead of replacing it.
    for row in snapshot["triggers"]:
        shown = [e["attributes"] for e in row["effects"] if e["type"] == "display_timer"]
        assert len({d["timer"] for d in shown}) == len(shown), row["name"]


@pytest.mark.parametrize("tampering", ["payment", "unlocked-teams", "full-tech-tree"])
def test_validation_detects_logic_tampering_after_artifact_hash_is_updated(
    probe_suite, tmp_path, tampering
):
    import shutil

    from ancienttdde.probes.build import validate_probes

    original, _ = probe_suite
    directory = tmp_path / "probes"
    shutil.copytree(original, directory)
    path = directory / "payments.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(path))
        if tampering == "payment":
            purchase = next(
                t for t in scenario.trigger_manager.triggers if t.name == "shop.purchase"
            )
            payment = next(e for e in purchase.effects if e.effect_type == 15)
            payment.max_units_affected = 5
        elif tampering == "unlocked-teams":
            scenario.option_manager.lock_teams = False
        else:
            scenario.sections["Options"].all_techs = 1
        edited = path.with_name("edited.aoe2scenario")
        scenario.write_to_file(str(edited))
        edited.replace(path)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["artifacts"]:
        if record["path"] == path.name:
            record["sha256"] = hash_file(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="(content|reload|logic|settings)"):
        validate_probes(directory, ROOT)


def test_results_require_real_run_metadata_and_survive_rebuild(probe_suite, tmp_path):
    from ancienttdde.probes.build import build_probes
    from ancienttdde.probes.results import record_result

    directory = tmp_path / "payments"
    build_probes(ROOT, directory, only=["payments"])
    with pytest.raises(ValueError, match="(game build|tester)"):
        record_result(directory, "payments.excess", "pass", game_build="", tester="", notes="")
    record_result(
        directory,
        "payments.excess",
        "fail",
        game_build="test-fixture",
        tester="pytest",
        notes="Synthetic record; no engine run. Excess Kings were removed.",
    )
    before = (directory / "results.json").read_bytes()
    build_probes(ROOT, directory, only=["payments"])
    assert (directory / "results.json").read_bytes() == before
    cases = json.loads(before)["cases"]
    row = next(c for c in cases if c["id"] == "payments.excess")
    assert row["runs"][-1]["status"] == "fail"
    assert row["runs"][-1]["scenario_sha256"]
    assert all(c["runs"] == [] for c in cases if c["id"] != "payments.excess")


def test_probe_cli_builds_validates_and_records_a_case(tmp_path):
    directory = tmp_path / "probes"
    runner = CliRunner()
    result = runner.invoke(
        app, ["probe", "--root", str(ROOT), "--output", str(directory), "--only", "scripts-enemy"]
    )
    assert result.exit_code == 0, result.output
    assert "pending" in result.output.lower()
    result = runner.invoke(app, ["validate", "--root", str(ROOT), "--probes", str(directory)])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "probe",
            "record",
            "--suite",
            str(directory),
            "--case",
            "scripts-enemy.heartbeat",
            "--status",
            "fail",
            "--game-build",
            "test-fixture",
            "--tester",
            "pytest",
            "--notes",
            "Synthetic record; no engine run.",
        ],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("destination", ["content/probes", "src/probes", "."])
def test_probe_output_cannot_overwrite_sources(destination):
    from ancienttdde.probes.build import build_probes

    with pytest.raises(ValueError, match="source"):
        build_probes(ROOT, ROOT / destination)


def test_probe_output_rejects_ancestors():
    from ancienttdde.probes.build import build_probes

    with pytest.raises(ValueError, match="source"):
        build_probes(ROOT, ROOT.parent, only=["payments"])


def test_probe_output_rejects_resolved_source_directory_symlinks(tmp_path):
    from ancienttdde.probes.build import build_probes

    root = tmp_path / "project"
    root.mkdir()
    shared = tmp_path / "shared-docs"
    shared.mkdir()
    marker = shared / "manifest.json"
    marker.write_text('{"unrelated": true}')
    (root / "docs").symlink_to(shared, target_is_directory=True)
    with pytest.raises(ValueError, match="source"):
        build_probes(root, root / "docs", only=["payments"])
    assert marker.read_text() == '{"unrelated": true}'


def test_probe_output_does_not_replace_an_unrelated_manifest(tmp_path):
    from ancienttdde.probes.build import build_probes

    output = tmp_path / "occupied"
    output.mkdir()
    path = output / "manifest.json"
    path.write_text('{"kind": "stock-de-map"}')
    before = path.read_bytes()
    with pytest.raises(ValueError, match="(manifest|unrelated|existing)"):
        build_probes(ROOT, output, only=["payments"])
    assert path.read_bytes() == before
    assert {p.name for p in output.iterdir()} == {"manifest.json"}


def test_result_recording_rejects_a_results_symlink_outside_the_suite(probe_suite, tmp_path):
    import shutil

    from ancienttdde.probes.results import record_result

    original, _ = probe_suite
    directory = tmp_path / "suite"
    shutil.copytree(original, directory)
    shared = tmp_path / "observations.json"
    shared.write_bytes((directory / "results.json").read_bytes())
    before = shared.read_bytes()
    (directory / "results.json").unlink()
    (directory / "results.json").symlink_to(shared)
    with pytest.raises(ValueError, match="outside"):
        record_result(
            directory,
            "payments.excess",
            "fail",
            game_build="test-fixture",
            tester="pytest",
            notes="Synthetic record; no engine run.",
        )
    assert shared.read_bytes() == before


def test_unknown_probe_name_does_not_write_outputs(tmp_path):
    from ancienttdde.probes.build import build_probes

    with pytest.raises(ValueError, match="Unknown probe"):
        build_probes(ROOT, tmp_path / "output", only=["unknown"])
    assert not (tmp_path / "output").exists()
