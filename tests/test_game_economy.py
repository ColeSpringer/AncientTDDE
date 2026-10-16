"""The built game's native economy, shop and tower triggers, read back from the scenario."""

import json
import math
from typing import Any

import pytest
from conftest import (
    ROOT,
    Attributes,
    GameBuild,
    attr_int,
    attr_list,
    attr_text,
    cached_json,
    effects,
    triggers_by_name,
    variables_by_name,
)

from ancienttdde.scenario.snapshot import MapUnit, ScenarioSnapshot, TriggerRecord

PLAYERS = range(1, 8)
KING, VILLAGER, RELIC, MONK, CASTLE, MONASTERY = 434, 83, 285, 125, 82, 104
FEMALE_VILLAGER, GOLD_MINE, STONE_MINE = 293, 66, 102
MONK_WITH_RELIC, POPULATION = 286, 110
HAY_STACK, SIGN, ACCURSED = 857, 819, 684
TOWERS, BOMBARD = (79, 234, 235, 236), (236,)
ATTACK, PIERCE, SET, ADD, SUBTRACT = 9, 3, 1, 2, 3
EQUAL = 0


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


def conditions_on(trigger: TriggerRecord, variable: int) -> list[Attributes]:
    """The attributes of a trigger's Variable Value conditions on one variable."""
    return [
        c["attributes"]
        for c in trigger["conditions"]
        if c["type"] == "variable_value" and c["attributes"]["variable"] == variable
    ]


def requested(trigger: TriggerRecord, variable: int) -> int | None:
    found = conditions_on(trigger, variable)
    return attr_int(found[0], "quantity") if found else None


def compared(trigger: TriggerRecord, variable: int) -> tuple[int, int]:
    """The comparison and quantity of a trigger's one condition on a variable."""
    [attributes] = conditions_on(trigger, variable)
    return attr_int(attributes, "comparison"), attr_int(attributes, "quantity")


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


def test_bought_and_periodic_tower_attack_is_left_to_the_xs(game_build: GameBuild) -> None:
    """A native effect cannot raise an attack class past 255, so no trigger adds bought or
    periodic tower attack: the XS adds it (see the attack cases in test_game_script.py)."""
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    bought = [p["key"] for p in catalog() if p["effect"]["kind"] == "tower_attack"]
    assert {"tower_attack_750", "bombard_attack_400"} <= set(bought)
    for player in PLAYERS:
        assert f"lane.p{player}.attack" not in triggers
        assert f"lane.p{player}.attack" not in variables
        for key in bought:
            assert not effects(triggers[f"lane.p{player}.buy.{key}"], "modify_attribute"), key


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
        (4, SET): balance()["economy"]["starting_population"],
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
def test_villagers_on_a_transfer_pad_are_teleported_to_its_arrival(
    game_build: GameBuild, player: int
) -> None:
    """Every villager standing on the pad moves to the arrival as it is, with its type and
    what it carries; nothing is removed or created, so the arrival flag stays. Each is first
    sent on to the arrival's walk tile, so none keeps walking back towards the pad."""
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    active = variables_by_name(data)[f"lane.p{player}.active"]
    for name in ("build", "economy", "north", "south"):
        site = anchors(game_build)[f"lane.p{player}.transfer.{name}"]
        pad = tuple(site["region"])
        arrival, walk = (tile(p) for p in site["points"])
        trigger = triggers[f"lane.p{player}.transfer.{name}.move"]
        assert trigger["looping"] and requested(trigger, active) == 1

        def region(attributes: dict[str, Any]) -> tuple[int, int, int, int]:
            return (
                attributes["area_x1"],
                attributes["area_y1"],
                attributes["area_x2"],
                attributes["area_y2"],
            )

        [standing] = [
            c["attributes"] for c in trigger["conditions"] if c["type"] == "objects_in_area"
        ]
        assert (standing["object_group"], standing["source_player"]) == (4, player)
        assert standing["quantity"] == 1 and region(standing) == pad
        assert [e["type"] for e in trigger["effects"]] == ["task_object", "teleport_object"]
        [sent] = effects(trigger, "task_object")
        assert (sent["object_group"], sent["source_player"], sent["action_type"]) == (4, player, 1)
        assert region(sent) == pad and located(sent) == walk
        [moved] = effects(trigger, "teleport_object")
        assert (moved["object_group"], moved["source_player"]) == (4, player)
        assert region(moved) == pad and located(moved) == arrival


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
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance
    from ancienttdde.game.messages import MESSAGES, message_code, message_texts

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    balance = load_balance(ROOT / "content/balance/game.json")
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(ROOT / "content/balance/shop.json", anchors(game_build), families)
    texts = message_texts(balance, shop)
    # The gold per King depends on the difficulty, which the game announces when it starts.
    assert texts["gold"] == "Gold converted into Kings; they arrive at your stall."
    # The population refusal names the purchase that adds room, as the shop sells it.
    assert texts["population"] == (
        "No population room for that purchase: +65 population adds some. Your Kings stay."
    )
    assert texts["population_limit"] == (
        "That purchase would take your lane past its population limit of 200; your Kings stay."
    )
    assert texts["population_full"] == (
        "Your lane's room already reaches its population limit of 200; your Kings stay."
    )
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
    assert sorted(changes) == [59, 66, 102, 399]
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
    from ancienttdde.game.waves import CHOICE_TIMER, WAVE_TIMER

    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    variables = variables_by_name(data)
    waves = balance()["waves"]
    [choice] = effects(triggers["game.choice.warning"], "display_timer")
    assert choice["timer"] == CHOICE_TIMER != WAVE_TIMER
    for number, wave in enumerate(waves, 1):
        trigger = triggers[f"game.wave.{number}.warning"]
        if number == 1:
            # The script asks for the first wave's countdown as preparation begins. A selection
            # cuts the choice countdown short, and DE's Reset Timer keeps a running timer's
            # text, so that timer is cleared first.
            assert trigger["looping"]
            assert requested(trigger, variables["game.wave_display"]) == 4
            assert [attr_int(e, "timer") for e in effects(trigger, "clear_timer")] == [CHOICE_TIMER]
            kinds = [e["type"] for e in trigger["effects"]]
            assert kinds.index("clear_timer") < kinds.index("display_timer")
            [reset] = effects(trigger, "change_variable")
            assert (reset["variable"], reset["quantity"], reset["operation"]) == (
                variables["game.wave_display"],
                0,
                SET,
            )
        else:
            assert not trigger["looping"]
            assert requested(trigger, variables["game.phase"]) == 2
            assert compared(trigger, variables["game.wave"]) == (EQUAL, number - 2)
        [timer] = effects(trigger, "display_timer")
        seconds = (
            balance()["preparation_seconds"] if number == 1 else balance()["intermission_seconds"]
        )
        assert (timer["display_time"], timer["timer"]) == (seconds, WAVE_TIMER)
        assert wave["key"] in timer["message"] and "%d" in timer["message"]


