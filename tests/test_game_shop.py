"""The purchase catalog: coverage of the original shop, captions, pads and validation."""

import copy
import json
import math
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest

from ancienttdde.map.geometry import Cell, cells, flood, footprint
from ancienttdde.map.models import FoundationConfig, MapDocument

ROOT = Path(__file__).resolve().parents[1]


def raw_catalog() -> dict[str, Any]:
    return json.loads((ROOT / "content/balance/shop.json").read_text(encoding="utf-8"))


def anchors() -> dict[str, Any]:
    config = json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8"))
    return config["anchors"]


def families() -> list[str]:
    from ancienttdde.game.config import load_balance

    return [name for name, _ in load_balance(ROOT / "content/balance/game.json").towers.families]


def load(raw: dict[str, Any], tmp_path: Path):
    from ancienttdde.game.catalog import load_shop

    path = tmp_path / "shop.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_shop(path, anchors(), families())


def shop():
    from ancienttdde.game.catalog import load_shop

    return load_shop(ROOT / "content/balance/shop.json", anchors(), families())


def test_every_original_purchase_family_has_one_modern_purchase() -> None:
    legacy = json.loads((ROOT / "content/legacy/purchases.json").read_text(encoding="utf-8"))
    families = {p["name"].split("(p")[0].strip() for p in legacy["purchases"]}
    assert len(families) == 36
    replaced = [p.legacy for p in shop().purchases]
    assert sorted(replaced) == sorted(families)


@pytest.mark.parametrize(
    ("key", "caption"),
    [
        ("tower_attack_4", "Tower attack +4: 1 King"),
        ("tower_attack_50", "Tower attack +50: 7 Kings"),
        ("king_every_minute", "1 King every minute: 21 Kings, once"),
        ("imperial_age", "Imperial Age and Keep: 1 King, once, after Castle Age and Guard Tower"),
        ("fourth_row", "Fourth row of towers: 3 Kings, once, after Third row of towers"),
        (
            "bombard_attack_400",
            "Bombard Tower attack +400: 18 Kings, for civilizations with Bombard Towers",
        ),
    ],
)
def test_captions_state_the_name_price_and_limits(key: str, caption: str) -> None:
    assert shop().get(key).caption == caption


@pytest.mark.parametrize(
    ("key", "price"), [("tower_attack_4", "1 King"), ("tower_attack_50", "7 Kings")]
)
def test_prices_are_written_once_for_captions_and_messages(key: str, price: str) -> None:
    assert shop().get(key).price == price
    assert shop().get(key).caption.startswith(f"{shop().get(key).name}: {price}")


def test_shared_signs_list_every_purchase_they_label() -> None:
    from ancienttdde.game.catalog import label_captions

    captions = label_captions(shop())
    left, right = shop().get("left_accursed_tower"), shop().get("right_accursed_tower")
    assert left.label is not None and left.label == right.label
    assert captions[left.label] == (
        "Left Accursed Tower: 1 King, once | Right Accursed Tower: 1 King, once"
    )


def test_once_purchases_have_distinct_ownership_bits() -> None:
    bits = [p.bit for p in shop().purchases if p.once]
    assert sorted(bits) == list(range(len(bits)))
    assert len(bits) <= 31
    assert all(p.bit == -1 for p in shop().purchases if not p.once)


def test_purchase_numbers_start_at_one_in_catalog_order() -> None:
    assert [p.index for p in shop().purchases] == list(range(1, len(shop().purchases) + 1))


@cache
def map_content() -> tuple[MapDocument, FoundationConfig]:
    from ancienttdde.map.foundation import migrate_map

    legacy = cast(
        MapDocument,
        json.loads((ROOT / "content/maps/legacy-map.json").read_text(encoding="utf-8")),
    )
    config = cast(
        FoundationConfig,
        json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8")),
    )
    return migrate_map(legacy, config), config


