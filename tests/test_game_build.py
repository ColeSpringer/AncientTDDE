"""Reload playable artifacts and reject changes hidden behind edited hashes."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from conftest import (
    KING,
    ROOT,
    GameBuild,
    attr_int,
    attr_list,
    attr_number,
    load_scenario,
    new_scenario,
    rehash_artifacts,
    save_scenario,
)
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.common.data import asset_text
from ancienttdde.map.geometry import Position
from ancienttdde.scenario.xs import xs_checker

MOVE = 1
NO_ATTACK_STANCE = 3


def test_playable_map_is_self_contained_and_verifies_after_reload(game_build: GameBuild) -> None:
    from ancienttdde.game.build import verify_game

    output, first = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    assert snapshot["map"]["width"] == 200
    assert snapshot["dependencies"]["external_xs"] == ""
    assert snapshot["dependencies"]["ai_files"] == 0
    assert snapshot["embedded_ai"][7]["script"].strip()
    assert snapshot["players"][8]["human"] is False
    assert all(p["human"] for p in snapshot["players"][1:8])
    assert not snapshot["options"]["victory_custom_conditions_required"]
    assert all(value == 0 for value in snapshot["global_victory"].values())
    assert {v["name"] for v in snapshot["variables"]} >= {"game.phase", "lane.p7.lives"}
    assert verify_game(output, ROOT) == first


def test_the_mod_folder_holds_the_same_scenario(game_build: GameBuild, tmp_path: Path) -> None:
    import shutil

    from ancienttdde.game.build import MOD_SCENARIO, SCENARIO_NAME, read_manifest

    output, _ = game_build
    assert MOD_SCENARIO == "Ancient TD DE/resources/_common/scenario/ancient-td-de.aoe2scenario"
    assert (output / MOD_SCENARIO).read_bytes() == (output / SCENARIO_NAME).read_bytes()
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    copy = edited / MOD_SCENARIO
    copy.write_bytes(copy.read_bytes() + b"\0")
    rehash_artifacts(edited, MOD_SCENARIO)
    with pytest.raises(ValueError, match="mod copy differs from the scenario"):
        read_manifest(edited / "manifest.json")


def test_native_actions_acknowledge_only_live_lane_requests(game_build: GameBuild) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        for suffix in (
            "initialize",
            "king",
            "buy.tower_attack_4",
            "transfer.build",
            "bonus.gold",
            *(f"spawned.e{enemy}" for enemy in range(1, 9) if enemy != player),
            *(f"enemy.e{enemy}" for enemy in range(1, 9) if enemy != player),
        ):
            trigger = triggers[f"lane.p{player}.{suffix}"]
            assert not trigger["execute_on_load"]
            assert any(
                c["type"] == "variable_value"
                and c["attributes"]["variable"] == variables[f"lane.p{player}.active"]
                and c["attributes"]["quantity"] == 1
                for c in trigger["conditions"]
            )
        init = triggers[f"lane.p{player}.initialize"]
        assert any(
            e["type"] == "change_variable"
            and e["attributes"]["variable"] == variables[f"lane.p{player}.initialized"]
            for e in init["effects"]
        )
    # Logic triggers stay enabled and are gated by variables; only display-only objectives
    # are revealed by activation. A cleared lane's cleanup deactivates that lane's other
    # triggers, the game.hide triggers deactivate display-only objectives, and the wave
    # triggers switch the status line between the wait and the wave.
    objectives = {
        t["id"] for t in snapshot["triggers"] if t["display_as_objective"] and not t["effects"]
    }
    by_id = {t["id"]: t for t in snapshot["triggers"]}
    for trigger in snapshot["triggers"]:
        for change in trigger["effects"]:
            if change["type"] == "activate_trigger":
                assert change["attributes"]["trigger_id"] in objectives
            if change["type"] == "deactivate_trigger":
                target = by_id[change["attributes"]["trigger_id"]]
                if trigger["name"].startswith("game.hide."):
                    assert target["id"] in objectives
                    continue
                if trigger["name"].startswith("game.wave."):
                    assert target["name"] in ("game.status.next", "game.status.spawning")
                    continue
                lane = re.fullmatch(r"(lane\.p[1-7])\.cleanup", trigger["name"])
                assert lane is not None, trigger["name"]
                assert target["name"].startswith(f"{lane[1]}.") and target is not trigger
    enemy = [u for u in snapshot["units"] if u["player_id"] == 8]
    assert any(u["unit_const"] == 434 for u in enemy)


def test_a_cleared_lanes_cleanup_ends_exactly_its_own_lanes_other_triggers(
    game_build: GameBuild,
) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    owned = {
        player: {t["id"] for t in snapshot["triggers"] if t["name"].startswith(f"lane.p{player}.")}
        for player in range(1, 8)
    }
    for player in range(1, 8):
        cleanup = triggers[f"lane.p{player}.cleanup"]
        ended = [
            e["attributes"]["trigger_id"]
            for e in cleanup["effects"]
            if e["type"] == "deactivate_trigger"
        ]
        assert len(ended) == len(set(ended))
        assert set(ended) == owned[player] - {cleanup["id"]}
        assert triggers[f"lane.p{player}.status"]["id"] in ended
        for other in range(1, 8):
            if other != player:
                assert owned[other].isdisjoint(ended)
        # The cleanup clears the lane before ending the rest of its triggers.
        kinds = [e["type"] for e in cleanup["effects"]]
        assert kinds.index("script_call") < kinds.index("deactivate_trigger")


def test_every_pad_shows_one_flag_per_king_of_its_price(game_build: GameBuild) -> None:
    """The map's flags mark where a pad's Kings stand: one Gaia flag a tile and one flagged
    tile per King of the price, the siege's base price."""
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance
    from ancienttdde.scenario.objects import marker_flags

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    anchors = json.loads((output / "map.json").read_text())["anchors"]
    balance = load_balance(ROOT / "content/balance/game.json")
    families = [name for name, _ in balance.towers.families]
    catalog = load_shop(ROOT / "content/balance/shop.json", anchors, families)
    flags = [u for u in snapshot["units"] if u["unit_const"] in marker_flags()]
    for purchase in catalog.purchases:
        x1, y1, x2, y2 = purchase.pad_region
        marked = [u for u in flags if x1 <= u["x"] < x2 + 1 and y1 <= u["y"] < y2 + 1]
        tiles = {(int(u["x"]), int(u["y"])) for u in marked}
        assert len(marked) == len(tiles) == purchase.kings, purchase.key
        assert all(u["player_id"] == 0 for u in marked), purchase.key


