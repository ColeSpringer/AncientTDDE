"""The stock DE data snapshot the balance model reads: towers, enemies, raiders, siege, techs."""

import json
from pathlib import Path
from typing import Any

import pytest
from AoE2ScenarioParser.datasets.techs import TechInfo

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "content/balance/stock.json"
PIERCE, MELEE, BUILDINGS = 3, 4, 11


def load(path: Path = SNAPSHOT):
    from ancienttdde.game.stock import load_stock

    return load_stock(path)


def write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "stock.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_snapshot_records_its_source_and_every_civilization() -> None:
    from ancienttdde.game.civilizations import load_profiles
    from ancienttdde.game.config import load_balance

    stock = load()
    assert stock.source.version.startswith("VER ") and stock.source.file == "empires2_x2_p1.dat"
    assert len(stock.source.sha256) == 64 and stock.source.civilizations == 63
    from ancienttdde.game.catalog import load_shop

    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8"))
    shop = load_shop(
        ROOT / "content/balance/shop.json",
        anchors["anchors"],
        [name for name, _ in balance.towers.families],
    )
    profiles = load_profiles(ROOT / "content/balance/civilizations.json", balance, shop)
    assert [c.id for c in stock.civilizations] == [c.id for c in profiles.civilizations]
    assert all(c.name for c in stock.civilizations)
    koreans = stock.civilization(18)
    assert koreans.name == "Koreans" and not koreans.lacks & {
        "GUARD_TOWER",
        "KEEP",
        "BOMBARD_TOWER",
    }
    assert sum("BOMBARD_TOWER" in c.lacks for c in stock.civilizations) >= 20
    assert all(c.lacks <= set(stock.technologies) for c in stock.civilizations)


def test_snapshot_holds_every_unit_the_game_and_the_model_use() -> None:
    from ancienttdde.game.config import RAIDERS, TOWER_BUILDINGS, load_balance

    stock = load()
    balance = load_balance(ROOT / "content/balance/game.json")
    stock.check_waves(balance)
    assert stock.unit("SIEGE_RAM").unit_class == 13 and stock.unit("KING").unit_class == 59
    from dataclasses import replace

    from ancienttdde.game.config import WaveDefinition

    boat = WaveDefinition("Cogs", "TRADE_COG", 1, 1, 2, 1, 100, False)
    with pytest.raises(ValueError, match="cannot walk a lane"):
        stock.check_waves(replace(balance, waves=(boat, *balance.waves[1:])))
    needed = (
        set(TOWER_BUILDINGS)
        | {wave.unit for wave in balance.waves}
        | set(RAIDERS["land"])
        | set(RAIDERS["naval"])
        | {
            "TREBUCHET",
            "TREBUCHET_PACKED",
            "TRADE_CART_EMPTY",
            "TRADE_COG",
            "KING",
            "MONK",
            "RELIC",
            "GOLD_MINE",
            "STONE_MINE",
            "FORAGE_BUSH",
            "TREE_A",
            "OUTPOST",
            "CASTLE",
        }
    )
    assert needed <= set(stock.units)


