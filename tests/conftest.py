import pytest


def object_mapping(key, legacy_id, stock_id, dataset, name, size=0):
    return {
        "key": key,
        "legacy_id": legacy_id,
        "civilization_ids": [9, 17, 8],
        "stock_id": stock_id,
        "disposition": "replace" if legacy_id != stock_id else "keep",
        "status": "reviewed",
        "map_identity": {"dataset": dataset, "name": name, "parser_version": "0.9.4"},
        "blocking_size": size,
    }


@pytest.fixture
def foundation_inputs():
    tiles = [[0, 0, -1] for _ in range(256)]
    for y in range(6):
        for x in range(10, 16):
            tiles[y * 16 + x] = [1, 0, -1]
    tiles[7 * 16 + 3] = [4, 2, 0]
    units = []
    for reference, owner, unit, x, y in [
        (0, 0, 857, 6.5, 8.5),
        (10, 1, 684, 12.5, 11.5),
        (11, 1, 204, 2.5, 8.5),
        (12, 8, 1740, 3.5, 10.5),
        (13, 1, 104, 7.5, 12.5),
        (14, 1, 83, 7.5, 12.5),
    ]:
        units.append(
            {
                "reference_id": reference,
                "player_id": owner,
                "unit_const": unit,
                "x": x,
                "y": y,
                "z": 1.0,
                "rotation": 1.5,
                "status": 2,
                "initial_animation_frame": 0,
                "garrisoned_in_id": 13 if reference == 14 else -1,
            }
        )
    legacy = {
        "schema_version": 1,
        "scenario_version": "1.49",
        "source": {"path": "original.aoe2scenario", "sha256": "a" * 64},
        "map": {"width": 16, "height": 16, "tiles": tiles},
        "players": [{"player_id": p, "civilization_id": c} for p, c in [(0, 9), (1, 17), (8, 8)]],
        "units": units,
    }
    config = {
        "schema_version": 1,
        "objects": [
            object_mapping("blocker", 857, 1776, "OtherInfo", "BLOCKER", 1),
            object_mapping("life", 684, 598, "BuildingInfo", "OUTPOST", 1),
            object_mapping("cart", 204, 128, "UnitInfo", "TRADE_CART_EMPTY"),
            object_mapping("sign", 1740, 819, "OtherInfo", "SIGN"),
            object_mapping("monastery", 104, 104, "BuildingInfo", "MONASTERY", 3),
            object_mapping("villager", 83, 83, "UnitInfo", "VILLAGER_MALE"),
        ],
        "anchors": {
            "lane.p1.spawn": {"point": [1.5, 8.5]},
            "lane.p1.exit": {"point": [12.5, 8.5]},
            "lane.p1.life": {"point": [12.5, 11.5], "reference_id": 10},
            "trade.home": {"point": [7.5, 12.5], "reference_id": 13},
            "siege.p1.1": {"point": [12.5, 2.5], "region": [11, 1, 13, 3]},
            "shop.attack": {"region": [2, 9, 4, 10]},
        },
        "placement_overrides": [{"reference_id": 12, "owner": 0, "caption": "+4 attack: 1 King"}],
        "terrain_patches": [
            {
                "key": "siege.p1.1",
                "region": [11, 1, 13, 3],
                "terrain_id": 0,
                "allowed_source_terrain": [1],
            }
        ],
        "routes": [
            {
                "key": "lane.p1",
                "start": "lane.p1.spawn",
                "end": "lane.p1.exit",
                "medium": "land",
                "region": [1, 7, 12, 9],
            }
        ],
        "isolation": [
            {"key": "siege.p1.1", "start": "siege.p1.1", "medium": "land", "region": [11, 1, 13, 3]}
        ],
        "land_terrain": [0, 4],
        "water_terrain": [1, 4],
    }
    return legacy, config
