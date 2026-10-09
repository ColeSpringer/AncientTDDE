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
KING = 434
OUTPOST = 598
HAY_STACK = 857


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
    replaced = [p.legacy for p in shop().purchases if p.legacy is not None]
    assert sorted(replaced) == sorted(families)


def test_raiders_and_the_siege_power_up_are_sold_beside_the_land_trade_wall() -> None:
    from ancienttdde.game.catalog import Raider, SiegePowerUp

    catalog = shop()
    land, naval, siege = (catalog.get(k) for k in ("land_raider", "naval_raider", "siege"))
    assert (land.effect, land.kings, land.legacy) == (Raider("land"), 3, None)
    assert (naval.effect, naval.kings, naval.legacy) == (Raider("naval"), 3, None)
    assert (siege.effect, siege.kings, siege.legacy) == (SiegePowerUp(3), 15, None)
    assert not any(p.once for p in (land, naval, siege))
    assert [p.pad for p in (land, naval, siege)] == [
        "shop.land_raider",
        "shop.naval_raider",
        "shop.siege",
    ]


@pytest.mark.parametrize(
    ("key", "caption"),
    [
        ("tower_attack_4", "Tower attack +4: 1 King"),
        ("tower_attack_50", "Tower attack +50: 7 Kings"),
        ("king_every_minute", "1 King every minute: 20 Kings, once"),
        ("imperial_age", "Imperial Age and Keep: 1 King, once, after Castle Age and Guard Tower"),
        ("fourth_row", "Fourth row of towers: 3 Kings, once, after Third row of towers"),
        (
            "bombard_attack_400",
            "Bombard Tower attack +400: 18 Kings, for civilizations with Bombard Towers",
        ),
        ("land_raider", "Land raider (light cavalry): 3 Kings, when PvP is on"),
        ("naval_raider", "Naval raider (fire galley): 3 Kings, when PvP is on"),
        ("siege", "Siege power-up: 15 Kings plus 3 per surviving rival, when PvP is on"),
        ("castle", "Castle (+20 population, castle research): 1 King, once"),
    ],
)
def test_captions_state_the_name_price_and_limits(key: str, caption: str) -> None:
    assert shop().get(key).caption == caption


@pytest.mark.parametrize(
    ("key", "price"),
    [
        ("tower_attack_4", "1 King"),
        ("tower_attack_50", "7 Kings"),
        ("siege", "15 Kings plus 3 per surviving rival"),
    ],
)
def test_prices_are_written_once_for_captions_and_messages(key: str, price: str) -> None:
    assert shop().get(key).price == price
    assert shop().get(key).caption.startswith(f"{shop().get(key).name}: {price}")


@pytest.mark.parametrize(
    ("key", "tag"),
    [
        ("tower_attack_4", "+4 attack: 1 King"),
        ("attack_1_every_30", "+1 attack/30 s: 4 Kings"),
        ("gold_1000", "1000 gold/2 min: 4 Kings"),
        ("left_accursed_tower", "Accursed Tower: 1 King"),
        ("siege", "Siege power-up: 15 Kings +3/rival"),
        ("castle", "Castle: 1 King"),
    ],
)
def test_overhead_tags_are_the_short_label_and_price(key: str, tag: str) -> None:
    """DE draws the tag above the exhibit at a fixed font size, so it stays short. Labels
    whose effect states the numbers come from the effect, so the catalog cannot misstate them."""
    from ancienttdde.game.catalog import display_captions

    catalog = shop()
    assert catalog.get(key).tag == tag
    assert catalog.get("king_every_150").label == "1 King/2.5 min"
    assert catalog.get("king_every_minute").label == "1 King/min"
    assert catalog.get("third_row").label == catalog.get("fourth_row").label == "Tower row"
    assert "label" not in next(p for p in raw_catalog()["purchases"] if p["key"] == "gold_1000")
    assert max(len(p.tag) for p in catalog.purchases) <= 33
    # The Accursed Tower pads share one exhibit, and so do the two halves of the tower-row
    # pad; their identical tags are written once.
    overhead = display_captions(catalog, overhead=True)
    assert overhead[catalog.get("left_accursed_tower").display or 0] == "Accursed Tower: 1 King"
    assert overhead[catalog.get("third_row").display or 0] == "Tower row: 3 Kings"


