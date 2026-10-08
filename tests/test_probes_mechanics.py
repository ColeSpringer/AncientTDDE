"""Per-probe trigger and placement checks over the generated suite."""

import math

import pytest
from conftest import (
    BARRACKS,
    KING,
    ROOT,
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

from ancienttdde.scenario.snapshot import MapUnit, ScenarioSnapshot, TriggerRecord


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


def units_of(snapshot: ScenarioSnapshot, player: int, kind: int) -> list[MapUnit]:
    return [u for u in snapshot["units"] if u["player_id"] == player and u["unit_const"] == kind]


def test_trade_income_routes_pair_each_trader_with_a_partner_at_a_known_distance(
    probe_suite: ProbeSuite,
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "trade-income")
    triggers = triggers_by_name(snapshot)
    for building, trader in ((84, 128), (45, 17)):
        homes = units_of(snapshot, 1, building)
        partners = units_of(snapshot, 0, building)
        assert len(homes) == 2 and len(partners) == 2
        assert all(p.get("capture_flag") == 0 for p in partners)
        traders = units_of(snapshot, 1, trader)
        assert len(traders) == 2
        lengths: list[float] = []
        for unit in traders:
            task = next(
                e["attributes"]
                for e in triggers["income.start"]["effects"]
                if e["type"] == "task_object"
                and e["attributes"]["selected_object_ids"] == [unit["reference_id"]]
            )
            partner = next(
                p for p in partners if p["reference_id"] == task["location_object_reference"]
            )
            home = min(homes, key=lambda h: abs(h["y"] - partner["y"]))
            assert home["y"] == partner["y"]
            lengths.append(partner["x"] - home["x"])
        # A short and a long route, so the income's growth with distance can be read.
        assert sorted(lengths) == [20, 46]


def test_trade_income_raid_pairs_wait_for_their_pads(probe_suite: ProbeSuite) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "trade-income")
    triggers = triggers_by_name(snapshot)
    for name, raider, victim in (("cart", 546, 128), ("cog", 1103, 17)):
        [attacker] = units_of(snapshot, 1, raider)
        prey = [u for u in units_of(snapshot, 8, victim)]
        assert len(prey) == 1
        [held] = [
            e["attributes"]
            for e in triggers["probe.initialize"]["effects"]
            if e["type"] == "change_object_stance"
            and e["attributes"]["selected_object_ids"] == [prey[0]["reference_id"]]
        ]
        assert held["attack_stance"] == 3
        order = next(
            e["attributes"]
            for e in triggers[f"income.raid.{name}"]["effects"]
            if e["type"] == "task_object"
        )
        assert order["selected_object_ids"] == [attacker["reference_id"]]
        assert order["location_object_reference"] == prey[0]["reference_id"]
        assert any(
            c["type"] == "objects_in_area" for c in triggers[f"income.raid.{name}"]["conditions"]
        )
        assert (
            math.dist(
                (attacker["x"], attacker["y"]),
                (prey[0]["x"], prey[0]["y"]),
            )
            <= 8
        )