def column(x: int, rows: range) -> set[tuple[int, int]]:
    return {(x, y) for y in rows}


# The side each pad is entered from, read off the map; every other pad opens to the north.
ENTERED_FROM_WEST = {
    "tower_attack_255",
    "tower_attack_750",
    "bombard_attack_400",
    "wood_2000",
    "king_every_150",
    "king_every_minute",
    "gold_1000",
    "gold_450",
    "gold_175",
    "land_raider",
    "naval_raider",
    "siege",
}
ENTERED_FROM_EAST = {
    "tower_attack_4",
    "tower_attack_10",
    "tower_attack_25",
    "tower_attack_50",
    "tower_attack_100",
    "tower_attack_170",
    "stone_1500",
    "stone_800",
    "stone_375",
    "attack_1_every_30",
    "attack_3_every_30",
    "relic_enclosure",
}
# Pads whose flags differ from the map's: priced differently from the original, or new.
FAR_END_FLAGS = {
    "third_row": column(162, range(47, 50)),
    "fourth_row": column(164, range(47, 50)),
    "naval_raider": column(169, range(20, 23)),
    "siege": column(169, range(24, 34)) | column(168, range(24, 29)),
    "land_raider": column(169, range(36, 39)),
    "castle": {(150, 49)},
    "king_every_150": column(130, range(18, 23)) | column(129, range(18, 21)),
    "king_every_minute": column(130, range(24, 30))
    | column(129, range(24, 30))
    | column(128, range(24, 30))
    | column(127, range(24, 26)),
    "gold_1000": column(130, range(31, 33)) | column(129, range(31, 33)),
    "gold_450": column(130, range(34, 36)),
    "stone_800": column(138, range(30, 33)) | column(139, range(30, 32)),
    "stone_375": column(138, range(34, 36)),
    "attack_1_every_30": column(138, range(25, 29)),
}


def test_pad_flags_fill_from_the_end_farthest_from_the_entrance(game_build: GameBuild) -> None:
    """Like the original's, a pad's flags fill whole rows from its far end towards the
    entrance; a pad whose map flags already do keeps them."""
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance
    from ancienttdde.map.geometry import cells, footprint
    from ancienttdde.scenario.objects import marker_flags

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    data = json.loads((output / "map.json").read_text())
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {row["stock_id"]: row.get("blocking_size", 0) for row in config["objects"]}
    balance = load_balance(ROOT / "content/balance/game.json")
    families = [name for name, _ in balance.towers.families]
    catalog = load_shop(ROOT / "content/balance/shop.json", data["anchors"], families)

    def flagged(units: list[dict[str, Any]]) -> set[tuple[int, int]]:
        return {(int(u["x"]), int(u["y"])) for u in units if u["unit_const"] in marker_flags()}

    built, original = flagged(snapshot["units"]), flagged(data["units"])
    blocked = {
        cell for u in snapshot["units"] for cell in footprint(u, sizes.get(u["unit_const"], 0))
    }
    for purchase in catalog.purchases:
        region = cells(purchase.pad_region)
        expected = FAR_END_FLAGS.get(purchase.key, original & region)
        assert built & region == expected, purchase.key
        # Rows of standable tiles, the farthest from the entrance first.
        open_tiles = region - blocked
        if purchase.key in ENTERED_FROM_WEST:
            depth = {tile: -tile[0] for tile in open_tiles}
        elif purchase.key in ENTERED_FROM_EAST:
            depth = {tile: tile[0] for tile in open_tiles}
        else:
            depth = {tile: -tile[1] for tile in open_tiles}
        shallowest = max(depth[tile] for tile in expected)
        assert all(tile in expected for tile in open_tiles if depth[tile] < shallowest), (
            purchase.key
        )