def test_every_purchase_names_a_display_object_beside_its_pad() -> None:
    """The original labels each pad with a placed unit it renames; those units stay where the
    map puts them. The raider and siege pads are new, so the build places a King for each."""
    from ancienttdde.game.catalog import check_displays, display_captions

    catalog = shop()
    placed = [p.display for p in catalog.purchases if p.display is not None]
    created = [p for p in catalog.purchases if p.display is None]
    assert len(placed) + len(created) == len(catalog.purchases)
    assert [p.key for p in created] == ["land_raider", "naval_raider", "siege"]
    assert all(p.display_at is not None for p in created)
    assert catalog.get("tower_attack_4").display == 18941
    assert catalog.get("left_accursed_tower").display == catalog.get("right_accursed_tower").display
    captions = display_captions(catalog)
    assert captions[18941] == "Tower attack +4: 1 King"
    assert captions[catalog.get("third_row").display or 0] == (
        "Third row of towers: 3 Kings, once | "
        "Fourth row of towers: 3 Kings, once, after Third row of towers"
    )
    assert set(captions) == set(placed)
    data, config = map_content()
    check_displays(catalog, data, config)


def test_kings_for_new_pads_stand_centred_in_the_hay_line_at_the_far_end() -> None:
    """Like the original's exhibits, each King the build places stands in the Hay Stack line
    beyond its pad's far, beach side, centred on the pad and flanked by Hay Stacks."""
    catalog = shop()
    data, _ = map_content()
    held = {(math.floor(u["x"]), math.floor(u["y"])): u["unit_const"] for u in data["units"]}
    for key in ("land_raider", "naval_raider", "siege"):
        purchase = catalog.get(key)
        _, y1, x2, y2 = purchase.pad_region
        centre = (y1 + y2 + 1) / 2
        assert purchase.display_at == (x2 + 1.5, centre), key
        for row in range(y1, y2 + 1):
            flank = abs(row + 0.5 - centre) >= 1
            assert held.get((x2 + 1, row)) == (HAY_STACK if flank else None), (key, row)


# DE draws a caption centred above its object in a font that does not shrink with the view.
# A tile is 96 by 48 pixels, a character about 12 pixels wide and a line 22 pixels tall, and a
# caption sits above the object's sprite plus a fixed margin: these sprite heights were
# measured on screenshots of the built game at the native zoom.
CHAR_WIDTH = 12.0
LINE_HEIGHT = 22.0
CAPTION_MARGIN = 20.0
SPRITE_HEIGHT = {OUTPOST: 151, 79: 140, 625: 70, 128: 50, 17: 50, 285: 35}
UNIT_SPRITE_HEIGHT = 45
# Captions closer than this, in pixels, read as one.
CAPTION_GAP = 6.0


def caption_box(
    unit_const: int, x: float, y: float, text: str
) -> tuple[float, float, float, float]:
    """The screen rectangle of a caption, in pixels from the map origin."""
    centre_x = (x + y) * 48.0
    lift = SPRITE_HEIGHT.get(unit_const, UNIT_SPRITE_HEIGHT) + CAPTION_MARGIN
    centre_y = (y - x) * 24.0 - lift
    half = CHAR_WIDTH * len(text) / 2
    return centre_x - half, centre_y - LINE_HEIGHT / 2, centre_x + half, centre_y + LINE_HEIGHT / 2


def test_captions_the_build_adds_keep_clear_of_every_other() -> None:
    """The original's exhibits keep their own spots, wherever that puts their tags; the Kings
    placed for the new pads and the run controls are placed so their captions run into none."""
    from ancienttdde.game.catalog import display_captions
    from ancienttdde.game.config import load_balance
    from ancienttdde.game.controls import CONTROLS, control_labels

    catalog = shop()
    data, config = map_content()
    units = {u["reference_id"]: u for u in data["units"]}
    placed: list[tuple[str, tuple[float, float, float, float]]] = []
    for display, text in display_captions(catalog, overhead=True).items():
        unit = units[display]
        placed.append((text, caption_box(unit["unit_const"], unit["x"], unit["y"], text)))
    added: list[tuple[str, tuple[float, float, float, float]]] = []
    for purchase in catalog.purchases:
        if purchase.display_at is not None:
            x, y = purchase.display_at
            added.append((purchase.tag, caption_box(KING, x, y, purchase.tag)))
    labels = control_labels(load_balance(ROOT / "content/balance/game.json"))
    anchors = config["anchors"]
    points = anchors["controls.run"].get("points", []) + anchors["controls.practice"].get(
        "points", []
    )
    for control, (x, y) in zip(CONTROLS, points, strict=True):
        text = labels[control.key]
        added.append((text, caption_box(OUTPOST, x, y, text)))
    for index, (first, a) in enumerate(added):
        for second, b in added[index + 1 :] + placed:
            apart = max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])
            assert apart >= CAPTION_GAP, f"{first!r} runs into {second!r}"


