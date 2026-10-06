"""Probe suite invariants, rejected inputs, tampering, output safety, CLI and results."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import (
    BARRACKS,
    KING,
    ROOT,
    ProbeSuite,
    attr_int,
    attr_list,
    load_scenario,
    probe_snapshot,
    rehash_artifacts,
    save_scenario,
    triggers_by_name,
)
from typer.testing import CliRunner

from ancienttdde.cli import app


def test_suite_builds_self_contained_solo_scenarios(probe_suite: ProbeSuite) -> None:
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
        snapshot = probe_snapshot(directory, probe["id"])
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


def test_probes_disable_all_builtin_victory_conditions_after_reload(
    probe_suite: ProbeSuite,
) -> None:
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        scenario = load_scenario(directory / probe["scenario"])
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
def test_probe_inspection_rejects_automatic_victory_conditions(
    probe_suite: ProbeSuite, tmp_path: Path, field: str
) -> None:
    from ancienttdde.probes.suite import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "automatic-victory.aoe2scenario"
    scenario = load_scenario(directory / "payments.aoe2scenario")
    setattr(scenario.sections["GlobalVictory"], field, 1)
    save_scenario(scenario, path)
    with pytest.raises(ValueError, match="victory"):
        inspect_probe(path)


def test_probes_preserve_controlled_test_settings_after_reload(probe_suite: ProbeSuite) -> None:
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        scenario = load_scenario(directory / probe["scenario"])
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
        diplomacy = {p.player_id: p.diplomacy or [] for p in scenario.player_manager.players}
        assert diplomacy[1][:2] == diplomacy[2][:2] == [0, 0]
        assert diplomacy[1][7] == diplomacy[8][0] == 3


# Objects the engine counts when deciding whether a player is still in the game. Towers
# (including Outposts), walls, gates, farms and trade units are ignored, so a player who
# owns only those is defeated at game start, which satisfies conquest for every enemy.
COUNTED_FOR_SURVIVAL = {KING, 83, 93, 448, 539, 42, 331, 84, 45, 109, BARRACKS}


# Stock footprints in tiles; even sizes are centered on tile corners, odd sizes on tiles.
FOOTPRINTS = {84: 4, 109: 4, 45: 3, BARRACKS: 3, 79: 1, 234: 1, 235: 1, 236: 1, 1776: 1, 819: 1}


def test_every_active_player_survives_game_start_and_unused_slots_cannot_act(
    probe_suite: ProbeSuite,
) -> None:
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        snapshot = probe_snapshot(directory, probe["id"])
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
                attr_int(pad, "area_x1") <= marker["x"] <= attr_int(pad, "area_x2") + 1
                and attr_int(pad, "area_y1") <= marker["y"] <= attr_int(pad, "area_y2") + 1
                for pad in pads
            ), f"{probe['id']}: marker inside a King payment region"
        initialization = triggers_by_name(snapshot)["probe.initialize"]
        for protection in ("disable_unit_attackable", "disable_object_deletion"):
            protected = {
                identifier
                for e in initialization["effects"]
                if e["type"] == protection
                for identifier in attr_list(e["attributes"], "selected_object_ids")
            }
            assert {u["reference_id"] for u in markers} <= protected
        towns = [u for u in snapshot["units"] if u["unit_const"] == 109]
        assert [u["player_id"] for u in towns] == ([1] if probe["id"] == "towers" else [])


def test_probe_inspection_rejects_empty_active_slots(
    probe_suite: ProbeSuite, tmp_path: Path
) -> None:
    from ancienttdde.probes.suite import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "empty-player.aoe2scenario"
    scenario = load_scenario(directory / "payments.aoe2scenario")
    scenario.unit_manager.units[2].extend(scenario.unit_manager.units[3])
    scenario.unit_manager.units[3].clear()
    for row in scenario.trigger_manager.triggers:
        for e in row.effects:
            if e.source_player == 3 and any(i >= 0 for i in e.selected_object_ids):
                e.source_player = 2
    save_scenario(scenario, path)
    with pytest.raises(ValueError, match="defeat"):
        inspect_probe(path)


def test_probe_inspection_rejects_players_kept_only_by_objects_the_engine_ignores(
    probe_suite: ProbeSuite, tmp_path: Path
) -> None:
    from ancienttdde.probes.suite import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "tower-only-player.aoe2scenario"
    scenario = load_scenario(directory / "payments.aoe2scenario")
    for unit in scenario.unit_manager.units[3]:
        unit.unit_const = 79
    save_scenario(scenario, path)
    with pytest.raises(ValueError, match="defeat"):
        inspect_probe(path)


def test_setup_instructions_stay_listed_as_an_open_objective(probe_suite: ProbeSuite) -> None:
    directory, manifest = probe_suite
    for probe in manifest["probes"]:
        snapshot = probe_snapshot(directory, probe["id"])
        pinned = triggers_by_name(snapshot)["Probe instructions"]
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
    heartbeat = probe_snapshot(directory, "scripts-enemy")
    names = {v["variable_id"]: v["name"] for v in heartbeat["variables"]}
    assert names[0] == "xs.heartbeat"


def test_buildings_are_centered_on_their_footprints(probe_suite: ProbeSuite) -> None:
    directory, manifest = probe_suite
    checked = 0
    for probe in manifest["probes"]:
        snapshot = probe_snapshot(directory, probe["id"])
        for unit in snapshot["units"]:
            size = FOOTPRINTS.get(unit["unit_const"])
            if size is None:
                continue
            checked += 1
            offset = 0.5 if size % 2 else 0.0
            assert (unit["x"] % 1, unit["y"] % 1) == (offset, offset), (probe["id"], unit)
    assert checked > 0


def test_probe_inspection_rejects_buildings_off_their_footprint_grid(
    probe_suite: ProbeSuite, tmp_path: Path
) -> None:
    from ancienttdde.probes.suite import inspect_probe

    directory, _ = probe_suite
    path = tmp_path / "misaligned-market.aoe2scenario"
    scenario = load_scenario(directory / "trade.aoe2scenario")
    market = next(u for u in scenario.unit_manager.units[1] if u.unit_const == 84)
    market.x += 0.5
    save_scenario(scenario, path)
    with pytest.raises(ValueError, match="footprint"):
        inspect_probe(path)


@pytest.mark.parametrize(
    "name", ["payments", "towers", "trade", "trade-gaia", "raiders", "siege", "scripts-enemy"]
)
def test_explicit_selected_units_use_their_real_owner_filter(
    probe_suite: ProbeSuite, name: str
) -> None:
    directory, _ = probe_suite
    snapshot = probe_snapshot(directory, name)
    owners = {u["reference_id"]: u["player_id"] for u in snapshot["units"]}
    for row in snapshot["triggers"]:
        for component in row["effects"]:
            attrs = component["attributes"]
            if "source_player" in attrs and attrs.get("selected_object_ids"):
                selected = attr_list(attrs, "selected_object_ids")
                assert {owners[i] for i in selected} == {attr_int(attrs, "source_player")}


@pytest.mark.parametrize("tampering", ["payment", "unlocked-teams", "full-tech-tree"])
def test_validation_detects_logic_tampering_after_artifact_hash_is_updated(
    payments_suite: Path, tmp_path: Path, tampering: str
) -> None:
    from ancienttdde.probes.build import verify_probes

    directory = tmp_path / "probes"
    shutil.copytree(payments_suite, directory)
    path = directory / "payments.aoe2scenario"
    scenario = load_scenario(path)
    if tampering == "payment":
        purchase = next(t for t in scenario.trigger_manager.triggers if t.name == "shop.purchase")
        payment = next(e for e in purchase.effects if e.effect_type == 15)
        payment.max_units_affected = 5
    elif tampering == "unlocked-teams":
        scenario.option_manager.lock_teams = False
    else:
        scenario.sections["Options"].all_techs = 1
    edited = path.with_name("edited.aoe2scenario")
    save_scenario(scenario, edited)
    edited.replace(path)
    rehash_artifacts(directory, path.name)
    # The reload no longer matches the recorded content, whatever the artifact hash says.
    with pytest.raises(ValueError, match="(content|reload|logic|settings)"):
        verify_probes(directory, ROOT)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("schema", "rebuild with ancienttdde probe --output .+ --only payments$"),
        ("parser", "was built with AoE2ScenarioParser 0.0.1, .+ --only payments$"),
        ("input", "Probe input SHA-256 mismatch: content/maps/format-seed.aoe2scenario"),
        ("artifact", "Probe artifact SHA-256 mismatch: payments.json"),
    ],
)
def test_a_stale_or_edited_suite_fails_before_any_rebuild(
    payments_suite: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    message: str,
) -> None:
    from ancienttdde.probes import build

    directory = tmp_path / "probes"
    shutil.copytree(payments_suite, directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if change == "schema":
        manifest["schema_version"] = 1
    elif change == "parser":
        manifest["parser_version"] = "0.0.1"
    elif change == "input":
        manifest["inputs"][0]["sha256"] = "0" * 64
    else:
        (directory / "payments.json").write_text("{}")
    (directory / "manifest.json").write_text(json.dumps(manifest))
    rebuilds: list[Path] = []

    def rebuild(root: Path, output: Path | None = None, *, only: list[str] | None = None) -> Path:
        rebuilds.append(root)
        raise AssertionError("validation rebuilt the probes before their cheap checks failed")

    monkeypatch.setattr(build, "build_probes", rebuild)
    with pytest.raises(ValueError, match=message):
        build.validate_probes(directory, ROOT)
    assert rebuilds == []


def test_validation_compares_a_suite_with_a_build_of_current_definitions(
    payments_suite: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ancienttdde.probes import build
    from ancienttdde.probes.suite import inspect_probe
    from ancienttdde.scenario.snapshot import content_digest

    directory = tmp_path / "probes"
    shutil.copytree(payments_suite, directory)
    path = directory / "payments.aoe2scenario"
    scenario = load_scenario(path)
    purchase = next(t for t in scenario.trigger_manager.triggers if t.name == "shop.purchase")
    payment = next(e for e in purchase.effects if e.effect_type == 15)
    payment.max_units_affected = 5
    save_scenario(scenario, directory / "edited.aoe2scenario")
    (directory / "edited.aoe2scenario").replace(path)
    snapshot = inspect_probe(path)
    (directory / "payments.json").write_text(json.dumps(snapshot))
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["probes"][0]["normalized_sha256"] = content_digest(snapshot)
    (directory / "manifest.json").write_text(json.dumps(manifest))
    rehash_artifacts(directory, "payments.aoe2scenario", "payments.json")

    def rebuild(root: Path, expected: Path | None = None, *, only: list[str] | None = None) -> Path:
        # The session suite is a build of the current definitions; copying it saves a rebuild.
        assert expected is not None and only == ["payments"]
        shutil.copytree(payments_suite, expected, dirs_exist_ok=True)
        return expected

    monkeypatch.setattr(build, "build_probes", rebuild)
    # The edited copy is internally consistent, so only the comparison can reject it.
    build.verify_probes(directory, ROOT)
    with pytest.raises(ValueError, match="Probe logic differs from current definitions: payments"):
        build.validate_probes(directory, ROOT)


def test_probe_comparison_rejects_logic_that_differs_from_current_definitions(
    probe_suite: ProbeSuite, payments_suite: Path, tmp_path: Path
) -> None:
    from ancienttdde.probes.build import compare_probes

    directory = tmp_path / "probes"
    shutil.copytree(payments_suite, directory)
    compare_probes(directory, payments_suite)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["probes"][0]["normalized_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="current definitions"):
        compare_probes(directory, payments_suite)
    original, _ = probe_suite
    with pytest.raises(ValueError, match="selection"):
        compare_probes(payments_suite, original)


def test_results_require_real_run_metadata_and_survive_rebuild(
    payments_suite: Path, tmp_path: Path
) -> None:
    from ancienttdde.probes.build import build_probes
    from ancienttdde.probes.results import record_result

    directory = tmp_path / "payments"
    shutil.copytree(payments_suite, directory)
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
    # A suite from an older manifest schema and input list is rebuilt in place.
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 1
    manifest["inputs"] = [{"path": "src/ancienttdde/probes/scenarios.py", "sha256": "0" * 64}]
    manifest_path.write_text(json.dumps(manifest))
    build_probes(ROOT, directory, only=["payments"])
    assert (directory / "results.json").read_bytes() == before
    assert json.loads(manifest_path.read_text())["schema_version"] == 2
    cases = json.loads(before)["cases"]
    row = next(c for c in cases if c["id"] == "payments.excess")
    assert row["runs"][-1]["status"] == "fail"
    assert row["runs"][-1]["scenario_sha256"]
    assert all(c["runs"] == [] for c in cases if c["id"] != "payments.excess")


def test_a_suite_is_not_rebuilt_in_place_with_a_different_selection(
    payments_suite: Path, tmp_path: Path
) -> None:
    from ancienttdde.probes.build import build_probes

    directory = tmp_path / "payments"
    shutil.copytree(payments_suite, directory)
    with pytest.raises(ValueError, match="different selection"):
        build_probes(ROOT, directory, only=["scripts-enemy"])
    # Without recorded results, the old selection's scenarios would stay beside the new ones.
    (directory / "results.json").unlink()
    with pytest.raises(ValueError, match="different selection"):
        build_probes(ROOT, directory, only=["scripts-enemy"])
    assert not (directory / "scripts-enemy.aoe2scenario").exists()


def test_probe_cli_builds_validates_and_records_a_case(tmp_path: Path) -> None:
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


def test_probe_output_does_not_replace_an_unrelated_manifest(tmp_path: Path) -> None:
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


def test_result_recording_rejects_a_results_symlink_outside_the_suite(
    payments_suite: Path, tmp_path: Path
) -> None:
    from ancienttdde.probes.results import record_result

    directory = tmp_path / "suite"
    shutil.copytree(payments_suite, directory)
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


def test_unknown_probe_name_does_not_write_outputs(tmp_path: Path) -> None:
    from ancienttdde.probes.build import build_probes

    with pytest.raises(ValueError, match="Unknown probe"):
        build_probes(ROOT, tmp_path / "output", only=["unknown"])
    assert not (tmp_path / "output").exists()