def test_no_acting_trigger_compares_a_variable_to_minus_one(game_build: GameBuild) -> None:
    """DE parks a trigger whose Variable Value condition has quantity -1 and never fires it;
    only the objectives that just display their text rely on that."""
    for trigger in snapshot(game_build)["triggers"]:
        if trigger["display_as_objective"] and not trigger["effects"]:
            continue
        for c in trigger["conditions"]:
            if c["type"] == "variable_value":
                assert attr_int(c["attributes"], "quantity") != -1, trigger["name"]


def test_no_flat_income_or_forced_population(game_build: GameBuild) -> None:
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    assert not any(name.endswith(".income") for name in triggers)
    for trigger in data["triggers"]:
        # The population purchase, and a civilization profile applied once, may add headroom;
        # the lane's setup only sets the starting room.
        if trigger["name"].endswith(".buy.population") or ".profile." in trigger["name"]:
            continue
        for e in effects(trigger, "modify_resource"):
            if e["tribute_list"] == 4:
                assert trigger["name"].endswith(".initialize") and e["operation"] == SET
                assert e["quantity"] == balance()["economy"]["starting_population"]


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
        labels = {
            key: (
                names[label_near(transfer.pad[0], transfer.pad[1])],
                names[label_near(*transfer.arrival)],
            )
            for key, transfer in lane.sites.transfers.items()
        }
        # Bought building villagers appear on the build arrival itself, bought resource
        # villagers two tiles from the economy arrival.
        assert labels == {
            "build": (
                "Villager on the flag: moves to the build area",
                "Arrivals from the resource area, and bought villagers",
            ),
            "economy": (
                "Villager on the flag: moves to the resource area",
                "Arrivals from the build area; bought villagers nearby",
            ),
            "north": (
                "Villager on the flag: moves to the north build rows",
                "Arrivals from the south build rows",
            ),
            "south": (
                "Villager on the flag: moves to the south build rows",
                "Arrivals from the north build rows",
            ),
        }
        # Short enough to read at a glance when the relic is selected.
        assert max(len(text) for pair in labels.values() for text in pair) <= 55
    assert names[21492] == "Based on Ancient TD v5.3 by DRAX6869 / DRAX"