def test_tower_and_enemy_numbers_match_the_installed_data() -> None:
    stock = load()
    watch = stock.unit("WATCH_TOWER")
    assert (watch.id, watch.hit_points, watch.reload, watch.range) == (79, 850, 2.0, 8.0)
    assert watch.attack(PIERCE) == 5 and watch.armor(PIERCE) == 7 and watch.armor(MELEE) == 1
    assert watch.cost == {"stone": 125, "wood": 35} and watch.build_time == 80
    keep = stock.unit("KEEP")
    assert (keep.hit_points, keep.attack(PIERCE)) == (2250, 8)
    bombard = stock.unit("BOMBARD_TOWER")
    assert (bombard.attack(PIERCE), bombard.reload, bombard.cost) == (
        120,
        6.0,
        {"gold": 100, "stone": 125},
    )
    accursed = stock.unit("THE_ACCURSED_TOWER")
    assert (accursed.attack(PIERCE), accursed.reload, accursed.range) == (8, 3.0, 13.0)
    paladin = stock.unit("PALADIN")
    assert (paladin.hit_points, paladin.armor(MELEE), paladin.armor(PIERCE)) == (160, 2, 3)
    assert stock.unit("WAR_ELEPHANT").armor(PIERCE) == 2
    assert stock.unit("VILLAGER_MALE").armor(PIERCE) == 0
    trebuchet = stock.unit("TREBUCHET")
    assert (trebuchet.attack(PIERCE), trebuchet.attack(BUILDINGS), trebuchet.reload) == (
        200,
        250,
        10.0,
    )
    assert (trebuchet.range, trebuchet.accuracy) == (16.0, 15)
    cart, cog = stock.unit("TRADE_CART_EMPTY"), stock.unit("TRADE_COG")
    assert (cart.hit_points, cart.speed, cart.work_rate) == (70, 1.25, 0.2875)
    assert cog.armor(PIERCE) == 6 and cog.speed > cart.speed
    assert stock.unit("LIGHT_CAVALRY").attack(MELEE) == 7
    assert stock.unit("GOLD_MINE").storage == 800 and stock.unit("TREE_A").storage == 125
    assert stock.relic_gold_per_minute == 30


def test_technologies_record_costs_and_their_tower_effects() -> None:
    stock = load()
    fletching = stock.technology("FLETCHING")
    assert fletching.id == TechInfo["FLETCHING"].ID
    assert fletching.cost == {"food": 100, "gold": 50} and fletching.time == 30
    assert (fletching.towers.attack, fletching.towers.range) == (1, 1)
    assert stock.technology("CHEMISTRY").towers.attack == 1
    assert stock.technology("ARROWSLITS").towers.attack == 1
    masonry = stock.technology("MASONRY").towers
    assert (masonry.hit_points_percent, masonry.melee_armor, masonry.pierce_armor) == (10, 1, 1)
    assert stock.technology("MURDER_HOLES").towers.minimum_range_removed
    assert stock.technology("KEEP").cost == {"food": 500, "wood": 350}
    assert stock.technology("GUARD_TOWER").towers.attack == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [(769, (3, 1)), (-1025, (4, -1)), (768.5, (3, 0.5)), (2936, (11, 120)), (0, (0, 0))],
)
def test_attack_values_unpack_their_damage_class(value: float, expected: tuple[int, float]) -> None:
    from ancienttdde.game.stock import class_amount

    assert class_amount(value) == expected


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("schema", "Unsupported stock schema"),
        ("missing_unit", "Stock snapshot lacks a unit: PALADIN"),
        ("missing_technology", "Stock snapshot lacks a technology: FLETCHING"),
        ("duplicate_civilization", "Duplicate civilization id: 1"),
        ("unknown_lack", "Civilization 1 lacks an unlisted technology: DRAGONS"),
        ("attack_shape", "attack must list"),
    ],
)
def test_invalid_snapshots_are_rejected(defect: str, message: str, tmp_path: Path) -> None:
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    match defect:
        case "schema":
            data["schema_version"] = 0
        case "missing_unit":
            del data["units"]["PALADIN"]
        case "missing_technology":
            del data["technologies"]["FLETCHING"]
        case "duplicate_civilization":
            data["civilizations"].append(dict(data["civilizations"][0]))
        case "unknown_lack":
            data["civilizations"][0]["lacks"] = ["DRAGONS"]
        case "attack_shape":
            data["units"]["WATCH_TOWER"]["attack"] = [[3]]
        case _:
            raise AssertionError(defect)
    with pytest.raises(ValueError, match=message):
        load(write(tmp_path, data))


def test_the_snapshot_digest_must_be_a_sha256(tmp_path: Path) -> None:
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    data["source"]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="SHA-256"):
        load(write(tmp_path, data))
