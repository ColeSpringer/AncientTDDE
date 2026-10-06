"""Named triggers and variables, and the native operations the game and probes share."""

import inspect
from pathlib import Path

import pytest
from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from conftest import BARRACKS, KING, attr_int, attr_list, new_scenario, save_scenario

from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.triggers import Builder


@pytest.fixture
def builder() -> Builder:
    return Builder(new_scenario("1.59"))


def test_triggers_and_variables_are_registered_by_name(builder: Builder) -> None:
    first = builder.trigger("first", looping=False)
    second = builder.trigger("second", enabled=False, looping=True)
    assert builder.names.resolve("trigger", "first") == first.trigger_id
    assert builder.names.resolve("trigger", "second") == second.trigger_id
    assert builder.variable("lives", variable_id=3) == 3
    assert builder.names.resolve("variable", "lives") == 3


def test_shared_operations_write_their_native_conditions_and_effects(
    builder: Builder, tmp_path: Path
) -> None:
    region = (2, 2, 4, 4)
    for key in ("lives", "phase", "elapsed"):
        builder.variable(key)
    setup = builder.trigger("setup", looping=False)
    builder.value(setup, "lives", 2)
    builder.set_value(setup, "lives", 1)
    king = builder.scenario.unit_manager.add_unit(player=2, unit_const=KING, x=1.5, y=1.5)
    builder.protect(setup, [king.reference_id])
    builder.protect(setup, [])
    builder.resources(setup, 500, player=2)
    builder.research(setup, "FEUDAL_AGE", player=2)
    builder.tower_attack_bonus(setup, 4, player=2)
    purchase = builder.trigger("purchase", looping=True)
    builder.on_pad(purchase, region, price=3)
    builder.at_most(purchase, 1, "king", 0)
    builder.pay(purchase, region, 1, 3)
    builder.clock("tick", "elapsed", Operation.ADD, while_positive="phase")
    path = tmp_path / "builder.aoe2scenario"
    save_scenario(builder.scenario, path)
    triggers = {t["name"]: t for t in inspect_scenario(path)["triggers"]}

    setup_record = triggers["setup"]
    assert not setup_record["looping"] and setup_record["enabled"]
    assert [c["type"] for c in setup_record["conditions"]] == ["variable_value"]
    effects = setup_record["effects"]
    assert [e["type"] for e in effects] == [
        "change_variable",
        "disable_unit_attackable",
        "disable_object_deletion",
        *["modify_resource"] * 4,
        "research_technology",
        *["modify_attribute"] * 3,
    ]
    assert [attr_list(e["attributes"], "selected_object_ids") for e in effects[1:3]] == [
        [king.reference_id]
    ] * 2
    assert {attr_int(e["attributes"], "quantity") for e in effects[3:7]} == {500}
    assert {attr_int(e["attributes"], "source_player") for e in effects[1:]} == {2}
    bonus = [e["attributes"] for e in effects[8:]]
    assert {attr_int(b, "object_list_unit_id") for b in bonus} == {79, 234, 235}
    assert all(b["armour_attack_class"] == 3 and b["armour_attack_quantity"] == 4 for b in bonus)

    purchase_record = triggers["purchase"]
    pad, cap = (c["attributes"] for c in purchase_record["conditions"])
    assert (pad["quantity"], pad["object_list"], pad["area_x2"]) == (3, 434, 4)
    assert (cap["quantity"], cap["object_list"]) == (0, 434)
    [payment] = purchase_record["effects"]
    assert (payment["attributes"]["max_units_affected"], payment["attributes"]["area_y1"]) == (3, 2)

    tick = triggers["tick"]
    assert tick["looping"]
    assert [c["type"] for c in tick["conditions"]] == ["timer", "variable_value"]
    assert [e["type"] for e in tick["effects"]] == ["change_variable"]


def test_every_trigger_states_whether_it_repeats() -> None:
    looping = inspect.signature(Builder.trigger).parameters["looping"]
    assert looping.default is inspect.Parameter.empty


def test_objects_are_protected_through_their_own_owners(builder: Builder, tmp_path: Path) -> None:
    # DE applies these effects only to the source player's objects, so a protection that
    # named one owner for another player's object would leave that object exposed.
    add = builder.scenario.unit_manager.add_unit
    first, partner, second = (
        add(player=player, unit_const=KING, x=x, y=1.5).reference_id
        for player, x in ((2, 1.5), (3, 3.5), (2, 5.5))
    )
    setup = builder.trigger("setup", looping=False)
    builder.protect(setup, [first, partner, second])
    with pytest.raises(ValueError, match="never placed: 99"):
        builder.protect(setup, [99])
    path = tmp_path / "protect.aoe2scenario"
    save_scenario(builder.scenario, path)
    [record] = inspect_scenario(path)["triggers"]
    assert [
        (
            e["type"],
            attr_int(e["attributes"], "source_player"),
            attr_list(e["attributes"], "selected_object_ids"),
        )
        for e in record["effects"]
    ] == [
        ("disable_unit_attackable", 2, [first, second]),
        ("disable_object_deletion", 2, [first, second]),
        ("disable_unit_attackable", 3, [partner]),
        ("disable_object_deletion", 3, [partner]),
    ]


def test_a_builder_looks_up_stock_ids_in_its_own_object_table() -> None:
    scenario = new_scenario("1.59")
    assert Builder(scenario).stock("king") == KING
    with pytest.raises(KeyError):
        Builder(scenario).stock("life")
    assert Builder(scenario, {"life": (BuildingInfo, "BARRACKS")}).stock("life") == BARRACKS