def test_a_pad_needs_one_entrance_and_its_flags_fill_whole_rows_from_the_far_end() -> None:
    from ancienttdde.game.construct import far_end, pad_rows

    region = (10, 10, 12, 11)
    open_tiles = {(x, y) for x in range(10, 13) for y in range(10, 12)}
    # Only the west side is free, so the rows run from x = 12 back to x = 10.
    walls = {(x, y) for x in range(9, 14) for y in (9, 12)} | {(13, 10), (13, 11)}
    rows = pad_rows("test", region, open_tiles, walls)
    assert rows == [[(12, 10), (12, 11)], [(11, 10), (11, 11)], [(10, 10), (10, 11)]]
    assert far_end(rows, 3) == {(12, 10), (12, 11), (11, 10)}
    # A lone flag takes its row's middle tile, the first of two.
    assert far_end(rows, 1) == {(12, 10)}
    assert far_end([[(1, 5), (2, 5), (3, 5)]], 1) == {(2, 5)}
    # Open on every side: the north and south edges tie.
    with pytest.raises(ValueError, match="test pad has no single entrance"):
        pad_rows("test", region, open_tiles, set())


def test_only_what_stands_in_the_way_closes_a_pads_side() -> None:
    """Marker flags have no collision, so they close no pad's side; a unit standing there or
    a blocking footprint does."""
    from ancienttdde.game.construct import entrance_obstacles
    from ancienttdde.game.triggers import Game

    scenario = new_scenario()
    for unit_const, x in ((601, 1.5), (KING, 3.5)):
        scenario.unit_manager.add_unit(player=0, unit_const=unit_const, x=x, y=1.5)
    assert entrance_obstacles(Game(scenario), {(9, 9)}) == {(3, 1), (9, 9)}


def test_ai_fillers_use_embedded_passive_ai(game_build: GameBuild) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    passive = asset_text("passive.per").strip()
    assert all(ai["script"].strip() == passive for ai in snapshot["embedded_ai"])
    assert all(p["lock_personality"] for p in snapshot["players"][1:])
    scenario = load_scenario(output / "ancient-td-de.aoe2scenario")
    assert all(p.lock_personality for p in scenario.player_manager.players[1:])


def test_the_runtime_checks_cleanly_against_the_build_prelude(
    game_build: GameBuild, tmp_path: Path
) -> None:
    from ancienttdde.game.build import PRELUDE

    output, manifest = game_build
    assert PRELUDE in {record["path"] for record in manifest["artifacts"]}
    snapshot = json.loads((output / "scenario.json").read_text())
    scripts = [
        effect["attributes"]["message"]
        for trigger in snapshot["triggers"]
        for effect in trigger["effects"]
        if effect["type"] == "script_call"
    ]
    # The prelude declares what the scenario embeds before the shared runtime. xs-check sees
    # constants from another file only when they are extern.
    prelude = (output / PRELUDE).read_text(encoding="utf-8")
    declarations = prelude.replace("extern const int ", "const int ")
    assert declarations != prelude
    text = asset_text("runtime.xs")
    assert any(declarations + text in script for script in scripts)
    runtime = tmp_path / "runtime.xs"
    runtime.write_text(text, encoding="utf-8")
    scenario = new_scenario()
    checker = scenario.xs_manager.xs_check
    checker.additional_args = ["--extra-prelude-path", str(output / PRELUDE)]
    with xs_checker(scenario):
        # The parser's check, which the build runs, also fails on warnings.
        checker.validate(runtime, show_tmpfile=False)


def test_initial_traders_receive_orders_to_their_own_partner(game_build: GameBuild) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    anchors = json.loads((output / "map.json").read_text())["anchors"]
    units = {u["reference_id"]: u for u in snapshot["units"]}
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        init = triggers[f"lane.p{player}.initialize"]
        for route, kind, endpoint, count in (("land", 128, 84, 8), ("water", 17, 45, 4)):
            traders = {
                u["reference_id"]
                for u in units.values()
                if u["player_id"] == player and u["unit_const"] == kind
            }
            assert len(traders) == count
            partner = anchors[f"trade.{route}.p{player}.partner"]["reference_id"]
            assert units[partner]["player_id"] == 0
            assert units[partner]["unit_const"] == endpoint
            orders = [
                e["attributes"]
                for e in init["effects"]
                if e["type"] == "task_object"
                and e["attributes"]["location_object_reference"] == partner
            ]
            assert len(orders) == 1
            assert orders[0]["source_player"] == player
            assert orders[0]["action_type"] == 0
            assert set(orders[0]["selected_object_ids"]) == traders


