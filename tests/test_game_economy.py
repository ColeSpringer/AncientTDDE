"""The built game's native economy, shop and tower triggers, read back from the scenario."""

import json
import math
from typing import Any

import pytest
from conftest import (
    ROOT,
    GameBuild,
    attr_int,
    attr_list,
    attr_text,
    cached_json,
    effects,
    triggers_by_name,
    variables_by_name,
)

from ancienttdde.scenario.snapshot import ScenarioSnapshot, TriggerRecord

PLAYERS = range(1, 8)
KING, VILLAGER, RELIC, MONK, CASTLE, MONASTERY = 434, 83, 285, 125, 82, 104
HAY_STACK, SIGN, ACCURSED = 857, 819, 684
TOWERS, BOMBARD = (79, 234, 235, 236), (236,)
ATTACK, PIERCE, SET, ADD, SUBTRACT = 9, 3, 1, 2, 3


def snapshot(build: GameBuild) -> ScenarioSnapshot:
    output, _ = build
    return cached_json(output / "scenario.json")


def anchors(build: GameBuild) -> dict[str, Any]:
    output, _ = build
    return cached_json(output / "map.json")["anchors"]


def catalog() -> list[dict[str, Any]]:
    return json.loads((ROOT / "content/balance/shop.json").read_text())["purchases"]


def balance() -> dict[str, Any]:
    return json.loads((ROOT / "content/balance/game.json").read_text())


def tile(point: list[float]) -> tuple[int, int]:
    return math.floor(point[0]), math.floor(point[1])


def located(effect: dict[str, Any]) -> tuple[int, int]:
    return attr_int(effect, "location_x"), attr_int(effect, "location_y")


def requested(trigger: TriggerRecord, variable: int) -> int | None:
    for c in trigger["conditions"]:
        attributes = c["attributes"]
        if c["type"] == "variable_value" and attributes["variable"] == variable:
            return attr_int(attributes, "quantity")
    return None


@pytest.mark.parametrize("player", PLAYERS)
def test_each_purchase_has_one_acknowledgement_per_lane(game_build: GameBuild, player: int) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variable = variables_by_name(data)[f"lane.p{player}.purchase"]
    for index, purchase in enumerate(catalog(), 1):
        trigger = triggers[f"lane.p{player}.buy.{purchase['key']}"]
        assert trigger["looping"]
        assert requested(trigger, variable) == index
        cleared = effects(trigger, "change_variable")[-1]
        assert cleared["variable"] == variable and cleared["quantity"] == 0
        assert cleared["operation"] == SET
        [chat] = effects(trigger, "send_chat")
        assert chat["source_player"] == player
        assert purchase["name"] in chat["message"]


