"""Native triggers that apply a civilization profile's adjustments to an initialized lane."""

import json
from pathlib import Path
from typing import cast

import pytest
from AoE2ScenarioParser.datasets.techs import TechInfo
from conftest import (
    ROOT,
    GameBuild,
    attr_int,
    attr_list,
    effects,
    load_scenario,
    save_scenario,
    triggers_by_name,
    variables_by_name,
)

from ancienttdde.common.data import write_json
from ancienttdde.game.civilizations import Civilization, Profile, Profiles
from ancienttdde.game.config import Resources
from ancienttdde.map.models import MapAnchor
from ancienttdde.scenario.snapshot import ScenarioSnapshot, TriggerRecord

SET, ADD, SUBTRACT = 1, 2, 3
HIT_POINTS, ATTACK, STONE_COSTS = 0, 9, 106
PIERCE = 3
TOWERS = (79, 234, 235, 236)
CART, COG, RELIC, MONASTERY, MONK = 128, 17, 285, 104, 125
# Civilizations no content defines, with every native adjustment, a copy differing only in
# what the XS applies, a second effect set and a neutral one.
RICH = Profile(
    kings=1,
    resources=Resources(0, 0, 500, 100),
    population=20,
    technologies=("MASONRY", "ARCHITECTURE"),
    attack=(("towers", 2), ("bombard", 50)),
    tower_hit_points=300,
    tower_stone=25,
    relics=1,
    traders=(("land", 1), ("water", 2)),
    purchases=("castle_age", "resource_villagers", "castle", "relics"),
)
TEST_PROFILES = Profiles(
    "a civilization without a profile",
    Profile(),
    (
        Civilization("RICH", 100, "", RICH),
        Civilization(
            "RICHER",
            101,
            "",
            Profile(
                kings=3,
                resources=RICH.resources,
                population=20,
                technologies=RICH.technologies,
                attack=RICH.attack,
                tower_hit_points=300,
                tower_stone=25,
                relics=1,
                traders=RICH.traders,
                purchases=RICH.purchases,
                raiders=(("land", 1),),
            ),
        ),
        Civilization("SHARP", 102, "", Profile(attack=(("towers", 5),))),
        Civilization("PLAIN", 103, "", Profile(kings=2)),
    ),
)


def requested(trigger: TriggerRecord, variable: int) -> int | None:
    for condition in trigger["conditions"]:
        attributes = condition["attributes"]
        if condition["type"] == "variable_value" and attributes["variable"] == variable:
            return attr_int(attributes, "quantity")
    return None