def test_lanes_own_no_towers_until_their_profile_applies(game_build: GameBuild) -> None:
    """The original's lanes own no tower at the start; a civilization profile's starting
    towers arrive by its native trigger, and each lane may build Watch Towers for the rest."""
    from ancienttdde.game.config import load_balance

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    towers = load_balance(ROOT / "content/balance/game.json").towers
    families = {unit for name, _ in towers.families for unit in towers.family_ids(name)}
    assert 79 in families
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        created = [
            e["attributes"]["object_list_unit_id"]
            for e in triggers[f"lane.p{player}.initialize"]["effects"]
            if e["type"] == "create_object"
        ]
        assert not set(created) & families, player
        enabled = [
            e["attributes"]["object_list_unit_id"]
            for e in triggers[f"lane.p{player}.initialize"]["effects"]
            if e["type"] == "enable_disable_object" and e["attributes"]["enabled"] == 1
        ]
        assert enabled == [79], player
    placed = [u for u in snapshot["units"] if 1 <= u["player_id"] <= 7]
    assert not [u for u in placed if u["unit_const"] in families]


def test_the_enemy_treats_lanes_as_allies_and_lanes_treat_it_as_an_enemy(
    game_build: GameBuild,
) -> None:
    """The original's one-way alliance: the enemy's units attack nothing while every lane's
    towers fire at them, and they walk at their stock speed. The map presets it for the enemy
    in slot 8; a trigger per number the enemy may hold sets it once the XS has chosen. Each
    new batch takes the No Attack stance in the spawn column, so a unit a tower hits does not
    turn to answer it."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.config import load_lanes

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    players = snapshot["players"]
    assert [p["player_id"] for p in players[:9]] == list(range(9))
    assert players[8]["diplomacy"][:7] == [DiplomacyState.ALLY] * 7
    for player in range(1, 8):
        assert players[player]["diplomacy"][7] == DiplomacyState.ENEMY
    for lane_number in range(1, 8):
        for enemy in range(1, 9):
            if enemy == lane_number:
                assert f"lane.p{lane_number}.enemy.e{enemy}" not in triggers
                continue
            trigger = triggers[f"lane.p{lane_number}.enemy.e{enemy}"]
            assert not trigger["looping"]
            requested = {
                c["attributes"]["variable"]: c["attributes"]["quantity"]
                for c in trigger["conditions"]
                if c["type"] == "variable_value"
            }
            assert len(trigger["conditions"]) == 2
            assert requested == {
                variables["game.enemy"]: enemy,
                variables[f"lane.p{lane_number}.active"]: 1,
            }
            stances_set = {
                (e["attributes"]["source_player"], e["attributes"]["target_player"]): e[
                    "attributes"
                ]["diplomacy"]
                for e in trigger["effects"]
                if e["type"] == "change_diplomacy"
            }
            assert stances_set == {
                (lane_number, enemy): DiplomacyState.ENEMY,
                (enemy, lane_number): DiplomacyState.ALLY,
            }
            assert len(trigger["effects"]) == 2
    anchors = json.loads((output / "map.json").read_text())["anchors"]
    stances: dict[str, list[dict[str, object]]] = {}
    expected: list[str] = []
    for lane in load_lanes(object_value(anchors, "anchors")):
        _, y1, _, y2 = lane.path
        assert f"lane.p{lane.player}.spawned" not in triggers
        for enemy in range(1, 9):
            if enemy == lane.player:
                assert f"lane.p{lane.player}.spawned.e{enemy}" not in triggers
                continue
            spawned = triggers[f"lane.p{lane.player}.spawned.e{enemy}"]
            expected.append(spawned["name"])
            assert [
                c["attributes"]["quantity"]
                for c in spawned["conditions"]
                if c["attributes"]["variable"] == variables["game.enemy"]
            ] == [enemy]
            kinds = [e["type"] for e in spawned["effects"]]
            assert kinds.count("change_object_stance") == 1
            assert kinds.index("change_object_stance") < kinds.index("task_object")
            [stance] = [
                e["attributes"] for e in spawned["effects"] if e["type"] == "change_object_stance"
            ]
            assert (stance["source_player"], stance["attack_stance"]) == (enemy, NO_ATTACK_STANCE)
            assert (
                stance["area_x1"],
                stance["area_y1"],
                stance["area_x2"],
                stance["area_y2"],
            ) == (lane.spawn_x, y1, lane.spawn_x + 1, y2)
    for trigger in snapshot["triggers"]:
        for change in trigger["effects"]:
            if change["type"] == "change_object_stance":
                stances.setdefault(trigger["name"], []).append(change["attributes"])
            attributes = change["attributes"]
            # The protected keeper King is the one enemy unit held in place.
            if (
                change["type"] == "modify_attribute"
                and attributes["source_player"] == 8
                and attributes["object_list_unit_id"] != KING
            ):
                assert attributes["object_attributes"] != ObjectAttribute.MOVEMENT_SPEED
    assert sorted(stances) == sorted(expected)


def test_each_lane_sends_the_batches_the_xs_creates_down_its_rows(game_build: GameBuild) -> None:
    """The XS creates every batch itself; no trigger creates an enemy. Each lane's
    acknowledgment orders the new batch in the spawn column, and its ten-second route keeps
    every enemy in the lane walking, each row band to its own exit tile, so pairs created side
    by side stay side by side."""
    from ancienttdde.common.data import object_value
    from ancienttdde.game.config import load_lanes

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    lane_waves = [
        t for t in snapshot["triggers"] if t["name"].startswith("lane.") and ".wave." in t["name"]
    ]
    assert not lane_waves
    for trigger in snapshot["triggers"]:
        for change in trigger["effects"]:
            if change["type"] == "create_object":
                assert change["attributes"]["source_player"] != 8
    anchors = json.loads((output / "map.json").read_text())["anchors"]
    for lane in load_lanes(object_value(anchors, "anchors")):
        x1, y1, x2, y2 = lane.path
        center = lane.center_y
        assert f"lane.p{lane.player}.route" not in triggers
        for enemy in range(1, 9):
            if enemy == lane.player:
                assert f"lane.p{lane.player}.route.e{enemy}" not in triggers
                continue
            # The XS creates each batch at the spawn tile's center.
            for name, columns in (
                (f"lane.p{lane.player}.spawned.e{enemy}", (lane.spawn_x, lane.spawn_x + 1)),
                (f"lane.p{lane.player}.route.e{enemy}", (x1, x2)),
            ):
                trigger = triggers[name]
                assert trigger["looping"]
                orders = [e["attributes"] for e in trigger["effects"] if e["type"] == "task_object"]
                bands = [
                    (o["area_y1"], o["area_y2"], o["location_x"], o["location_y"]) for o in orders
                ]
                assert bands == [
                    (y1, center - 1, lane.exit_x, center - 1),
                    (center, center, lane.exit_x, center),
                    (center + 1, y2, lane.exit_x, center + 1),
                ]
                assert all(o["source_player"] == enemy and o["action_type"] == MOVE for o in orders)
                assert all((o["area_x1"], o["area_x2"]) == columns for o in orders)
                requested = {
                    c["attributes"]["variable"]: c["attributes"]["quantity"]
                    for c in trigger["conditions"]
                    if c["type"] == "variable_value"
                }
                assert requested[variables["game.enemy"]] == enemy
                assert requested[variables[f"lane.p{lane.player}.active"]] == 1
            route = triggers[f"lane.p{lane.player}.route.e{enemy}"]
            assert [
                c["attributes"]["timer"] for c in route["conditions"] if c["type"] == "timer"
            ] == [10]
            spawned = triggers[f"lane.p{lane.player}.spawned.e{enemy}"]
            requested = {
                c["attributes"]["variable"]: c["attributes"]["quantity"]
                for c in spawned["conditions"]
                if c["type"] == "variable_value"
            }
            assert requested[variables[f"lane.p{lane.player}.spawn"]] == 1
            [cleared] = [
                e["attributes"] for e in spawned["effects"] if e["type"] == "change_variable"
            ]
            assert (cleared["variable"], cleared["quantity"]) == (
                variables[f"lane.p{lane.player}.spawn"],
                0,
            )


def test_results_go_to_the_winning_lane_or_to_whichever_number_the_enemy_holds(
    game_build: GameBuild,
) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    declared = {
        name: trigger
        for name, trigger in triggers.items()
        if any(e["type"] == "declare_victory" for e in trigger["effects"])
    }
    assert set(declared) == {f"game.result.p{p}" for p in range(1, 8)} | {
        f"game.result.e{e}" for e in range(1, 9)
    }
    for name, trigger in declared.items():
        player = int(name[-1])
        phase = 6 if name.startswith("game.result.p") else 8
        requested = {
            c["attributes"]["variable"]: c["attributes"]["quantity"]
            for c in trigger["conditions"]
            if c["type"] == "variable_value"
        }
        assert requested == {variables["game.winner"]: player, variables["game.phase"]: phase}
        [victory] = [e["attributes"] for e in trigger["effects"] if e["type"] == "declare_victory"]
        assert victory["source_player"] == player


@pytest.mark.parametrize("change", ["resource_bonus", "ai_personality"])
def test_validation_rejects_tampered_logic_even_with_updated_hashes(
    game_build: GameBuild, tmp_path: Path, change: str
) -> None:
    import shutil

    from ancienttdde.game.build import ARTIFACTS, MOD_SCENARIO, compare_game
    from ancienttdde.scenario.inspect import inspect_scenario
    from ancienttdde.scenario.snapshot import content_digest

    output, _ = game_build
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    path = edited / "ancient-td-de.aoe2scenario"
    scenario = load_scenario(path)
    if change == "resource_bonus":
        scenario.trigger_manager.add_trigger("Unexpected bonus").new_effect.modify_resource(
            source_player=1, tribute_list=3, quantity=9999, operation=1
        )
    else:
        scenario.player_manager.players[1].lock_personality = False
    with xs_checker(scenario):
        save_scenario(scenario, edited / "changed.aoe2scenario")
    (edited / "changed.aoe2scenario").replace(path)
    shutil.copyfile(path, edited / MOD_SCENARIO)
    snapshot = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    (edited / "scenario.json").write_text(json.dumps(snapshot))
    manifest = json.loads((edited / "manifest.json").read_text())
    manifest["normalized_sha256"] = content_digest(snapshot)
    (edited / "manifest.json").write_text(json.dumps(manifest))
    rehash_artifacts(edited, *ARTIFACTS)
    # The edited copy is internally consistent; only a build of the current definitions
    # exposes the change.
    with pytest.raises(ValueError, match="current definitions"):
        compare_game(edited, output)


def test_validation_compares_the_build_with_a_build_of_current_definitions(
    game_build: GameBuild, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from ancienttdde.game import build
    from ancienttdde.scenario.inspect import inspect_scenario
    from ancienttdde.scenario.snapshot import content_digest

    output, _ = game_build
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    path = edited / "ancient-td-de.aoe2scenario"
    scenario = load_scenario(path)
    scenario.trigger_manager.add_trigger("Unexpected bonus").new_effect.modify_resource(
        source_player=1, tribute_list=3, quantity=9999, operation=1
    )
    with xs_checker(scenario):
        save_scenario(scenario, edited / "changed.aoe2scenario")
    (edited / "changed.aoe2scenario").replace(path)
    shutil.copyfile(path, edited / build.MOD_SCENARIO)
    snapshot = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    (edited / "scenario.json").write_text(json.dumps(snapshot))
    manifest = json.loads((edited / "manifest.json").read_text())
    manifest["normalized_sha256"] = content_digest(snapshot)
    (edited / "manifest.json").write_text(json.dumps(manifest))
    rehash_artifacts(edited, "ancient-td-de.aoe2scenario", build.MOD_SCENARIO, "scenario.json")

    def rebuild(root: Path, expected: Path | None = None) -> Path:
        # The session build is a build of the current definitions; copying it saves a rebuild.
        assert expected is not None
        shutil.copytree(output, expected, dirs_exist_ok=True)
        return expected

    monkeypatch.setattr(build, "build_game", rebuild)
    # The edited copy is internally consistent, so only the comparison can reject it.
    build.verify_game(edited, ROOT)
    with pytest.raises(ValueError, match="Game logic differs from current definitions"):
        build.validate_game(edited, ROOT)


def test_validation_rejects_a_prelude_that_differs_from_current_definitions(
    game_build: GameBuild, tmp_path: Path
) -> None:
    import shutil

    from ancienttdde.game.build import PRELUDE, compare_game

    output, _ = game_build
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    prelude = edited / PRELUDE
    prelude.write_text(prelude.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    rehash_artifacts(edited, PRELUDE)
    message = f"Game sidecar differs from current definitions: {re.escape(PRELUDE)}"
    with pytest.raises(ValueError, match=message):
        compare_game(edited, output)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("schema", "schema 1; expected 2, rebuild with ancienttdde build --output "),
        ("artifacts", "every artifact this version builds; rebuild with ancienttdde build "),
        ("parser", "ancient-td-game was built with AoE2ScenarioParser 0.0.1"),
        ("input", "Game input SHA-256 mismatch: content/balance/game.json"),
        ("artifact", "Game artifact SHA-256 mismatch: map.json"),
    ],
)
def test_a_stale_or_edited_game_fails_before_any_rebuild(
    game_build: GameBuild,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    message: str,
) -> None:
    import shutil

    from ancienttdde.game import build

    output, _ = game_build
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    manifest = json.loads((edited / "manifest.json").read_text())
    if change == "schema":
        manifest["schema_version"] = 1
    elif change == "artifacts":
        # A build made before the prelude sidecar existed.
        manifest["artifacts"] = [r for r in manifest["artifacts"] if r["path"] != build.PRELUDE]
    elif change == "parser":
        manifest["parser_version"] = "0.0.1"
    elif change == "input":
        balance = next(r for r in manifest["inputs"] if r["path"] == "content/balance/game.json")
        balance["sha256"] = "0" * 64
    else:
        (edited / "map.json").write_text("{}")
    (edited / "manifest.json").write_text(json.dumps(manifest))
    rebuilds: list[Path] = []

    def rebuild(root: Path, output: Path | None = None) -> Path:
        rebuilds.append(root)
        raise AssertionError("validation rebuilt the game before its cheap checks failed")

    monkeypatch.setattr(build, "build_game", rebuild)
    with pytest.raises(ValueError, match=message):
        build.validate_game(edited, ROOT)
    assert rebuilds == []


def test_build_cli_output_validates_against_a_fresh_rebuild(game_build: GameBuild) -> None:
    output, _ = game_build
    assert (output / "ancient-td-de.aoe2scenario").is_file()
    result = CliRunner().invoke(app, ["validate", "--root", str(ROOT), "--build", str(output)])
    assert result.exit_code == 0, result.output


def test_game_output_rejects_sources_and_unrelated_artifacts(tmp_path: Path) -> None:
    from ancienttdde.game.build import build_game

    with pytest.raises(ValueError, match="source"):
        build_game(ROOT, ROOT / "src/generated")
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        build_game(ROOT, tmp_path)


def test_generated_spawns_and_starter_buildings_avoid_map_blockers(game_build: GameBuild) -> None:
    from ancienttdde.map.geometry import footprint

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {row["stock_id"]: row.get("blocking_size", 0) for row in config["objects"]}
    units = {u["reference_id"]: u for u in snapshot["units"]}
    blocked = {
        tile
        for unit in snapshot["units"]
        for tile in footprint(unit, sizes.get(unit["unit_const"], 0))
    }
    for trigger in snapshot["triggers"]:
        # Tiles of placements removed earlier in the same trigger are free again.
        freed: set[tuple[int, int]] = set()
        for effect in trigger["effects"]:
            attributes = effect["attributes"]
            if effect["type"] == "remove_object":
                for identifier in attr_list(attributes, "selected_object_ids"):
                    unit = units[identifier]
                    freed |= footprint(unit, sizes.get(unit["unit_const"], 0))
            if effect["type"] == "create_object":
                position: Position = {
                    "x": attr_number(attributes, "location_x"),
                    "y": attr_number(attributes, "location_y"),
                }
                size = max(sizes.get(attr_int(attributes, "object_list_unit_id"), 0), 1)
                created = footprint(position, size)
                assert not created & (blocked - freed), f"{trigger['name']} creates on a blocker"


def test_each_lane_swaps_its_lumber_trees_for_endless_ones_as_it_starts(
    game_build: GameBuild,
) -> None:
    """The endless amount applies to trees created after it, not to the placed ones, so a
    lane's initialize trigger removes each placed tree and creates one on its tile, after the
    orders that name the placed trees."""
    from ancienttdde.map.geometry import cells

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    deposits = triggers["game.deposits"]
    assert not deposits["conditions"] and not deposits["looping"]
    [amount] = [e for e in deposits["effects"] if e["attributes"]["object_list_unit_id"] == 399]
    assert amount["type"] == "modify_attribute"
    assert amount["attributes"]["source_player"] == 0
    assert amount["attributes"]["object_attributes"] == 21
    assert amount["attributes"]["operation"] == 1
    # DE applies this value as a 16-bit number: a DE trial turned 1,000,000 into 16,960.
    assert 30_000 <= amount["attributes"]["quantity"] <= 32_767
    trees = [u for u in snapshot["units"] if u["unit_const"] == 399 and u["player_id"] == 0]
    for player in range(1, 8):
        economy = cells(tuple(anchors[f"lane.p{player}.economy"]["region"]))
        placed = {
            u["reference_id"]: (int(u["x"]), int(u["y"]))
            for u in trees
            if (int(u["x"]), int(u["y"])) in economy
        }
        assert len(placed) == 4, f"P{player} needs four lumber trees"
        init = triggers[f"lane.p{player}.initialize"]
        # The amount is set in an earlier trigger that waits on nothing.
        assert deposits["id"] < init["id"]
        kinds = [e["type"] for e in init["effects"]]
        swaps = [
            index
            for index, e in enumerate(init["effects"])
            if e["type"] == "remove_object"
            and set(attr_list(e["attributes"], "selected_object_ids")) & set(placed)
        ]
        assert len(swaps) == 4
        # The lumberjacks' orders name the placed trees, so every order comes first.
        assert max(i for i, kind in enumerate(kinds) if kind == "task_object") < min(swaps)
        for index in swaps:
            removal, creation = init["effects"][index], init["effects"][index + 1]
            [reference] = attr_list(removal["attributes"], "selected_object_ids")
            assert removal["attributes"]["source_player"] == 0
            assert creation["type"] == "create_object"
            assert creation["attributes"]["source_player"] == 0
            assert creation["attributes"]["object_list_unit_id"] == 399
            created = (creation["attributes"]["location_x"], creation["attributes"]["location_y"])
            assert created == placed[reference]


def test_all_seven_players_have_a_preplaced_reachable_berry_mill(game_build: GameBuild) -> None:
    from ancienttdde.map.geometry import cells, flood, footprint, neighbors

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    land = {
        (index % 200, index // 200)
        for index, tile in enumerate(snapshot["map"]["tiles"])
        if tile[0] in config["land_terrain"]
    }
    for player in range(1, 8):
        prefix = f"lane.p{player}"
        mills = [
            unit
            for unit in snapshot["units"]
            if unit["player_id"] == player and unit["unit_const"] == 68
        ]
        assert len(mills) == 1, f"P{player} needs a starting berry mill"
        mill = mills[0]
        assert (mill["x"], mill["y"]) == (84, 15 + 28 * (player - 1))
        occupied = footprint(mill, 2)
        blocked = {
            tile
            for unit in snapshot["units"]
            if unit["reference_id"] != mill["reference_id"]
            for tile in footprint(unit, sizes.get(unit["unit_const"], 0))
        }
        economy = cells(tuple(config["anchors"][f"{prefix}.economy"]["region"]))
        assert occupied <= economy & land
        assert not occupied & blocked
        perimeter = {n for cell in occupied for n in neighbors(cell)} - occupied
        reachable = flood(perimeter, economy & land - blocked - occupied)
        gatherers = [
            (int(u["x"]), int(u["y"]))
            for u in snapshot["units"]
            if u["player_id"] == player
            and u["unit_const"] == 293
            and (int(u["x"]), int(u["y"])) in economy
        ]
        assert len(gatherers) == 2
        assert all(position in reachable for position in gatherers)


def test_the_king_a_cleared_lane_keeps_is_named(game_build: GameBuild) -> None:
    """Selecting the King the XS leaves on a cleared lane's spare siege islet says why it is
    there. Its trigger waits outside the lane's own, which the cleanup ends as it creates it."""
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    anchors = json.loads((output / "map.json").read_text())["anchors"]
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    for player in range(1, 8):
        x, y = (int(v) for v in anchors[f"siege.p{player}.3"]["point"])
        for role, message, inverted in (
            ("", f"Slot keeper: P{player}'s cleared lane stays in the game", 1),
            (".enemy", f"Enemy: P{player}'s units are the waves; its King keeps the slot", 0),
        ):
            keeper = triggers[f"game.keeper{role}.p{player}"]
            assert not keeper["looping"] and keeper["enabled"]
            [holding, standing] = keeper["conditions"]
            held = holding["attributes"]
            assert holding["type"] == "variable_value"
            assert (held["variable"], held["quantity"], held["inverted"]) == (
                variables["game.enemy"],
                player,
                inverted,
            )
            attributes = standing["attributes"]
            assert standing["type"] == "objects_in_area"
            assert (attributes["source_player"], attributes["object_list"]) == (player, KING)
            assert attributes["quantity"] == 1
            assert (
                attributes["area_x1"],
                attributes["area_y1"],
                attributes["area_x2"],
                attributes["area_y2"],
            ) == (x, y, x, y)
            [rename] = keeper["effects"]
            named = rename["attributes"]
            assert rename["type"] == "change_object_name"
            assert (named["source_player"], named["object_list_unit_id"]) == (player, KING)
            assert (named["area_x1"], named["area_y1"], named["area_x2"], named["area_y2"]) == (
                x,
                y,
                x,
                y,
            )
            assert named["message"] == message
            cleanup = triggers[f"lane.p{player}.cleanup"]
            ended = [
                e["attributes"]["trigger_id"]
                for e in cleanup["effects"]
                if e["type"] == "deactivate_trigger"
            ]
            assert ended and keeper["id"] not in ended


def test_lane_cleanup_clears_the_whole_lane_and_protects_the_king_it_leaves(
    game_build: GameBuild,
) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        cleanup = triggers[f"lane.p{player}.cleanup"]
        calls = [
            e["attributes"]["message"] for e in cleanup["effects"] if e["type"] == "script_call"
        ]
        # The mill goes too: the XS leaves only one King on the lane's spare siege islet.
        assert calls == [f"void ancientCleanupP{player}() {{ ancientCleanupLane({player}); }}"]
        kinds = [e["type"] for e in cleanup["effects"]]
        for protection in ("disable_unit_attackable", "disable_object_deletion"):
            [protect] = [e["attributes"] for e in cleanup["effects"] if e["type"] == protection]
            assert (protect["source_player"], protect["object_list_unit_id"]) == (player, KING)
            assert kinds.index("script_call") < kinds.index(protection)
        assert not any(
            e["type"] in ("remove_object", "change_ownership")
            and e["attributes"]["source_player"] == player
            for e in cleanup["effects"]
        )