def test_kings_placed_for_new_pads_stand_nearest_their_own_pad() -> None:
    """A caption is read as the nearest pad's, so a King the build places stands nearer its own
    pad than any other."""
    from ancienttdde.game.catalog import distance

    catalog = shop()
    for purchase in catalog.purchases:
        if purchase.display_at is None:
            continue
        x, y = purchase.display_at
        own = distance(purchase.pad_region, x, y)
        for other in catalog.purchases:
            if other.pad != purchase.pad:
                assert distance(other.pad_region, x, y) > own, (purchase.key, other.key)


def entrances() -> set[Cell]:
    """The tiles the lanes' Kings gather on before walking into the shop."""
    _, config = map_content()
    points = [config["anchors"][f"lane.p{p}.kings"].get("points", [])[1] for p in range(1, 8)]
    return {(math.floor(x), math.floor(y)) for x, y in points}


def test_exhibits_keep_off_creation_tiles_and_out_of_the_kings_way(tmp_path: Path) -> None:
    from ancienttdde.game.catalog import check_displays, exhibit_position

    data, config = map_content()
    catalog = shop()
    check_displays(catalog, data, config, entrances=entrances())
    units = {u["reference_id"]: u for u in data["units"]}
    x, y = exhibit_position(catalog.get("wood_2000"), units)
    with pytest.raises(ValueError, match="creation tile"):
        check_displays(catalog, data, config, reserved={(math.floor(x), math.floor(y))})
    raw = raw_catalog()
    rows = {p["key"]: p for p in raw["purchases"]}
    # A King in the one-tile gap between Hay Stacks that leads into the Castle Age pad.
    del rows["castle_age"]["display"]
    rows["castle_age"]["display_at"] = [131.5, 45.5]
    with pytest.raises(ValueError, match="cut the castle_age pad off"):
        check_displays(load(raw, tmp_path), data, config, entrances=entrances())


def test_created_exhibits_cannot_share_a_tile(tmp_path: Path) -> None:
    from ancienttdde.game.catalog import check_displays

    raw = raw_catalog()
    rows = {p["key"]: p for p in raw["purchases"]}
    # A free tile beside both the naval raider and the siege pads.
    rows["naval_raider"]["display_at"] = rows["siege"]["display_at"] = [165.5, 23.5]
    data, config = map_content()
    with pytest.raises(ValueError, match="share tile"):
        check_displays(load(raw, tmp_path), data, config)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"display": 19181}, "beside its pad"),
        ({"display": 999999}, "placed"),
        ({"display": 40004}, "Gaia"),
        ({"display_at": [160.5, 15.5]}, "pad"),
        ({"display_at": [168.5, 36.5]}, "pad"),
        ({"display_at": [159.5, 14.5]}, "placed object"),
        ({"display_at": [159.5, 16.5]}, "another object"),
        ({"display_at": [156.5, 19.5]}, "another object"),
        ({"display_at": [156.5, 51.5]}, "terrain"),
        ({"display_at": [-0.5, 15.5]}, "off the map"),
        ({"display_at": [150.5, 40.5]}, "beside its pad"),
    ],
)
def test_displays_must_stand_free_beside_their_pads(
    change: dict[str, object], message: str, tmp_path: Path
) -> None:
    from ancienttdde.game.catalog import check_displays

    raw = raw_catalog()
    first = raw["purchases"][0]
    del first["display"]
    first.update(change)
    data, config = map_content()
    with pytest.raises(ValueError, match=message):
        check_displays(load(raw, tmp_path), data, config)


