"""Reload playable artifacts and reject changes hidden behind edited hashes."""

import contextlib
import io
import json
import re
from pathlib import Path

import pytest
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.probes.xs import xs_checker
from ancienttdde.provenance import hash_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def game_build(tmp_path_factory):
    from ancienttdde.engine.build import build_game

    output = tmp_path_factory.mktemp("game-build")
    manifest = build_game(ROOT, output)
    return output, manifest


def test_playable_map_is_self_contained_and_repeatable(game_build, tmp_path):
    from ancienttdde.engine.build import build_game, validate_game

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
    assert validate_game(output, ROOT) == first
    second = build_game(ROOT, tmp_path / "repeat")
    assert first["normalized_sha256"] == second["normalized_sha256"]
    assert first["inputs"] == second["inputs"]


def test_native_actions_acknowledge_only_live_lane_requests(game_build):
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        for suffix in ("initialize", "income", "wave.1"):
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
    assert not any(
        e["type"] in ("activate_trigger", "deactivate_trigger")
        for t in snapshot["triggers"]
        for e in t["effects"]
    )
    enemy = [u for u in snapshot["units"] if u["player_id"] == 8]
    assert any(u["unit_const"] == 434 for u in enemy)


def test_ai_fillers_use_embedded_passive_ai(game_build):
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    passive = (ROOT / "src/ancienttdde/ai/passive.per").read_text().strip()
    assert all(ai["script"].strip() == passive for ai in snapshot["embedded_ai"])
    assert all(p["lock_personality"] for p in snapshot["players"][1:])
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(output / "ancient-td-de.aoe2scenario"))
    assert all(p.lock_personality for p in scenario.player_manager.players[1:])


def test_initial_traders_receive_orders_to_their_own_partner(game_build):
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


def test_every_wave_spawns_a_pair_per_lane(game_build):
    from ancienttdde.engine.config import load_balance

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    batches = [
        t for t in snapshot["triggers"] if t["name"].startswith("lane.") and ".wave." in t["name"]
    ]
    assert len(batches) == 7 * len(load_balance(ROOT / "content/balance/game.json").waves)
    for trigger in batches:
        spawns = [e["attributes"] for e in trigger["effects"] if e["type"] == "create_object"]
        assert len(spawns) == 2
        assert all(e["source_player"] == 8 for e in spawns)
        assert spawns[0]["object_list_unit_id"] == spawns[1]["object_list_unit_id"]
        assert spawns[0]["location_y"] == spawns[1]["location_y"]
        assert spawns[1]["location_x"] == spawns[0]["location_x"] + 1


@pytest.mark.parametrize("change", ["resource_bonus", "ai_personality"])
def test_validation_rejects_tampered_logic_even_with_updated_hashes(game_build, tmp_path, change):
    import shutil

    from ancienttdde.engine.build import validate_game
    from ancienttdde.inspection.scenario import inspect_scenario
    from ancienttdde.probes.build import probe_digest

    output, _ = game_build
    edited = tmp_path / "edited"
    shutil.copytree(output, edited)
    path = edited / "ancient-td-de.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        scenario = AoE2DEScenario.from_file(str(path))
        if change == "resource_bonus":
            scenario.trigger_manager.add_trigger("Unexpected bonus").new_effect.modify_resource(
                source_player=1, tribute_list=3, quantity=9999, operation=1
            )
        else:
            scenario.player_manager.players[1].lock_personality = False
        with xs_checker(scenario):
            scenario.write_to_file(str(edited / "changed.aoe2scenario"))
    (edited / "changed.aoe2scenario").replace(path)
    snapshot = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    (edited / "scenario.json").write_text(json.dumps(snapshot))
    manifest = json.loads((edited / "manifest.json").read_text())
    manifest["normalized_sha256"] = probe_digest(snapshot)
    for record in manifest["artifacts"]:
        record["sha256"] = hash_file(edited / record["path"])
    (edited / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="current definitions"):
        validate_game(edited, ROOT)


