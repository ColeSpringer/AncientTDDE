import json

from ancienttdde.inspection.dat import inspect_dat


def dump(path, value):
    path.write_text(json.dumps(value))


def test_dat_keeps_gaia_enemy_and_human_variants_and_indirect_graphics(tmp_path):
    (tmp_path / "civilizations").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "custom_boss.smx").write_bytes(b"asset")
    dump(tmp_path / "manifest.json", {"source_file_version": "VER 7.4", "game_version": "GV_C17"})
    dump(
        tmp_path / "civilizations.json",
        [
            {"index": 0, "name": "Gaia", "file": "civilizations/gaia.json"},
            {"index": 1, "name": "Human", "file": "civilizations/human.json"},
            {"index": 8, "name": "Enemy", "file": "civilizations/enemy.json"},
        ],
    )
    for identifier, hp in [(0, 1), (1, 700), (8, 55)]:
        name = {0: "gaia", 1: "human", 8: "enemy"}[identifier]
        unit = {
            "ID": 0,
            "Name": name,
            "HitPoints": hp,
            "StandingGraphic": {"first": 0, "second": -1},
            "DeadUnitID": 1,
        }
        corpse = {"ID": 1, "Name": "corpse", "StandingGraphic": {"first": 2, "second": -1}}
        dump(
            tmp_path / f"civilizations/{name}.json",
            {
                "Name": name,
                "TechTreeID": 0,
                "TeamBonusID": 0,
                "Resources": [identifier, 500],
                "Units": [unit, corpse],
            },
        )
    dump(
        tmp_path / "graphics.json",
        [
            {"ID": 0, "FileName": "stock", "Deltas": [{"GraphicID": 1}]},
            {"ID": 1, "FileName": "custom_boss", "Deltas": []},
            {"ID": 2, "FileName": "custom_boss", "Deltas": []},
        ],
    )
    dump(tmp_path / "technologies.json", [{"Name": "Technology", "Civ": 8, "EffectID": 0}])
    dump(
        tmp_path / "effects.json",
        [{"Name": "Bonus", "EffectCommands": [{"Type": 4, "A": 0, "B": -1, "C": 0, "D": 500}]}],
    )
    result = inspect_dat(tmp_path, {0}, {0}, tmp_path / "assets")
    definitions = result["objects"][0]["civilizations"]
    assert definitions["0"]["definition"]["HitPoints"] == 1
    assert definitions["1"]["definition"]["HitPoints"] == 700
    assert definitions["8"]["definition"]["HitPoints"] == 55
    assert definitions["0"]["custom_graphics"] == [1, 2]
    assert definitions["0"]["linked_object_ids"] == [1]
    assert result["technologies"][0]["definition"]["Civ"] == 8
    assert result["civilizations"][2]["resources"][0] == 8
