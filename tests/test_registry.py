import pytest

from ancienttdde.registry import ReferenceRegistry


def test_registry_resolves_same_legacy_id_by_civilization():
    registry = ReferenceRegistry(
        [
            {
                "key": "shop.wood",
                "legacy_id": 169,
                "civilization_ids": [0],
                "disposition": "replace",
                "stock_id": 149,
                "status": "candidate",
            },
            {
                "key": "wave.hussar",
                "legacy_id": 169,
                "civilization_ids": [8],
                "disposition": "keep",
                "stock_id": 441,
                "status": "candidate",
            },
        ]
    )
    assert registry.legacy(169, 0)["key"] == "shop.wood"
    assert registry.legacy(169, 8)["key"] == "wave.hussar"
    with pytest.raises(ValueError, match="verified"):
        registry.stock("wave.hussar")


def test_registry_rejects_ambiguous_mappings():
    rows = [
        {
            "key": "one",
            "legacy_id": 1,
            "civilization_ids": [0],
            "disposition": "keep",
            "stock_id": 1,
            "status": "candidate",
        },
        {
            "key": "two",
            "legacy_id": 1,
            "civilization_ids": [0],
            "disposition": "drop",
            "stock_id": None,
            "status": "reviewed",
        },
    ]
    with pytest.raises(ValueError, match="Duplicate legacy"):
        ReferenceRegistry(rows)


def test_verified_mapping_and_named_trigger_and_variable_references():
    registry = ReferenceRegistry(
        [
            {
                "key": "king",
                "legacy_id": 434,
                "civilization_ids": [1],
                "disposition": "keep",
                "stock_id": 434,
                "status": "verified",
            }
        ]
    )
    assert registry.stock("king") == 434
    registry.register("trigger", "initialize", 0)
    registry.register("variable", "lives.p1", 0)
    assert registry.resolve("trigger", "initialize") == 0
    assert registry.resolve("variable", "lives.p1") == 0
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register("trigger", "initialize", 1)


def test_map_identity_verification_does_not_approve_gameplay():
    row = {
        "key": "map.blocker",
        "legacy_id": 857,
        "civilization_ids": [9],
        "disposition": "replace",
        "stock_id": 1776,
        "status": "reviewed",
        "map_identity": {
            "dataset": "OtherInfo",
            "name": "BLOCKER",
            "parser_version": "0.9.4",
        },
    }
    registry = ReferenceRegistry([row])
    assert registry.map_stock("map.blocker") == 1776
    with pytest.raises(ValueError, match="verified"):
        registry.stock("map.blocker")
    row["map_identity"]["name"] = "HAY_STACK"
    with pytest.raises(ValueError, match="identity"):
        ReferenceRegistry([row]).map_stock("map.blocker")
    row["map_identity"]["name"] = "BLOCKER"
    row["status"] = "candidate"
    with pytest.raises(ValueError, match="reviewed"):
        ReferenceRegistry([row]).map_stock("map.blocker")