def test_periodic_attack_purchases_may_raise_different_families(tmp_path: Path) -> None:
    """The XS adds each investment's attack to its own family."""
    from ancienttdde.game.catalog import Investment

    raw = raw_catalog()
    rows = {p["key"]: p for p in raw["purchases"]}
    rows["attack_3_every_30"]["effect"]["family"] = "bombard"
    effect = load(raw, tmp_path).get("attack_3_every_30").effect
    assert isinstance(effect, Investment) and effect.family == "bombard"


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
    from ancienttdde.game.catalog import SiegePowerUp

    data, config = map_content()
    walkable = open_land(data, config)
    claimed: dict[Cell, str] = {}
    for purchase in shop().purchases:
        tiles = cells(purchase.pad_region) & walkable
        assert len(tiles) >= min(purchase.kings, 4), purchase.key
        # The siege's price grows with the rivals: six of them in a full game.
        if isinstance(purchase.effect, SiegePowerUp):
            assert len(tiles) >= purchase.kings + 6 * purchase.effect.kings_per_rival
        for cell in tiles:
            assert claimed.setdefault(cell, purchase.pad) == purchase.pad, (cell, purchase.key)


@pytest.mark.parametrize("player", range(1, 8))
def test_every_pad_is_reachable_from_each_kings_entrance(player: int) -> None:
    """With the exhibits standing where the build puts them: a unit holds its tile."""
    from ancienttdde.game.catalog import exhibit_position

    data, config = map_content()
    units = {u["reference_id"]: u for u in data["units"]}
    exhibits = {
        (math.floor(x), math.floor(y))
        for x, y in (exhibit_position(p, units) for p in shop().purchases)
    }
    walkable = open_land(data, config) - exhibits
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
        ("unknown_resource", "resource"),
        ("repeatable_investment", "must be once-only: gold_175"),
        ("self_requirement", "Purchase third_row cannot require itself"),
        ("requirement_cycle", "Purchase requirements form a cycle: castle_age"),
        ("unknown_technology", "Unknown technology: CATAPULTS"),
        ("too_many_once", "At most 31 purchases can be once-only"),
        ("second_repair", "At most one repair purchase"),
        ("second_relics", "At most one relics purchase"),
        ("no_display", "exactly one of display or display_at"),
        ("moved_display", "exactly one of display or display_at"),
        ("old_schema", "Unsupported shop schema"),
        ("previous_schema", "Unsupported shop schema"),
        ("second_siege", "At most one siege purchase"),
        ("second_land_raider", "At most one land raider purchase"),
        ("siege_kings_per_rival", "kings_per_rival"),
        ("unknown_medium", "medium"),
        ("blank_legacy", "legacy"),
        ("blank_label", "label"),
        ("unnamed_label", "needs a label"),
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
    elif defect == "no_display":
        del first["display"]
    elif defect == "moved_display":
        # The original's exhibits stay where the map puts them.
        first["display_at"] = [156.5, 17.5]
    elif defect == "old_schema":
        raw["schema_version"] = 1
    elif defect == "previous_schema":
        raw["schema_version"] = 3
    elif defect == "second_siege":
        first["effect"] = {"kind": "siege", "kings_per_rival": 5}
    elif defect == "second_land_raider":
        first["effect"] = {"kind": "raider", "medium": "land"}
    elif defect == "siege_kings_per_rival":
        next(p for p in purchases if p["key"] == "siege")["effect"]["kings_per_rival"] = 0
    elif defect == "unknown_medium":
        first["effect"] = {"kind": "raider", "medium": "air"}
    elif defect == "blank_legacy":
        first["legacy"] = " "
    elif defect == "blank_label":
        first["label"] = " "
    elif defect == "unnamed_label":
        next(p for p in purchases if p["key"] == "land_raider").pop("label")
    elif defect in ("second_repair", "second_relics"):
        kind = defect.removeprefix("second_")
        first["effect"] = next(p for p in purchases if p["effect"]["kind"] == kind)["effect"]
        first["once"] = True
    if first["effect"]["kind"] in ("relics", "siege", "raider", "repair"):
        # An effect that does not name its own label needs one from the catalog.
        first.setdefault("label", "Label")
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