def open_land(data: MapDocument, config: FoundationConfig) -> set[Cell]:
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    width = data["map"]["width"]
    land = {
        (i % width, i // width)
        for i, t in enumerate(data["map"]["tiles"])
        if t[0] in config["land_terrain"]
    }
    return land - blocked


def test_pads_hold_their_price_in_open_tiles_without_sharing_any() -> None:
    data, config = map_content()
    walkable = open_land(data, config)
    claimed: dict[Cell, str] = {}
    for purchase in shop().purchases:
        tiles = cells(purchase.pad_region) & walkable
        assert len(tiles) >= min(purchase.kings, 4), purchase.key
        for cell in tiles:
            assert claimed.setdefault(cell, purchase.pad) == purchase.pad, (cell, purchase.key)


@pytest.mark.parametrize("player", range(1, 8))
def test_every_pad_is_reachable_from_each_kings_entrance(player: int) -> None:
    data, config = map_content()
    walkable = open_land(data, config)
    _, rally = config["anchors"][f"lane.p{player}.kings"].get("points", [])
    reached = flood({(math.floor(rally[0]), math.floor(rally[1]))}, walkable)
    for purchase in shop().purchases:
        assert cells(purchase.pad_region) & reached, purchase.key


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("duplicate_key", "Duplicate purchase key: tower_attack_4"),
        ("free", "kings"),
        ("unknown_kind", "Unknown purchase effect: teleport"),
        ("unknown_requirement", "unknown_purchase"),
        ("repeatable_requirement", "must require a once-only purchase"),
        ("unknown_family", "Unknown tower family: walls"),
        ("unknown_pad", "Purchase pad needs a shop region: shop.nowhere"),
        ("no_label", "needs exactly one of sign or new_sign"),
        ("unknown_resource", "resource"),
        ("repeatable_investment", "must be once-only: gold_175"),
        ("self_requirement", "Purchase third_row cannot require itself"),
        ("requirement_cycle", "Purchase requirements form a cycle: castle_age"),
        ("unknown_technology", "Unknown technology: CATAPULTS"),
        ("too_many_once", "At most 31 purchases can be once-only"),
        ("second_repair", "At most one repair purchase"),
        ("second_relics", "At most one relics purchase"),
    ],
)
def test_invalid_catalogs_are_rejected(defect: str, message: str, tmp_path: Path) -> None:
    raw = raw_catalog()
    purchases = raw["purchases"]
    first = purchases[0]
    if defect == "duplicate_key":
        purchases.append(copy.deepcopy(first))
    elif defect == "free":
        first["kings"] = 0
    elif defect == "unknown_kind":
        first["effect"] = {"kind": "teleport"}
    elif defect == "unknown_requirement":
        first["requires"] = "unknown_purchase"
    elif defect == "repeatable_requirement":
        first["requires"] = "tower_attack_10"
    elif defect == "unknown_family":
        first["effect"] = {"kind": "tower_attack", "family": "walls", "amount": 4}
    elif defect == "unknown_pad":
        first["pad"] = "shop.nowhere"
    elif defect == "no_label":
        first.pop("sign", None)
        first.pop("new_sign", None)
    elif defect == "unknown_resource":
        first["effect"] = {"kind": "resource", "resource": "glory", "amount": 10}
    elif defect == "repeatable_investment":
        next(p for p in purchases if p["key"] == "gold_175").pop("once")
    elif defect == "self_requirement":
        next(p for p in purchases if p["key"] == "third_row")["requires"] = "third_row"
    elif defect == "requirement_cycle":
        next(p for p in purchases if p["key"] == "castle_age")["requires"] = "imperial_age"
    elif defect == "unknown_technology":
        first["only_with"] = {"technology": "CATAPULTS", "text": "catapults"}
    elif defect == "too_many_once":
        for purchase in purchases:
            purchase["once"] = True
    elif defect in ("second_repair", "second_relics"):
        kind = defect.removeprefix("second_")
        first["effect"] = next(p for p in purchases if p["effect"]["kind"] == kind)["effect"]
        first["once"] = True
    with pytest.raises(ValueError, match=message):
        load(raw, tmp_path)


def test_pads_that_share_a_standable_tile_are_rejected(tmp_path: Path) -> None:
    from ancienttdde.game.catalog import check_pads

    data, config = map_content()
    check_pads(shop(), data, config)
    raw = raw_catalog()
    second = next(p for p in raw["purchases"] if p["key"] == "tower_attack_10")
    second["pad"] = "shop.tower_attack_4"
    with pytest.raises(ValueError, match="share"):
        check_pads(load(raw, tmp_path), data, config)


@pytest.mark.parametrize(
    ("resource", "caption"),
    [
        ("gold", "Gold bonus: reach the end of the rows for 10000 gold and endless gold mines"),
        ("food", "Food bonus: reach the end of the rows for 1000 food and an endless berry bush"),
        ("stone", "Stone bonus: reach the end of the rows for 3000 stone and endless stone mines"),
    ],
)
def test_bonus_signs_name_the_bonus_and_its_endless_deposits(resource: str, caption: str) -> None:
    from ancienttdde.game.config import load_balance
    from ancienttdde.game.instructions import bonus_caption

    assert bonus_caption(load_balance(ROOT / "content/balance/game.json"), resource) == caption
