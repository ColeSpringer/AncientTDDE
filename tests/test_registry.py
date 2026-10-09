import pytest

from ancienttdde.models import MapIdentity, ObjectMapping
from ancienttdde.registry import NameTable, ObjectMappings


def test_mappings_resolve_the_same_legacy_id_by_civilization() -> None:
    mappings = ObjectMappings(
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
    assert mappings.legacy(169, 0)["key"] == "shop.wood"
    assert mappings.legacy(169, 8)["key"] == "wave.hussar"
    with pytest.raises(ValueError, match="verified"):
        mappings.stock("wave.hussar")


def test_unmapped_legacy_objects_are_reported_or_found_absent() -> None:
    mappings = ObjectMappings(
        [
            {
                "key": "tower",
                "legacy_id": 79,
                "civilization_ids": [0],
                "disposition": "keep",
                "stock_id": 79,
                "status": "candidate",
            }
        ]
    )
    assert mappings.find_legacy(79, 0) is not None
    assert mappings.find_legacy(79, 8) is None
    with pytest.raises(ValueError, match="79.*8"):
        mappings.legacy(79, 8)


def test_mappings_reject_ambiguous_rows() -> None:
    rows: list[ObjectMapping] = [
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
        ObjectMappings(rows)


def test_verified_mapping_resolves_its_stock_object() -> None:
    mappings = ObjectMappings(
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
    assert mappings.stock("king") == 434


def test_named_trigger_and_variable_references() -> None:
    names = NameTable()
    names.register("trigger", "initialize", 0)
    names.register("variable", "lives.p1", 0)
    assert names.resolve("trigger", "initialize") == 0
    assert names.resolve("variable", "lives.p1") == 0
    with pytest.raises(ValueError, match="Duplicate"):
        names.register("trigger", "initialize", 1)
    with pytest.raises(ValueError, match="Unknown reference kind"):
        names.register("unit", "king", 1)
    with pytest.raises(ValueError, match="Invalid reference ID"):
        names.register("object", "king", -1)


def test_name_table_lists_one_kinds_identifiers_under_a_key_prefix() -> None:
    names = NameTable()
    names.register("trigger", "lane.p1.spawned", 3)
    names.register("trigger", "lane.p10.spawned", 4)
    names.register("variable", "lane.p1.lives", 5)
    names.register("trigger", "lane.p1.route", 1)
    names.register("trigger", "game.clock", 2)
    assert names.registered("trigger", "lane.p1.") == [3, 1]
    assert names.registered("object", "lane.p1.") == []


def test_map_identity_verification_does_not_approve_gameplay() -> None:
    identity: MapIdentity = {"dataset": "OtherInfo", "name": "BLOCKER", "parser_version": "0.9.4"}
    row: ObjectMapping = {
        "key": "map.blocker",
        "legacy_id": 857,
        "civilization_ids": [9],
        "disposition": "replace",
        "stock_id": 1776,
        "status": "reviewed",
        "map_identity": identity,
    }
    mappings = ObjectMappings([row])
    assert mappings.map_stock("map.blocker") == 1776
    with pytest.raises(ValueError, match="verified"):
        mappings.stock("map.blocker")
    identity["name"] = "HAY_STACK"
    with pytest.raises(ValueError, match="identity"):
        ObjectMappings([row]).map_stock("map.blocker")
    identity["name"] = "BLOCKER"
    row["status"] = "candidate"
    with pytest.raises(ValueError, match="reviewed"):
        ObjectMappings([row]).map_stock("map.blocker")
