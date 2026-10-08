"""Reload playable artifacts and reject changes hidden behind edited hashes."""

import json
import re
from pathlib import Path

import pytest
from conftest import (
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


def test_native_actions_acknowledge_only_live_lane_requests(game_build: GameBuild) -> None:
    output, _ = game_build
    snapshot = json.loads((output / "scenario.json").read_text())
    variables = {v["name"]: v["variable_id"] for v in snapshot["variables"]}
    triggers = {t["name"]: t for t in snapshot["triggers"]}
    for player in range(1, 8):
        for suffix in (
            "initialize",
            "king",
            "attack",
            "wave.1",
            "buy.tower_attack_4",
            "transfer.build",
            "bonus.gold",
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
    # are revealed by activation, and nothing is ever deactivated.
    objectives = {
        t["id"] for t in snapshot["triggers"] if t["display_as_objective"] and not t["effects"]
    }
    for trigger in snapshot["triggers"]:
        for change in trigger["effects"]:
            assert change["type"] != "deactivate_trigger"
            if change["type"] == "activate_trigger":
                assert change["attributes"]["trigger_id"] in objectives
    enemy = [u for u in snapshot["units"] if u["player_id"] == 8]
    assert any(u["unit_const"] == 434 for u in enemy)


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


def test_every_wave_spawns_a_pair_per_lane(game_build: GameBuild) -> None:
    from ancienttdde.game.config import load_balance

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
def test_validation_rejects_tampered_logic_even_with_updated_hashes(
    game_build: GameBuild, tmp_path: Path, change: str
) -> None:
    import shutil

    from ancienttdde.game.build import ARTIFACTS, compare_game
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
    snapshot = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    (edited / "scenario.json").write_text(json.dumps(snapshot))
    manifest = json.loads((edited / "manifest.json").read_text())
    manifest["normalized_sha256"] = content_digest(snapshot)
    (edited / "manifest.json").write_text(json.dumps(manifest))
    rehash_artifacts(edited, "ancient-td-de.aoe2scenario", "scenario.json")

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


def test_lumber_trees_are_replaced_with_endless_wood_at_the_start(game_build: GameBuild) -> None:
    from ancienttdde.map.geometry import cells

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


def test_lane_cleanup_preserves_the_preplaced_mill_reference(game_build: GameBuild) -> None:
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