def test_attack_changes_target_only_tower_definitions(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    assert not any(
        e["type"]
        in ("change_object_attack", "modify_attribute_for_class", "modify_object_attribute")
        for t in data["triggers"]
        for e in t["effects"]
    )
    for trigger in data["triggers"]:
        for attributes in effects(trigger, "modify_attribute"):
            if attributes["object_attributes"] == ATTACK:
                assert attributes["object_list_unit_id"] in (*TOWERS, ACCURSED)
                assert attributes["armour_attack_class"] == PIERCE


@pytest.mark.parametrize(
    ("key", "family", "amount"),
    [("tower_attack_50", TOWERS, 50), ("bombard_attack_400", BOMBARD, 400)],
)
def test_tower_attack_purchases_raise_their_family(
    game_build: GameBuild, key: str, family: tuple[int, ...], amount: int
) -> None:
    triggers = triggers_by_name(snapshot(game_build))
    for player in PLAYERS:
        changes = effects(triggers[f"lane.p{player}.buy.{key}"], "modify_attribute")
        assert sorted(c["object_list_unit_id"] for c in changes) == sorted(family)
        assert all(c["source_player"] == player and c["operation"] == ADD for c in changes)
        assert all(c["armour_attack_quantity"] == amount for c in changes)


@pytest.mark.parametrize("player", PLAYERS)
def test_periodic_attack_arrives_one_point_at_a_time(game_build: GameBuild, player: int) -> None:
    data = snapshot(game_build)
    trigger = triggers_by_name(data)[f"lane.p{player}.attack"]
    attack = variables_by_name(data)[f"lane.p{player}.attack"]
    assert trigger["looping"]
    assert any(
        c["type"] == "variable_value"
        and c["attributes"]["variable"] == attack
        and c["attributes"]["quantity"] == 1
        and c["attributes"]["comparison"] == 4
        for c in trigger["conditions"]
    )
    changes = effects(trigger, "modify_attribute")
    assert sorted(c["object_list_unit_id"] for c in changes) == sorted(TOWERS)
    assert all(c["armour_attack_quantity"] == 1 for c in changes)
    [spent] = effects(trigger, "change_variable")
    assert (spent["variable"], spent["quantity"], spent["operation"]) == (attack, 1, SUBTRACT)


@pytest.mark.parametrize("player", PLAYERS)
def test_special_towers_replace_their_reserved_hay_stack(
    game_build: GameBuild, player: int
) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    units = {u["reference_id"]: u for u in data["units"]}
    for side in ("left", "right"):
        x, y, _, _ = anchors(game_build)[f"lane.p{player}.special.{side}"]["region"]
        trigger = triggers[f"lane.p{player}.buy.{side}_accursed_tower"]
        [removal] = effects(trigger, "remove_object")
        [hay] = attr_list(removal, "selected_object_ids")
        assert units[hay]["unit_const"] == HAY_STACK and units[hay]["player_id"] == 0
        assert (math.floor(units[hay]["x"]), math.floor(units[hay]["y"])) == (x, y)
        [tower] = effects(trigger, "create_object")
        assert tower["object_list_unit_id"] == ACCURSED and tower["source_player"] == player
        assert located(tower) == (x, y)


@pytest.mark.parametrize("player", PLAYERS)
def test_expansion_rows_remove_only_their_hay_stacks(game_build: GameBuild, player: int) -> None:
    triggers = triggers_by_name(snapshot(game_build))
    for row in ("third", "fourth"):
        removals = effects(triggers[f"lane.p{player}.buy.{row}_row"], "remove_object")
        regions = sorted([r["area_x1"], r["area_y1"], r["area_x2"], r["area_y2"]] for r in removals)
        expected = sorted(
            anchors(game_build)[f"lane.p{player}.expansion.{row}.{side}"]["region"]
            for side in ("north", "south")
        )
        assert regions == expected
        assert all(
            r["source_player"] == 0 and r["object_list_unit_id"] == HAY_STACK for r in removals
        )


@pytest.mark.parametrize("player", PLAYERS)
def test_lanes_start_with_the_original_economy(game_build: GameBuild, player: int) -> None:
    from AoE2ScenarioParser.datasets.techs import TechInfo

    data = snapshot(game_build)
    init = triggers_by_name(data)[f"lane.p{player}.initialize"]
    start = balance()["economy"]["starting_resources"]
    granted = {
        (e["tribute_list"], e["operation"]): e["quantity"] for e in effects(init, "modify_resource")
    }
    assert granted == {
        (0, SET): start["food"],
        (1, SET): start["wood"],
        (2, SET): start["stone"],
        (3, SET): start["gold"],
        (4, SET): 0,
    }
    researched = {
        e["technology"]: e["force_research_technology"]
        for e in effects(init, "research_technology")
    }
    expected = ["FEUDAL_AGE", *balance()["economy"]["starting_technologies"]]
    assert researched == {TechInfo[name].ID: 1 for name in expected}
    assert {"BALLISTICS", "MURDER_HOLES", "CARAVAN", "WHEELBARROW", "HAND_CART"} <= set(expected)
    assert all(e["source_player"] == player for e in effects(init, "research_technology"))
    special = [e for e in effects(init, "modify_attribute") if e["object_list_unit_id"] == ACCURSED]
    assert [(e["armour_attack_quantity"], e["operation"]) for e in special] == [
        (balance()["towers"]["special"]["pierce_bonus"], ADD)
    ]
    relics = effects(init, "create_garrisoned_object")
    assert len(relics) == balance()["economy"]["starting_relics"]
    units = {u["reference_id"]: u for u in data["units"]}
    for relic in relics:
        # Relics belong to Gaia, as in the original map's garrison effects.
        assert relic["object_list_unit_id_2"] == RELIC and relic["object_list_unit_id"] == RELIC
        assert relic["source_player"] == 0
        [monastery] = attr_list(relic, "selected_object_ids")
        assert units[monastery]["unit_const"] == MONASTERY
        assert units[monastery]["player_id"] == player


@pytest.mark.parametrize("player", PLAYERS)
def test_new_kings_walk_from_the_stall_into_the_shop(game_build: GameBuild, player: int) -> None:
    trigger = triggers_by_name(snapshot(game_build))[f"lane.p{player}.king"]
    spawn, rally = (tile(p) for p in anchors(game_build)[f"lane.p{player}.kings"]["points"])
    assert trigger["looping"]
    [waiting] = [c["attributes"] for c in trigger["conditions"] if c["type"] == "objects_in_area"]
    assert waiting["object_list"] == KING and waiting["source_player"] == player
    assert (waiting["area_x1"], waiting["area_y1"], waiting["area_x2"], waiting["area_y2"]) == (
        *spawn,
        *spawn,
    )
    [walk] = effects(trigger, "task_object")
    assert located(walk) == rally and walk["object_list_unit_id"] == KING
    assert not effects(trigger, "create_object") and not effects(trigger, "change_variable")


@pytest.mark.parametrize("player", PLAYERS)
def test_transferred_villagers_walk_clear_of_the_arrival(
    game_build: GameBuild, player: int
) -> None:
    triggers = triggers_by_name(snapshot(game_build))
    for name in ("build", "economy", "north", "south"):
        site = anchors(game_build)[f"lane.p{player}.transfer.{name}"]
        arrival, walk = (tile(p) for p in site["points"])
        trigger = triggers[f"lane.p{player}.transfer.{name}"]
        assert trigger["looping"]
        [standing] = [
            c["attributes"] for c in trigger["conditions"] if c["type"] == "objects_in_area"
        ]
        assert standing["object_group"] == 4 and standing["source_player"] == player
        assert (standing["area_x1"], standing["area_y1"]) == arrival
        assert (standing["area_x2"], standing["area_y2"]) == arrival
        [moved] = effects(trigger, "task_object")
        assert moved["object_group"] == 4 and located(moved) == walk
        assert not effects(trigger, "remove_object") and not effects(trigger, "create_object")


@pytest.mark.parametrize("player", PLAYERS)
@pytest.mark.parametrize(
    ("resource", "deposit", "tribute"), [("gold", 66, 3), ("food", 59, 0), ("stone", 102, 2)]
)
def test_resource_bonuses_pay_once_and_open_endless_deposits(
    game_build: GameBuild, player: int, resource: str, deposit: int, tribute: int
) -> None:
    trigger = triggers_by_name(snapshot(game_build))[f"lane.p{player}.bonus.{resource}"]
    assert not trigger["looping"]
    reached = [c["attributes"] for c in trigger["conditions"] if c["type"] == "objects_in_area"]
    region = anchors(game_build)[f"lane.p{player}.bonus.{resource}"]["region"]
    assert [[r["area_x1"], r["area_y1"], r["area_x2"], r["area_y2"]] for r in reached] == [region]
    assert reached[0]["source_player"] == player and reached[0]["object_group"] == 4
    [grant] = effects(trigger, "modify_resource")
    assert grant["tribute_list"] == tribute
    assert grant["quantity"] == balance()["economy"]["resource_bonus"][resource]
    created = [e for e in effects(trigger, "create_object") if e["object_list_unit_id"] == deposit]
    expected = [
        tile(p) for p in anchors(game_build)[f"lane.p{player}.endless.{resource}"]["points"]
    ]
    assert sorted(located(e) for e in created) == sorted(expected)
    assert all(e["source_player"] == 0 for e in created)
    from ancienttdde.game.config import load_balance
    from ancienttdde.game.instructions import bonus_delivered

    [chat] = effects(trigger, "send_chat")
    assert chat["message"] == bonus_delivered(
        load_balance(ROOT / "content/balance/game.json"), resource
    )


@pytest.mark.parametrize("player", PLAYERS)
def test_messages_reach_only_their_lanes_player(game_build: GameBuild, player: int) -> None:
    from ancienttdde.game.config import load_balance
    from ancienttdde.game.messages import MESSAGES, message_code, message_texts

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    texts = message_texts(load_balance(ROOT / "content/balance/game.json"))
    # The gold per King depends on the difficulty, which the game announces when it starts.
    assert texts["gold"] == "Gold converted into Kings; they arrive at your stall."
    # The objectives show only the shared siege cooldown; the last buyer waits longer.
    assert "longer for its last buyer" in texts["siege_cooldown"]
    for key, _ in MESSAGES:
        trigger = triggers[f"lane.p{player}.message.{key}"]
        assert trigger["looping"]
        assert requested(trigger, variables[f"lane.p{player}.message"]) == message_code(key)
        [chat] = effects(trigger, "send_chat")
        assert chat["source_player"] == player and chat["message"] == texts[key]
        [cleared] = effects(trigger, "change_variable")
        assert cleared["variable"] == variables[f"lane.p{player}.message"]
        assert (cleared["quantity"], cleared["operation"]) == (0, SET)
    script = data["dependencies"]["embedded_xs"]
    assert "shopName" not in script and "xsSendChat" not in script


def test_new_deposits_hold_more_than_a_run_uses(game_build: GameBuild) -> None:
    trigger = triggers_by_name(snapshot(game_build))["game.deposits"]
    assert not trigger["looping"] and not trigger["conditions"]
    changes = {e["object_list_unit_id"]: e for e in effects(trigger, "modify_attribute")}
    assert sorted(changes) == [59, 66, 102]
    for change in changes.values():
        assert change["source_player"] == 0 and change["object_attributes"] == 21
        assert change["quantity"] == balance()["economy"]["endless_deposit"] <= 32767


def test_shop_has_no_signs_and_keeps_its_named_units(game_build: GameBuild) -> None:
    """DE cannot rename Sign objects, so the shop's signs are removed; the named units stay."""
    data = snapshot(game_build)
    x1, y1, x2, y2 = anchors(game_build)["shop.bounds"]["region"]
    inside = [u for u in data["units"] if x1 <= u["x"] <= x2 + 1 and y1 <= u["y"] <= y2 + 1]
    assert not [u for u in inside if u["unit_const"] == SIGN]
    units = {u["reference_id"]: u for u in data["units"]}
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance

    families = [
        name for name, _ in load_balance(ROOT / "content/balance/game.json").towers.families
    ]
    shop = load_shop(ROOT / "content/balance/shop.json", anchors(game_build), families)
    assert all(p.display in units for p in shop.purchases if p.display is not None)
    # The resource bonus signs stay as markers at the end of the rows.
    assert len([u for u in data["units"] if u["unit_const"] == SIGN]) == 21
    labels = triggers_by_name(data)["game.labels"]
    for rename in effects(labels, "change_object_name"):
        [ref] = attr_list(rename, "selected_object_ids")
        assert units[ref]["unit_const"] != SIGN


def test_waves_are_announced_with_a_countdown(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    waves = balance()["waves"]
    for number, wave in enumerate(waves, 1):
        trigger = triggers[f"game.wave.{number}.warning"]
        assert not trigger["looping"]
        assert requested(trigger, variables["game.wave"]) == number - 2
        assert requested(trigger, variables["game.phase"]) == 2
        [timer] = effects(trigger, "display_timer")
        seconds = (
            balance()["preparation_seconds"] if number == 1 else balance()["intermission_seconds"]
        )
        assert timer["display_time"] == seconds
        assert wave["key"] in timer["message"] and "%d" in timer["message"]


def test_no_flat_income_or_forced_population(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    assert not any(name.endswith(".income") for name in triggers)
    for trigger in data["triggers"]:
        # The population purchase, and a civilization profile applied once, may add headroom;
        # the lane's setup only levels it to zero.
        if trigger["name"].endswith(".buy.population") or ".profile." in trigger["name"]:
            continue
        for e in effects(trigger, "modify_resource"):
            if e["tribute_list"] == 4:
                assert trigger["name"].endswith(".initialize") and e["operation"] == SET
                assert e["quantity"] == 0


@pytest.mark.parametrize("player", PLAYERS)
def test_purchases_place_units_at_their_lane_sites(game_build: GameBuild, player: int) -> None:
    from ancienttdde.common.data import object_value
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.spawns import purchase_spawns

    sites = anchors(game_build)
    families = [
        name for name, _ in load_balance(ROOT / "content/balance/game.json").towers.families
    ]
    shop = load_shop(ROOT / "content/balance/shop.json", sites, families)
    lane = load_lanes(object_value(sites, "anchors"))[player - 1]

    raiders = load_balance(ROOT / "content/balance/game.json").interaction.raiders

    def spawned(key: str, kind: int) -> list[tuple[int, int]]:
        made = purchase_spawns(lane, shop.get(key), raiders)
        return sorted((s.x10 // 10, s.y10 // 10) for s in made if s.unit == kind)

    def points(key: str, count: int | None = None) -> list[tuple[int, int]]:
        return sorted(tile(p) for p in sites[f"lane.p{player}.{key}"]["points"][:count])

    assert spawned("building_villagers", VILLAGER) == points("villagers.build", 2)
    assert spawned("resource_villagers", VILLAGER) == points("villagers.economy", 2)
    assert spawned("relics", RELIC) == points("relics")
    assert spawned("relics", MONK) == points("monks")
    assert spawned("trade_carts", 128) == points("carts")
    assert spawned("trade_cogs", 17) == points("cogs")
    assert spawned("land_raider", raiders.land.unit_id) == points("raiders.land", 1)
    assert spawned("naval_raider", raiders.naval.unit_id) == points("raiders.naval", 1)
    assert purchase_spawns(lane, shop.get("siege"), raiders) == ()
    assert all(
        s.gaia == (s.unit == RELIC) for s in purchase_spawns(lane, shop.get("relics"), raiders)
    )
    [castle] = purchase_spawns(lane, shop.get("castle"), raiders)
    assert castle.unit == CASTLE
    assert (castle.x10, castle.y10) == tuple(
        10 * int(v) for v in sites[f"lane.p{player}.castle"]["point"]
    )
    triggers = triggers_by_name(snapshot(game_build))
    for key in (
        "building_villagers",
        "resource_villagers",
        "trade_carts",
        "trade_cogs",
        "relics",
        "castle",
    ):
        assert not effects(triggers[f"lane.p{player}.buy.{key}"], "create_object"), key
    moved = effects(triggers[f"lane.p{player}.buy.relic_enclosure"], "change_ownership")
    assert sorted(m["object_list_unit_id"] for m in moved) == sorted([MONK, MONASTERY])
    assert all(m["source_player"] == 0 and m["target_player"] == player for m in moved)
    [population] = effects(triggers[f"lane.p{player}.buy.population"], "modify_resource")
    assert (population["tribute_list"], population["operation"]) == (4, ADD)
    [walk] = effects(triggers[f"lane.p{player}.buy.building_villagers"], "task_object")
    assert located(walk) == tile(sites[f"lane.p{player}.villagers.build"]["points"][2])
    [trade] = effects(triggers[f"lane.p{player}.buy.trade_carts"], "task_object")
    assert (
        trade["location_object_reference"] == sites[f"trade.land.p{player}.partner"]["reference_id"]
    )


def test_objects_are_named_when_the_game_starts(game_build: GameBuild) -> None:
    """Pad displays, transfer labels, life Outposts and the credit are renamed at once, as the
    original map does, so players can read what they are buying and where they are."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.catalog import display_captions, load_shop
    from ancienttdde.game.config import load_balance, load_lanes

    data = snapshot(game_build)
    trigger = triggers_by_name(data)["game.labels"]
    assert not trigger["conditions"] and not trigger["looping"]
    units = {u["reference_id"]: u for u in data["units"]}
    names: dict[int, str] = {}
    for rename in effects(trigger, "change_object_name"):
        [ref] = attr_list(rename, "selected_object_ids")
        assert rename["source_player"] == units[ref]["player_id"]
        names[ref] = attr_text(rename, "message")
    sites = anchors(game_build)
    balance = load_balance(ROOT / "content/balance/game.json")
    shop = load_shop(
        ROOT / "content/balance/shop.json", sites, [name for name, _ in balance.towers.families]
    )
    for ref, caption in display_captions(shop).items():
        assert names[ref] == caption
    for purchase in shop.purchases:
        if purchase.display is not None:
            assert purchase.caption in names[purchase.display]
        else:
            [king] = [
                ref
                for ref, u in units.items()
                if u["unit_const"] == KING and (u["x"], u["y"]) == purchase.display_at
            ]
            assert units[king]["player_id"] == 0 and names[king] == purchase.caption
    relics = [ref for ref, u in units.items() if u["unit_const"] == RELIC and u["player_id"] == 0]

    def label_near(x: int, y: int) -> int:
        center = (x + 0.5, y + 0.5)
        [found] = [r for r in relics if math.dist((units[r]["x"], units[r]["y"]), center) <= 2.5]
        return found

    for lane in load_lanes(object_value(sites, "anchors")):
        assert names[lane.life_reference].startswith(f"P{lane.player} lives")
        for key, transfer in lane.sites.transfers.items():
            pad = names[label_near(transfer.pad[0], transfer.pad[1])]
            arrival = names[label_near(*transfer.arrival)]
            assert pad.startswith("Transfer pad:") and "moves to the" in pad, key
            assert "arrive here from the" in arrival, key
            if key == "build":
                # Bought building villagers appear on the arrival tile itself.
                assert arrival.endswith("and when bought"), arrival
            elif key == "economy":
                # Bought resource villagers appear two tiles from the arrival.
                assert arrival.endswith("bought villagers appear beside it"), arrival
            else:
                assert "bought" not in arrival
    assert names[21492] == "Based on Ancient TD v5.3 by DRAX6869 / DRAX"


def test_pad_exhibits_stand_where_the_catalog_puts_them_with_their_captions(
    game_build: GameBuild,
) -> None:
    """A placed exhibit with a display_at is moved there and a King is created there
    otherwise; each carries its purchases' tags as the caption DE draws above it."""
    from ancienttdde.game.catalog import display_captions, load_shop
    from ancienttdde.game.config import load_balance

    data = snapshot(game_build)
    units = {u["reference_id"]: u for u in data["units"]}
    balance = load_balance(ROOT / "content/balance/game.json")
    shop = load_shop(
        ROOT / "content/balance/shop.json",
        anchors(game_build),
        [name for name, _ in balance.towers.families],
    )
    tags = display_captions(shop, overhead=True)
    for purchase in shop.purchases:
        if purchase.display is not None:
            unit = units[purchase.display]
            assert unit.get("caption_string") == tags[purchase.display], purchase.key
            if purchase.display_at is not None:
                assert (unit["x"], unit["y"]) == purchase.display_at, purchase.key
        else:
            [king] = [
                u
                for u in units.values()
                if u["unit_const"] == KING and (u["x"], u["y"]) == purchase.display_at
            ]
            assert king["player_id"] == 0 and king.get("caption_string") == purchase.tag
    assert tags[shop.get("tower_attack_4").display or 0] == "+4 attack: 1 King"


@pytest.mark.parametrize("player", PLAYERS)
def test_creation_tiles_hold_no_placed_objects(game_build: GameBuild, player: int) -> None:
    """XS creates Kings, bought units and transferred villagers with collision checks, so even
    the map's marker flags must be gone from those tiles."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.spawns import creation_tiles

    sites = anchors(game_build)
    families = [
        name for name, _ in load_balance(ROOT / "content/balance/game.json").towers.families
    ]
    shop = load_shop(ROOT / "content/balance/shop.json", sites, families)
    lane = load_lanes(object_value(sites, "anchors"))[player - 1]
    balance = load_balance(ROOT / "content/balance/game.json")
    tiles = creation_tiles(lane, shop, balance.interaction)
    assert lane.sites.king_spawn in tiles and len(tiles) >= 18
    # Trebuchets arrive on this lane's islets for whoever holds the siege.
    assert set(lane.sites.siege[: balance.interaction.siege.trebuchets_per_rival]) <= tiles
    assert {spawn.tiles[0] for spawn in lane.sites.raiders.values()} <= tiles
    standing = [
        (u["unit_const"], math.floor(u["x"]), math.floor(u["y"]))
        for u in snapshot(game_build)["units"]
        if (math.floor(u["x"]), math.floor(u["y"])) in tiles
    ]
    assert standing == []
    # The transfer pads keep their flags: players stand villagers on them.
    flags = {
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in snapshot(game_build)["units"]
        if u["unit_const"] in (601, 602, 603)
    }
    for transfer in lane.sites.transfers.values():
        assert (transfer.pad[0], transfer.pad[1]) in flags


@pytest.mark.parametrize("player", PLAYERS)
def test_age_purchases_research_only_the_age_natively(game_build: GameBuild, player: int) -> None:
    triggers = triggers_by_name(snapshot(game_build))
    for key, age in (("castle_age", 102), ("imperial_age", 103)):
        [research] = effects(triggers[f"lane.p{player}.buy.{key}"], "research_technology")
        assert (research["technology"], research["force_research_technology"]) == (age, 1)


def test_game_reads_its_shop_catalog(game_build: GameBuild) -> None:
    _, manifest = game_build
    assert "content/balance/shop.json" in {r["path"] for r in manifest["inputs"]}


def test_objectives_show_the_wave_countdown_and_every_lane(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    status = triggers["game.status"]
    assert status["display_as_objective"]
    assert f"<Variable {variables['game.display_wave']}>" in status["short_description"]
    assert f"<Variable {variables['game.countdown']}>" in status["short_description"]
    for player in PLAYERS:
        lane = triggers[f"lane.p{player}.status"]
        assert lane["display_as_objective"]
        lives = variables[f"lane.p{player}.lives"]
        assert f"<Variable {lives}>/{balance()['lives']}" in lane["short_description"]
    # Shown from the start and never fired: they only display their variables.
    for shown in [status] + [triggers[f"lane.p{p}.status"] for p in PLAYERS]:
        assert shown["enabled"] and shown["display_on_screen"] and not shown["effects"]
        assert [(c["type"], c["attributes"]["quantity"]) for c in shown["conditions"]] == [
            ("variable_value", -1)
        ]


@pytest.mark.parametrize("player", PLAYERS)
def test_population_starts_at_zero_headroom_for_every_lane(
    game_build: GameBuild, player: int
) -> None:
    init = triggers_by_name(snapshot(game_build))[f"lane.p{player}.initialize"]
    headroom = [
        (e["operation"], e["quantity"])
        for e in effects(init, "modify_resource")
        if e["tribute_list"] == 4 and e["source_player"] == player
    ]
    # Civilization bonuses that start with population are levelled; only purchases add it.
    assert headroom == [(SET, 0)]