@pytest.fixture(scope="module")
def profile_scenario(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[ScenarioSnapshot, dict[str, MapAnchor]]:
    """The migrated map with the first lane's profile triggers for the test civilizations."""
    from ancienttdde.common.worker import run_module
    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.profiles import lane_profiles
    from ancienttdde.game.triggers import Game
    from ancienttdde.map.build import read_content
    from ancienttdde.map.foundation import migrate_map
    from ancienttdde.scenario.inspect import inspect_scenario

    directory = tmp_path_factory.mktemp("profile-triggers")
    legacy, config = read_content(ROOT)
    write_json(directory / "map.json", migrate_map(legacy, config))
    # Construction runs in its own interpreter, as the builds run it.
    run_module(
        "ancienttdde.map.construct",
        str(ROOT / "content/maps/format-seed.aoe2scenario"),
        str(directory / "map.json"),
        str(directory / "foundation.aoe2scenario"),
        label="Map construction",
    )
    scenario = load_scenario(directory / "foundation.aoe2scenario")
    game = Game(scenario)
    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = config["anchors"]
    lane = load_lanes(cast(dict[str, object], anchors))[0]
    lane_profiles(game, lane, balance, TEST_PROFILES, shop())
    save_scenario(scenario, directory / "profiles.aoe2scenario")
    return inspect_scenario(directory / "profiles.aoe2scenario"), anchors


def shop():
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance

    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8"))
    families = [
        name for name, _ in load_balance(ROOT / "content/balance/game.json").towers.families
    ]
    return load_shop(ROOT / "content/balance/shop.json", anchors["anchors"], families)


def test_each_native_effect_set_gets_one_gated_trigger_per_lane(
    profile_scenario: tuple[ScenarioSnapshot, dict[str, MapAnchor]],
) -> None:
    snapshot, _ = profile_scenario
    triggers = triggers_by_name(snapshot)
    variables = variables_by_name(snapshot)
    assert [name for name in triggers if ".profile." in name] == [
        "lane.p1.profile.1",
        "lane.p1.profile.2",
    ]
    assert [TEST_PROFILES.native_index(c.profile) for c in TEST_PROFILES.civilizations] == [
        1,
        1,
        2,
        0,
    ]
    # The XS sets the profile field only for an active lane whose setup has run, so the set
    # number is the one condition; the sets the lane does not play cost one check a pass.
    for index in (1, 2):
        trigger = triggers[f"lane.p1.profile.{index}"]
        assert not trigger["looping"] and trigger["enabled"]
        assert requested(trigger, variables["lane.p1.profile"]) == index
        assert len(trigger["conditions"]) == 1
    sharp = triggers["lane.p1.profile.2"]
    assert [e["type"] for e in sharp["effects"]] == ["modify_attribute"] * 4
    assert {
        (e["object_list_unit_id"], e["armour_attack_quantity"])
        for e in effects(sharp, "modify_attribute")
    } == {(tower, 5) for tower in TOWERS}


def test_resources_population_and_technologies_are_granted_once(
    profile_scenario: tuple[ScenarioSnapshot, dict[str, MapAnchor]],
) -> None:
    snapshot, _ = profile_scenario
    trigger = triggers_by_name(snapshot)["lane.p1.profile.1"]
    granted = {
        (e["tribute_list"], attr_int(e, "operation")): attr_int(e, "quantity")
        for e in effects(trigger, "modify_resource")
    }
    assert granted == {(2, ADD): 500, (3, ADD): 100, (4, ADD): 20}
    assert all(e["source_player"] == 1 for e in effects(trigger, "modify_resource"))
    researched = [
        (e["technology"], e["force_research_technology"], e["source_player"])
        for e in effects(trigger, "research_technology")
    ]
    assert researched == [
        (TechInfo[name].ID, 1, 1) for name in ("MASONRY", "ARCHITECTURE", "CASTLE_AGE")
    ]


def test_tower_attack_hit_points_and_stone_cost_reach_every_tower_definition(
    profile_scenario: tuple[ScenarioSnapshot, dict[str, MapAnchor]],
) -> None:
    snapshot, _ = profile_scenario
    trigger = triggers_by_name(snapshot)["lane.p1.profile.1"]
    changes = effects(trigger, "modify_attribute")
    assert all(c["source_player"] == 1 for c in changes)
    attack = [
        (c["object_list_unit_id"], c["armour_attack_quantity"])
        for c in changes
        if c["object_attributes"] == ATTACK
    ]
    assert attack == [(t, 2) for t in TOWERS] + [(236, 50)]
    assert all(
        c["armour_attack_class"] == PIERCE and c["operation"] == ADD
        for c in changes
        if c["object_attributes"] == ATTACK
    )
    hit_points = {
        c["object_list_unit_id"]: (attr_int(c, "quantity"), c["operation"])
        for c in changes
        if c["object_attributes"] == HIT_POINTS
    }
    assert hit_points == {t: (300, ADD) for t in TOWERS}
    stone = {
        c["object_list_unit_id"]: (attr_int(c, "quantity"), c["operation"])
        for c in changes
        if c["object_attributes"] == STONE_COSTS
    }
    assert stone == {t: (25, SUBTRACT) for t in TOWERS}


def test_relics_and_traders_appear_at_the_lanes_sites_and_trade_at_once(
    profile_scenario: tuple[ScenarioSnapshot, dict[str, MapAnchor]],
) -> None:
    snapshot, anchors = profile_scenario
    trigger = triggers_by_name(snapshot)["lane.p1.profile.1"]
    units = {u["reference_id"]: u for u in snapshot["units"]}
    [relic] = effects(trigger, "create_garrisoned_object")
    assert (
        relic["source_player"],
        relic["object_list_unit_id"],
        relic["object_list_unit_id_2"],
    ) == (
        0,
        RELIC,
        RELIC,
    )
    [monastery] = attr_list(relic, "selected_object_ids")
    assert monastery == anchors["lane.p1.monastery.1"].get("reference_id")
    assert units[monastery]["unit_const"] == MONASTERY and units[monastery]["player_id"] == 1
    created = [
        (e["object_list_unit_id"], attr_int(e, "location_x"), attr_int(e, "location_y"))
        for e in effects(trigger, "create_object")
        if e["object_list_unit_id"] in (CART, COG)
    ]
    carts = [tuple(int(v) for v in p) for p in anchors["lane.p1.carts"].get("points", [])]
    cogs = [tuple(int(v) for v in p) for p in anchors["lane.p1.cogs"].get("points", [])]
    assert created == [(CART, *carts[0]), (COG, *cogs[0]), (COG, *cogs[1])]
    assert all(
        e["source_player"] == 1
        for e in effects(trigger, "create_object")
        if e["object_list_unit_id"] in (CART, COG)
    )
    orders = {
        e["object_list_unit_id"]: e["location_object_reference"]
        for e in effects(trigger, "task_object")
        if e["object_list_unit_id"] in (CART, COG)
    }
    assert orders == {
        CART: anchors["trade.land.p1.partner"].get("reference_id"),
        COG: anchors["trade.water.p1.partner"].get("reference_id"),
    }
    [cogs_order] = [e for e in effects(trigger, "task_object") if e["object_list_unit_id"] == COG]
    assert (
        cogs_order["area_x1"],
        cogs_order["area_y1"],
        cogs_order["area_x2"],
        cogs_order["area_y2"],
    ) == (
        min(c[0] for c in cogs[:2]),
        min(c[1] for c in cogs[:2]),
        max(c[0] for c in cogs[:2]),
        max(c[1] for c in cogs[:2]),
    )


def test_granted_purchases_apply_their_effects_to_the_units_the_xs_places(
    profile_scenario: tuple[ScenarioSnapshot, dict[str, MapAnchor]],
) -> None:
    snapshot, anchors = profile_scenario
    trigger = triggers_by_name(snapshot)["lane.p1.profile.1"]
    # The XS places granted units at initialization exactly as it does after a payment, so the
    # trigger creates only the starting traders and relics of the settings.
    made = {attr_int(e, "object_list_unit_id") for e in effects(trigger, "create_object")}
    assert made == {CART, COG}
    villagers = [
        tuple(int(v) for v in p) for p in anchors["lane.p1.villagers.economy"].get("points", [])
    ]
    # Granted villagers walk off their arrival, as after a purchase.
    walks = [e for e in effects(trigger, "task_object") if e["object_list_unit_id"] == 83]
    assert len(walks) == 1 and walks[0]["action_type"] == 1
    assert (walks[0]["location_x"], walks[0]["location_y"]) == villagers[2]
    # The age arrives natively; the XS asks for its tower upgrade as after a payment.
    researched = {attr_int(e, "technology") for e in effects(trigger, "research_technology")}
    assert TechInfo["CASTLE_AGE"].ID in researched


def test_more_starting_traders_than_spots_are_rejected(tmp_path: Path) -> None:
    from conftest import new_scenario

    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.profiles import lane_profiles
    from ancienttdde.game.triggers import Game

    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    lane = load_lanes(anchors)[0]
    greedy = Profiles(
        "", Profile(), (Civilization("GREEDY", 100, "", Profile(traders=(("land", 4),))),)
    )
    game = Game(new_scenario())
    with pytest.raises(ValueError, match="cart"):
        lane_profiles(game, lane, balance, greedy, shop())


def test_the_built_game_holds_one_trigger_per_lane_and_native_effect_set(
    game_build: GameBuild,
) -> None:
    from ancienttdde.game.civilizations import load_profiles
    from ancienttdde.game.config import load_balance

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    profiles = load_profiles(
        ROOT / "content/balance/civilizations.json",
        load_balance(ROOT / "content/balance/game.json"),
        shop(),
    )
    names = [t["name"] for t in snapshot["triggers"] if ".profile." in t["name"]]
    assert names == [
        f"lane.p{player}.profile.{index}"
        for player in range(1, 8)
        for index in range(1, len(profiles.native_groups()) + 1)
    ]
    prelude = (output / "runtime-prelude.xs").read_text(encoding="utf-8")
    native = prelude.split("int civNative")[1].split("}")[0]
    for civilization in profiles.civilizations:
        index = profiles.native_index(civilization.profile)
        if index != profiles.native_index(profiles.default):
            assert f"if (index == {civilization.id}) return ({index});" in native
