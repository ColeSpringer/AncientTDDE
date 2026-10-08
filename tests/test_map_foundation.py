import copy

import pytest
from conftest import FoundationInputs

from ancienttdde.scenario.snapshot import MapUnit


def test_migration_preserves_geometry_and_references_and_replaces_custom_objects(
    foundation_inputs: FoundationInputs,
) -> None:
    from ancienttdde.map.foundation import migrate_map, validate_map

    legacy, config = foundation_inputs
    original = copy.deepcopy(legacy)
    result = migrate_map(legacy, config)
    assert legacy == original
    assert result["map"]["tiles"][7 * 16 + 3] == [4, 2, 0]
    assert result["map"]["tiles"][2 * 16 + 12] == [0, 0, -1]
    units = {u["reference_id"]: u for u in result["units"]}
    assert units[0]["unit_const"] == 1776
    assert units[10]["unit_const"] == 598
    assert units[11]["unit_const"] == 128
    assert units[12]["unit_const"] == 819
    assert units[12]["player_id"] == 0
    assert units[12].get("caption_string") == "+4 attack: 1 King"
    assert units[14]["garrisoned_in_id"] == 13
    assert units[0]["rotation"] == 1.5
    assert result.get("anchors", {})["lane.p1.life"].get("reference_id") == 10
    report = validate_map(result, config)
    assert report["routes"][0]["reachable"] is True
    assert report["isolation"][0]["contained"] is True


def test_anchors_can_name_several_points(foundation_inputs: FoundationInputs) -> None:
    from ancienttdde.map.foundation import migrate_map, validate_map

    legacy, config = foundation_inputs
    config["anchors"]["lane.p1.kings"] = {"points": [[2.5, 3.5], [2.5, 6.5]]}
    result = migrate_map(legacy, config)
    assert result.get("anchors", {})["lane.p1.kings"] == {"points": [[2.5, 3.5], [2.5, 6.5]]}
    validate_map(result, config)


def test_isolation_can_start_from_every_point_of_an_anchor(
    foundation_inputs: FoundationInputs,
) -> None:
    from ancienttdde.map.foundation import migrate_map, validate_map

    legacy, config = foundation_inputs
    # An arrival and its walk target on the siege islet; the second point lies off it.
    config["anchors"]["siege.p1.arrivals"] = {"points": [[12.5, 2.5], [11.5, 1.5]]}
    config["isolation"].append(
        {
            "key": "arrivals",
            "start": "siege.p1.arrivals",
            "medium": "land",
            "region": [11, 1, 13, 3],
        }
    )
    report = validate_map(migrate_map(legacy, config), config)
    assert report["isolation"][-1] == {"key": "arrivals", "contained": True, "reachable_tiles": 9}
    config["anchors"]["siege.p1.arrivals"]["points"].append([2.5, 3.5])
    with pytest.raises(ValueError, match="arrivals: failed land isolation"):
        validate_map(migrate_map(legacy, config), config)


@pytest.mark.parametrize(
    ("points", "message"),
    [
        ([[2.5, 3.5], [3.5, 16.0]], "Anchor outside map: lane.p1.kings"),
        ([[2.5, 3.5], [3.5]], "Anchor outside map: lane.p1.kings"),
        ([], "Anchor needs a point or region: lane.p1.kings"),
    ],
)
def test_anchor_points_must_lie_on_the_map(
    foundation_inputs: FoundationInputs, points: list[list[float]], message: str
) -> None:
    from ancienttdde.map.foundation import migrate_map

    legacy, config = foundation_inputs
    config["anchors"]["lane.p1.kings"] = {"points": points}
    with pytest.raises(ValueError, match=f"^{message}$"):
        migrate_map(legacy, config)


def test_blocked_routes_fail_validation(foundation_inputs: FoundationInputs) -> None:
    from ancienttdde.map.foundation import migrate_map, validate_map

    legacy, config = foundation_inputs
    result = migrate_map(legacy, config)
    for y in [7, 9]:
        unit: MapUnit = {**result["units"][0], "reference_id": 100 + y, "y": y + 0.5}
        result["units"].append(unit)
    with pytest.raises(ValueError, match="lane.p1.*route"):
        validate_map(result, config)


def test_connected_siege_islets_fail_validation(foundation_inputs: FoundationInputs) -> None:
    from ancienttdde.map.foundation import migrate_map, validate_map

    legacy, config = foundation_inputs
    result = migrate_map(legacy, config)
    result["map"]["tiles"][2 * 16 + 10] = [0, 0, -1]
    with pytest.raises(ValueError, match="siege.p1.1.*isolation"):
        validate_map(result, config)


@pytest.mark.parametrize(
    "defect",
    [
        "unknown_object",
        "unknown_terrain",
        "duplicate_instance",
        "dangling_garrison",
        "missing_anchor_instance",
        "out_of_bounds",
        "bad_patch",
    ],
)
def test_invalid_map_inputs_fail_before_generation(
    foundation_inputs: FoundationInputs, defect: str
) -> None:
    from ancienttdde.map.foundation import migrate_map

    legacy, config = foundation_inputs
    if defect == "unknown_object":
        legacy["units"][0]["unit_const"] = 9999
    elif defect == "unknown_terrain":
        legacy["map"]["tiles"][0][0] = 9999
    elif defect == "duplicate_instance":
        legacy["units"][1]["reference_id"] = 0
    elif defect == "dangling_garrison":
        legacy["units"][-1]["garrisoned_in_id"] = 9999
    elif defect == "missing_anchor_instance":
        config["anchors"]["lane.p1.life"]["reference_id"] = 9999
    elif defect == "out_of_bounds":
        config["anchors"]["lane.p1.spawn"]["point"] = [16.0, 8.5]
    elif defect == "bad_patch":
        config["terrain_patches"][0]["region"] = [1, 1, 3, 3]
    with pytest.raises(ValueError):
        migrate_map(legacy, config)