def test_tower_damage_lines_up_one_tower_of_each_kind_with_its_own_target_spot(
    probe_suite: ProbeSuite,
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "tower-damage")
    triggers = triggers_by_name(snapshot)
    # The siege Keep stands far south; the measured towers share one row.
    towers = {
        u["unit_const"]: u
        for u in snapshot["units"]
        if u["player_id"] == 1 and u["unit_const"] in (79, 234, 235, 236, 684) and u["y"] < 20
    }
    assert set(towers) == {79, 234, 235, 236, 684}
    spots: dict[str, list[tuple[int, int]]] = {}
    for enemy in ("militia", "knight", "elephant"):
        trigger = triggers[f"damage.{enemy}"]
        created = [e["attributes"] for e in trigger["effects"] if e["type"] == "create_object"]
        assert len(created) == 5 and all(e["source_player"] == 8 for e in created)
        spots[enemy] = [(attr_int(e, "location_x"), attr_int(e, "location_y")) for e in created]
        assert any(c["type"] == "objects_in_area" for c in trigger["conditions"])
        [stance] = [
            e["attributes"] for e in trigger["effects"] if e["type"] == "change_object_stance"
        ]
        assert stance["attack_stance"] == 2 and stance["source_player"] == 8
    assert spots["militia"] == spots["knight"] == spots["elephant"]
    # Each spot lies within its own tower's range and beyond every other tower's.
    ranges = {79: 8, 234: 8, 235: 8, 236: 8, 684: 13}
    for spot in spots["militia"]:
        center = (spot[0] + 0.5, spot[1] + 0.5)
        near = [
            kind
            for kind, tower in towers.items()
            if math.dist(center, (tower["x"], tower["y"])) <= ranges[kind]
        ]
        assert len(near) == 1, spot


def test_tower_damage_enemies_take_the_scheduled_hit_points(probe_suite: ProbeSuite) -> None:
    from ancienttdde.game.config import load_balance

    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "tower-damage")
    init = triggers_by_name(snapshot)["probe.initialize"]
    balance = load_balance(ROOT / "content/balance/game.json")
    normal = balance.difficulty.index("normal")
    hit_points = {
        attr_int(e["attributes"], "object_list_unit_id"): attr_number(e["attributes"], "quantity")
        for e in init["effects"]
        if e["type"] == "modify_attribute"
        and e["attributes"]["source_player"] == 8
        and e["attributes"]["object_attributes"] == 0
    }
    waves: dict[str, int] = {}
    for index, wave in enumerate(balance.waves):
        waves.setdefault(wave.unit, index)
    assert hit_points == {
        74: balance.hit_points(waves["MILITIA"], normal),
        38: balance.hit_points(waves["KNIGHT"], normal),
        239: balance.hit_points(waves["WAR_ELEPHANT"], normal),
    }


def test_tower_damage_attack_pad_raises_the_four_towers_and_the_siege_pad_places_trebuchets(
    probe_suite: ProbeSuite,
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, "tower-damage")
    triggers = triggers_by_name(snapshot)
    attack = triggers["damage.attack"]
    raised = {
        attr_int(e["attributes"], "object_list_unit_id"): attr_int(
            e["attributes"], "armour_attack_quantity"
        )
        for e in attack["effects"]
        if e["type"] == "modify_attribute"
    }
    assert raised == {79: 100, 234: 100, 235: 100, 236: 100}
    siege = triggers["damage.siege"]
    trebuchets = [e["attributes"] for e in siege["effects"] if e["type"] == "create_object"]
    assert len(trebuchets) == 2 and all(e["object_list_unit_id"] == 42 for e in trebuchets)
    [keep] = [
        u
        for u in snapshot["units"]
        if u["player_id"] == 1 and u["unit_const"] == 235 and u["y"] > 40
    ]
    for trebuchet in trebuchets:
        distance = math.dist(
            (attr_int(trebuchet, "location_x") + 0.5, attr_int(trebuchet, "location_y") + 0.5),
            (keep["x"], keep["y"]),
        )
        assert 8 < distance <= 16
    stuck = [
        e["attributes"]
        for e in triggers["probe.initialize"]["effects"]
        if e["type"] == "modify_attribute"
        and e["attributes"]["source_player"] == 8
        and e["attributes"]["object_list_unit_id"] in (42, 331)
    ]
    assert all(e["object_attributes"] == 5 and attr_number(e, "quantity") == 0 for e in stuck)
    assert len(stuck) == 2


def test_the_damage_probe_uses_the_games_accursed_tower_pierce() -> None:
    from ancienttdde.game.config import load_balance
    from ancienttdde.probes.damage import ACCURSED_PIERCE

    assert ACCURSED_PIERCE == load_balance(ROOT / "content/balance/game.json").towers.special_pierce
