"""Per-probe trigger and placement checks over the generated suite."""

import math

import pytest
from conftest import (
    BARRACKS,
    KING,
    ProbeSuite,
    attr_int,
    attr_list,
    attr_number,
    load_scenario,
    probe_snapshot,
    tiles,
    triggers_by_name,
    variables_by_name,
)

from ancienttdde.scenario.snapshot import ScenarioSnapshot, TriggerRecord


def test_siege_life_markers_are_counted_objects_distinct_from_payment_kings(
    probe_suite: ProbeSuite,
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    request = triggers_by_name(snapshot)["siege.p8.purchase"]
    life = {
        attr_int(c["attributes"], "object_list")
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
        and attr_number(e["attributes"], "quantity") > 0
    ]
    assert grants == []
    stockpiles = {(p["food"], p["wood"], p["gold"], p["stone"]) for p in snapshot["players"][1:]}
    assert stockpiles == {(0, 0, 0, 0)}


@pytest.mark.parametrize("name,partner_owner", [("trade", 2), ("trade-gaia", 0)])
def test_trade_comparisons_have_one_unambiguous_home_per_medium(
    probe_suite: ProbeSuite, name: str, partner_owner: int
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, name)
    for building, trader in ((84, 128), (45, 17)):
        endpoints = [u for u in snapshot["units"] if u["unit_const"] == building]
        assert sorted(u["player_id"] for u in endpoints) == sorted([1, partner_owner])
        home = next(u for u in endpoints if u["player_id"] == 1)
        partner = next(u for u in endpoints if u["player_id"] == partner_owner)
        assert home["x"] < partner["x"] and home["y"] == partner["y"]
        if partner_owner == 0:
            assert partner.get("capture_flag") == 0
        traders = [u for u in snapshot["units"] if u["unit_const"] == trader]
        assert len(traders) == 1 and traders[0]["player_id"] == 1
        task = next(
            e["attributes"]
            for e in triggers_by_name(snapshot)["trade.start"]["effects"]
            if e["type"] == "task_object"
            and e["attributes"]["selected_object_ids"] == [traders[0]["reference_id"]]
        )
        assert task["location_object_reference"] == partner["reference_id"]
        assert task["source_player"] == 1


@pytest.mark.parametrize("name", ["trade", "trade-gaia"])
def test_endpoint_attackers_wait_for_the_protection_control_pad(
    probe_suite: ProbeSuite, name: str
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, name)
    attack = triggers_by_name(snapshot)["trade.attack.endpoints"]
    assert any(c["type"] == "objects_in_area" for c in attack["conditions"])
    assert not any(c["type"] == "timer" for c in attack["conditions"])
    initialization = triggers_by_name(snapshot)["probe.initialize"]
    attackers = [
        u for u in snapshot["units"] if u["player_id"] == 8 and u["unit_const"] in {448, 539}
    ]
    idle = {
        i
        for e in initialization["effects"]
        if e["type"] == "change_object_stance" and e["attributes"]["attack_stance"] == 3
        for i in attr_list(e["attributes"], "selected_object_ids")
    }
    assert {u["reference_id"] for u in attackers} <= idle


def test_payment_trigger_consumes_only_the_price_and_preserves_rejected_kings(
    probe_suite: ProbeSuite,
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "payments")
    purchase = triggers_by_name(snapshot)["shop.purchase"]
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
    rejected = triggers_by_name(snapshot)["shop.rejected"]
    assert all(e["type"] not in {"remove_object", "modify_resource"} for e in rejected["effects"])


def test_tower_bonus_targets_explicit_types_and_upgrade_controls(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "towers")
    bonus = triggers_by_name(snapshot)["tower.bonus"]
    changes = [e["attributes"] for e in bonus["effects"] if e["type"] == "modify_attribute"]
    assert {attr_int(e, "object_list_unit_id") for e in changes} == {79, 234, 235}
    assert all(e["armour_attack_quantity"] == 4 and e["armour_attack_class"] == 3 for e in changes)
    assert not bonus["looping"]
    technologies = {
        attr_int(e["attributes"], "technology")
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "research_technology"
    }
    assert {101, 102, 103, 140, 63} <= technologies


@pytest.mark.parametrize("name", ["trade", "trade-gaia", "raiders"])
def test_trade_endpoints_are_protected_and_traders_remain_attackable(
    probe_suite: ProbeSuite, name: str
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, name)
    protected = {
        i
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "disable_unit_attackable"
        for i in attr_list(e["attributes"], "selected_object_ids")
    }
    assert protected
    units = {u["reference_id"]: u for u in snapshot["units"]}
    assert {units[i]["unit_const"] for i in protected} >= {84, 45}
    assert all(units[i]["unit_const"] not in {128, 17} for i in protected)


def test_raider_payment_gates_accept_three_owner_kings(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "raiders")
    for name in ("land", "naval"):
        purchase = triggers_by_name(snapshot)[f"raider.{name}.purchase"]
        payment = next(
            c["attributes"] for c in purchase["conditions"] if c["type"] == "objects_in_area"
        )
        assert payment["quantity"] == 3 and payment["object_list"] == KING
        assert payment["source_player"] == 1
    assert any(u["unit_const"] == 1776 for u in snapshot["units"])


def variable_names(scenario: ScenarioSnapshot) -> dict[int, str]:
    return {identifier: name for name, identifier in variables_by_name(scenario).items()}


def variable_conditions(row: TriggerRecord, names: dict[int, str]) -> dict[tuple[str, int], int]:
    return {
        (names[attr_int(attributes, "variable")], attr_int(attributes, "comparison")): attr_int(
            attributes, "quantity"
        )
        for c in row["conditions"]
        if c["type"] == "variable_value"
        for attributes in (c["attributes"],)
    }


def variable_effects(row: TriggerRecord, names: dict[int, str]) -> dict[tuple[str, int], int]:
    return {
        (names[attr_int(attributes, "variable")], attr_int(attributes, "operation")): attr_int(
            attributes, "quantity"
        )
        for e in row["effects"]
        if e["type"] == "change_variable"
        for attributes in (e["attributes"],)
    }


EQUAL, LARGER, LARGER_OR_EQUAL = 0, 2, 4


SET, ADD, SUBTRACT = 1, 2, 3


def test_siege_claims_lock_before_payment_and_cleans_both_forms(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    names = variable_names(snapshot)
    for player in (1, 8):
        purchase = triggers_by_name(snapshot)[f"siege.p{player}.purchase"]
        assert purchase["effects"][0]["type"] == "change_variable"
        owner = purchase["effects"][0]["attributes"]
        assert owner["quantity"] == player and names[attr_int(owner, "variable")] == "siege.owner"
        assert variable_conditions(purchase, names)[("siege.owner", EQUAL)] == 0
        assert (
            next(e["attributes"] for e in purchase["effects"] if e["type"] == "remove_object")[
                "max_units_affected"
            ]
            == 25
        )
        for ending in ("expiry", "eliminated", "defeated"):
            cleanup = triggers_by_name(snapshot)[f"siege.p{player}.{ending}"]
            removed = {
                attr_int(e["attributes"], "object_list_unit_id")
                for e in cleanup["effects"]
                if e["type"] == "remove_object"
            }
            assert {42, 331} <= removed
            assert variable_effects(cleanup, names)[("siege.owner", SET)] == 0


def test_siege_stage_timing_uses_variables_instead_of_reactivated_timers(
    probe_suite: ProbeSuite,
) -> None:
    # A Timer condition keeps its elapsed count while its trigger is disabled, so a one-shot
    # stage trigger that is activated again fires at once. Stages therefore stay enabled and
    # looping, and compare a seconds variable that a one-second clock advances.
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    names = variable_names(snapshot)
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
    clock = triggers_by_name(snapshot)["siege.clock"]
    assert variable_conditions(clock, names) == {("siege.phase", LARGER): 0}
    assert variable_effects(clock, names) == {("siege.elapsed", ADD): 1}
    for player in (1, 8):
        purchase = triggers_by_name(snapshot)[f"siege.p{player}.purchase"]
        assert variable_effects(purchase, names) == {
            ("siege.owner", SET): player,
            ("siege.phase", SET): 1,
            ("siege.elapsed", SET): 0,
        }
        warning = triggers_by_name(snapshot)[f"siege.p{player}.warning"]
        assert variable_conditions(warning, names) == {
            ("siege.owner", EQUAL): player,
            ("siege.phase", EQUAL): 1,
            ("siege.elapsed", LARGER_OR_EQUAL): 10,
        }
        assert variable_effects(warning, names) == {
            ("siege.phase", SET): 2,
            ("siege.elapsed", SET): 0,
        }
        expiry = triggers_by_name(snapshot)[f"siege.p{player}.expiry"]
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


def test_siege_cooldowns_count_down_and_gate_the_next_purchase(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    names = variable_names(snapshot)
    for key in ("siege.shared", "siege.p1", "siege.p8"):
        clock = triggers_by_name(snapshot)[f"{key}.clock"]
        assert variable_conditions(clock, names) == {(f"{key}.cooldown", LARGER): 0}
        assert variable_effects(clock, names) == {(f"{key}.cooldown", SUBTRACT): 1}
    for player in (1, 8):
        purchase = triggers_by_name(snapshot)[f"siege.p{player}.purchase"]
        gates = variable_conditions(purchase, names)
        assert gates[("siege.shared.cooldown", EQUAL)] == 0
        assert gates[(f"siege.p{player}.cooldown", EQUAL)] == 0
        assert (f"siege.p{8 if player == 1 else 1}.cooldown", EQUAL) not in gates


def test_siege_cleanup_waits_until_the_owner_has_no_life_marker(probe_suite: ProbeSuite) -> None:
    # Own Fewer Objects is inclusive: it holds when the player owns at most the quantity, so
    # quantity 1 would hold while the single Barracks still stands and cancel every siege.
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    for player in (1, 8):
        eliminated = triggers_by_name(snapshot)[f"siege.p{player}.eliminated"]
        [marker] = [
            c["attributes"] for c in eliminated["conditions"] if c["type"] != "variable_value"
        ]
        assert marker["object_list"] == BARRACKS
        assert marker["source_player"] == player
        assert marker["quantity"] == 0


def test_siege_trebuchets_spawn_deployed(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    created = [
        e["attributes"]["object_list_unit_id"]
        for t in snapshot["triggers"]
        for e in t["effects"]
        if e["type"] == "create_object"
    ]
    assert created and set(created) == {42}


def test_siege_rival_kings_cannot_walk_off_their_pad(probe_suite: ProbeSuite) -> None:
    # The engine walks a computer player's Kings into any garrisonable building it owns,
    # regardless of the AI script, so P8's payment Kings are made immobile while P1's stay
    # movable for the human tester.
    directory, _ = probe_suite
    scenario = load_scenario(directory / "siege.aoe2scenario")
    initialization = scenario.sections["Triggers"].trigger_data[0]
    frozen = {
        (e.source_player, e.object_list_unit_id): e.quantity_float
        for e in initialization.effect_data
        if e.effect_type == 51 and e.object_attributes == 5
    }
    assert frozen[(8, KING)] == 0.0
    assert (1, KING) not in frozen
    assert {frozen[(p, unit)] for p in (1, 8) for unit in (42, 331)} == {0.0}


def test_siege_islets_are_isolated_and_both_positions_can_reach_rival_towers(
    probe_suite: ProbeSuite,
) -> None:
    from ancienttdde.map.geometry import flood

    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    land = {(i % 64, i // 64) for i, tile in enumerate(tiles(snapshot)) if tile[0] in {0, 4}}
    for player, rival in ((1, 8), (8, 1)):
        target = next(
            u for u in snapshot["units"] if u["player_id"] == rival and u["unit_const"] == 235
        )
        warning = triggers_by_name(snapshot)[f"siege.p{player}.warning"]
        placements = [e["attributes"] for e in warning["effects"] if e["type"] == "create_object"]
        assert len(placements) == 2
        for placement in placements:
            x, y = attr_int(placement, "location_x"), attr_int(placement, "location_y")
            assert math.dist((x, y), (target["x"], target["y"])) <= 15
            assert flood({(x, y)}, land) == {
                (px, py) for px in range(x - 1, x + 2) for py in range(y - 1, y + 2)
            }


def test_siege_reserve_payment_can_exercise_buyer_cooldown(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    request = triggers_by_name(snapshot)["siege.p1.purchase"]
    pad = next(c["attributes"] for c in request["conditions"] if c["type"] == "objects_in_area")
    spare_kings = [
        u
        for u in snapshot["units"]
        if u["player_id"] == 1
        and u["unit_const"] == 434
        and not (
            attr_int(pad, "area_x1") <= u["x"] < attr_int(pad, "area_x2") + 1
            and attr_int(pad, "area_y1") <= u["y"] < attr_int(pad, "area_y2") + 1
        )
    ]
    assert len(spare_kings) >= 25


def test_siege_visible_countdowns_use_game_seconds(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "siege")
    displayed = [
        e["attributes"]
        for row in snapshot["triggers"]
        for e in row["effects"]
        if e["type"] == "display_timer"
    ]
    assert displayed and all(d["time_unit"] == 2 for d in displayed)
    assert {attr_int(d, "display_time") for d in displayed} == {10, 60, 120}
    # The buyer cooldown is shown beside the shared cooldown instead of replacing it.
    for row in snapshot["triggers"]:
        shown = [e["attributes"] for e in row["effects"] if e["type"] == "display_timer"]
        assert len({attr_int(d, "timer") for d in shown}) == len(shown), row["name"]