def test_build_cli_produces_a_game_and_keeps_map_only_available(tmp_path):
    result = CliRunner().invoke(
        app, ["build", "--root", str(ROOT), "--output", str(tmp_path / "run")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "run/ancient-td-de.aoe2scenario").is_file()
    result = CliRunner().invoke(
        app, ["validate", "--root", str(ROOT), "--build", str(tmp_path / "run")]
    )
    assert result.exit_code == 0, result.output


def test_game_output_rejects_sources_and_unrelated_artifacts(tmp_path):
    from ancienttdde.engine.build import build_game

    with pytest.raises(ValueError, match="source"):
        build_game(ROOT, ROOT / "src/generated")
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        build_game(ROOT, tmp_path)


def test_generated_spawns_and_starter_buildings_avoid_map_blockers(game_build):
    from ancienttdde.generation.geometry import footprint

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
                for identifier in attributes.get("selected_object_ids") or []:
                    unit = units[identifier]
                    freed |= footprint(unit, sizes.get(unit["unit_const"], 0))
            if effect["type"] == "create_object":
                created = footprint(
                    {"x": attributes["location_x"], "y": attributes["location_y"]},
                    max(sizes.get(attributes["object_list_unit_id"], 0), 1),
                )
                assert not created & (blocked - freed), f"{trigger['name']} creates on a blocker"


def test_lumber_trees_are_replaced_with_endless_wood_at_the_start(game_build):
    from ancienttdde.generation.geometry import cells

    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    trigger = next(t for t in snapshot["triggers"] if t["name"] == "game.lumber")
    assert not trigger["conditions"] and not trigger["looping"]
    first, *rest = trigger["effects"]
    assert first["type"] == "modify_attribute"
    assert first["attributes"]["source_player"] == 0
    assert first["attributes"]["object_list_unit_id"] == 399
    assert first["attributes"]["object_attributes"] == 21
    assert first["attributes"]["operation"] == 1
    # DE applies this value as a 16-bit number: a DE trial turned 1,000,000 into 16,960.
    assert 30_000 <= first["attributes"]["quantity"] <= 32_767
    replaced = [
        (removal["attributes"]["selected_object_ids"], creation["attributes"])
        for removal, creation in zip(rest[::2], rest[1::2], strict=True)
    ]
    trees = {u["reference_id"]: u for u in snapshot["units"] if u["unit_const"] == 399}
    for player in range(1, 8):
        economy = cells(tuple(anchors[f"lane.p{player}.economy"]["region"]))
        lane = {r for r, u in trees.items() if (int(u["x"]), int(u["y"])) in economy}
        assert len(lane) == 4, f"P{player} needs four lumber trees"
    assert sorted(ids[0] for ids, _ in replaced) == sorted(trees)
    for ids, created in replaced:
        tree = trees[ids[0]]
        assert len(ids) == 1
        assert created["source_player"] == 0
        assert created["object_list_unit_id"] == 399
        assert (created["location_x"], created["location_y"]) == (int(tree["x"]), int(tree["y"]))


def test_all_seven_players_have_a_preplaced_reachable_berry_mill(game_build):
    from ancienttdde.generation.geometry import cells, flood, footprint, neighbors

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


def test_lane_cleanup_preserves_the_preplaced_mill_reference(game_build):
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        mill = next(
            u for u in snapshot["units"] if u["player_id"] == player and u["unit_const"] == 68
        )
        cleanup = triggers[f"lane.p{player}.cleanup"]
        calls = [
            e["attributes"]["message"] for e in cleanup["effects"] if e["type"] == "script_call"
        ]
        assert len(calls) == 1
        binding = re.search(r"ancientCleanupLane\((\d+), (\d+)\)", calls[0])
        assert binding is not None
        assert tuple(map(int, binding.groups())) == (player, mill["reference_id"])
        assert not any(
            e["type"] in ("remove_object", "change_ownership")
            and e["attributes"]["source_player"] == player
            for e in cleanup["effects"]
        )