@pytest.mark.parametrize("player", PLAYERS)
def test_transfer_flags_name_their_destination_and_their_relics_point_at_them(
    game_build: GameBuild, player: int
) -> None:
    """The relic beside a transfer pad stands in a sealed pocket; the flag on the pad's one
    tile is where a villager goes. Compass words would mislead in DE's isometric view."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.config import load_lanes
    from ancienttdde.game.labels import TRANSFER_AREAS
    from ancienttdde.scenario.objects import marker_flags

    data = snapshot(game_build)
    units = {u["reference_id"]: u for u in data["units"]}
    names = {
        attr_list(rename, "selected_object_ids")[0]: attr_text(rename, "message")
        for rename in effects(triggers_by_name(data)["game.labels"], "change_object_name")
    }
    lane = load_lanes(object_value(anchors(game_build), "anchors"))[player - 1]
    for key, transfer in lane.sites.transfers.items():
        destination = TRANSFER_AREAS[key][0]
        x, y = transfer.pad[0], transfer.pad[1]
        [flag] = [
            u
            for u in units.values()
            if u["unit_const"] in marker_flags()
            and (math.floor(u["x"]), math.floor(u["y"])) == (x, y)
        ]
        assert flag.get("caption_string") == f"Transfer pad: to the {destination}", key
        [relic] = [
            ref
            for ref, u in units.items()
            if u["unit_const"] == RELIC and math.dist((u["x"], u["y"]), (x + 0.5, y + 0.5)) <= 2.5
        ]
        assert names[relic] == f"Villager on the flag: moves to the {destination}", key


def test_pad_exhibits_stay_where_the_map_puts_them_with_their_captions(
    game_build: GameBuild,
) -> None:
    """The original's exhibits stay on their map spots and a King is created beside each new
    pad; each carries its purchases' tags as the caption DE draws above it."""
    from ancienttdde.game.catalog import display_captions, load_shop
    from ancienttdde.game.config import load_balance

    output, _ = game_build
    data = snapshot(game_build)
    units = {u["reference_id"]: u for u in data["units"]}
    spots = {u["reference_id"]: (u["x"], u["y"]) for u in cached_json(output / "map.json")["units"]}
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
            assert (unit["x"], unit["y"]) == spots[purchase.display], purchase.key
        else:
            [king] = [
                u
                for u in units.values()
                if u["unit_const"] == KING and (u["x"], u["y"]) == purchase.display_at
            ]
            assert king["player_id"] == 0 and king.get("caption_string") == purchase.tag
    assert tags[shop.get("tower_attack_4").display or 0] == "+4 attack: 1 King"


@pytest.mark.parametrize("player", PLAYERS)
def test_creation_tiles_hold_only_the_originals_arrival_flags(
    game_build: GameBuild, player: int
) -> None:
    """XS creates Kings, bought units and trebuchets on these tiles, and native triggers a
    profile's starting towers. The original's flags stay on the transfer arrivals and the
    bought villagers' spots: villagers are teleported there, or created without a collision
    check. Every other creation tile holds nothing."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.spawns import creation_tiles
    from ancienttdde.scenario.objects import marker_flags

    output, _ = game_build
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
    assert {tile for pair in lane.sites.towers for tile in pair} <= tiles
    marked = {transfer.arrival for transfer in lane.sites.transfers.values()}
    marked |= {spot for spawn in lane.sites.villagers.values() for spot in spawn.tiles}
    assert marked <= tiles
    standing: dict[tuple[int, int], list[MapUnit]] = {}
    for u in snapshot(game_build)["units"]:
        spot = (math.floor(u["x"]), math.floor(u["y"]))
        if spot in tiles:
            standing.setdefault(spot, []).append(u)
    assert set(standing) == marked
    placed = {u["reference_id"]: u for u in cached_json(output / "map.json")["units"]}
    for spot, units in standing.items():
        [flag] = units
        assert flag["unit_const"] in marker_flags(), spot
        # The original's own flag, never one the build made.
        original = placed[flag["reference_id"]]
        assert original["unit_const"] == flag["unit_const"], spot
        assert (math.floor(original["x"]), math.floor(original["y"])) == spot
    # The transfer pads keep their flags: players stand villagers on them.
    flags = {
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in snapshot(game_build)["units"]
        if u["unit_const"] in marker_flags()
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
    waiting, spawning = triggers["game.status.next"], triggers["game.status.spawning"]
    for status in (waiting, spawning):
        assert status["display_as_objective"]
        assert f"<Variable {variables['game.display_wave']}>" in status["short_description"]
        assert f"<Variable {variables['game.countdown']}>" in status["short_description"]
    for player in PLAYERS:
        lane = triggers[f"lane.p{player}.status"]
        assert lane["display_as_objective"]
        lives = variables[f"lane.p{player}.lives"]
        assert f"<Variable {lives}>/{balance()['lives']}" in lane["short_description"]
    # Never fired: they only display their variables. The countdown to the next wave and the
    # lives show from the start; the wave's spawning line waits for its first wave.
    for shown in [waiting, spawning] + [triggers[f"lane.p{p}.status"] for p in PLAYERS]:
        assert shown["display_on_screen"] and not shown["effects"]
        assert shown["enabled"] == (shown is not spawning)
        assert [(c["type"], c["attributes"]["quantity"]) for c in shown["conditions"]] == [
            ("variable_value", -1)
        ]


def test_the_status_line_switches_between_the_wait_and_the_wave(game_build: GameBuild) -> None:
    """Before a wave the status counts down to it; while a wave spawns, it counts down the
    spawning. The triggers that start each wait and each wave switch the lines."""
    data = snapshot(game_build)
    triggers = triggers_by_name(data)
    waiting = triggers["game.status.next"]["id"]
    spawning = triggers["game.status.spawning"]["id"]

    def switched(name: str) -> tuple[list[int], list[int]]:
        trigger = triggers[name]
        return (
            [attr_int(e, "trigger_id") for e in effects(trigger, "activate_trigger")],
            [attr_int(e, "trigger_id") for e in effects(trigger, "deactivate_trigger")],
        )

    assert switched("game.wave.timer.clear") == ([spawning], [waiting])
    waits = ["game.wave.endless.warning"]
    waits += [f"game.wave.{number}.warning" for number in range(1, len(balance()["waves"]) + 1)]
    for name in waits:
        assert switched(name) == ([waiting], [spawning]), name


@pytest.mark.parametrize("player", PLAYERS)
def test_kings_and_monks_take_no_population(game_build: GameBuild, player: int) -> None:
    """The lane's setup sets the population cost of its Kings and monks to zero, so the shop's
    currency and the relics' monks never hold a purchase back."""
    init = triggers_by_name(snapshot(game_build))[f"lane.p{player}.initialize"]
    freed = {
        e["object_list_unit_id"]: (e["operation"], e["quantity"])
        for e in effects(init, "modify_attribute")
        if e["object_attributes"] == POPULATION and e["source_player"] == player
    }
    assert freed == {KING: (SET, 0), MONK: (SET, 0), MONK_WITH_RELIC: (SET, 0)}
    # Before the lane's room is set, so the Kings on the map never land on top of it.
    order = [
        (e["type"], e["attributes"].get("object_attributes"), e["attributes"].get("tribute_list"))
        for e in init["effects"]
    ]
    room = order.index(("modify_resource", None, 4))
    zeroed = [i for i, o in enumerate(order) if o == ("modify_attribute", POPULATION, None)]
    assert len(zeroed) == 3 and max(zeroed) < room


@pytest.mark.parametrize("player", PLAYERS)
def test_population_starts_with_the_contents_room_for_every_lane(
    game_build: GameBuild, player: int
) -> None:
    init = triggers_by_name(snapshot(game_build))[f"lane.p{player}.initialize"]
    headroom = [
        (e["operation"], e["quantity"])
        for e in effects(init, "modify_resource")
        if e["tribute_list"] == 4 and e["source_player"] == player
    ]
    # Civilization bonuses that start with population are levelled to the same room; only
    # purchases and the profiles add more.
    assert headroom == [(SET, balance()["economy"]["starting_population"])]


def test_the_model_assumes_the_gold_and_stone_miners_a_lane_starts_with(
    game_build: GameBuild,
) -> None:
    """A lane's resource-area villagers start gathering the deposit beside them; the baseline
    income counts exactly those on gold and on stone."""
    from ancienttdde.game.balance import Assumptions, load_inputs
    from ancienttdde.game.economy import GATHER_REACH

    data = snapshot(game_build)
    x1, y1, x2, y2 = load_inputs(ROOT).lanes[0].economy
    deposits = [u for u in data["units"] if u["unit_const"] in (GOLD_MINE, STONE_MINE)]
    miners = {GOLD_MINE: 0, STONE_MINE: 0}
    for unit in data["units"]:
        if unit["player_id"] != 1 or unit["unit_const"] not in (VILLAGER, FEMALE_VILLAGER):
            continue
        if not (x1 <= unit["x"] <= x2 + 1 and y1 <= unit["y"] <= y2 + 1):
            continue
        nearest = min(deposits, key=lambda d: math.dist((d["x"], d["y"]), (unit["x"], unit["y"])))
        if math.dist((nearest["x"], nearest["y"]), (unit["x"], unit["y"])) <= GATHER_REACH:
            miners[nearest["unit_const"]] += 1
    assumptions = Assumptions()
    assert miners == {
        GOLD_MINE: assumptions.gold_villagers,
        STONE_MINE: assumptions.stone_villagers,
    }
