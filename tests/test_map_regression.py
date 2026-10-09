import json
from collections import Counter
from pathlib import Path

import pytest

from ancienttdde.map.build import build_map, check_reload, read_manifest
from ancienttdde.map.extract import extract_map
from ancienttdde.map.foundation import migrate_map
from ancienttdde.scenario.snapshot import scenario_digest

ROOT = Path(__file__).resolve().parents[1]


def test_versioned_stock_template_matches_current_migration(tmp_path: Path) -> None:
    template = ROOT / "content/maps/stock-de-template.aoe2scenario"
    assert template.is_file()
    legacy = json.loads((ROOT / "content/maps/legacy-map.json").read_text())
    config = json.loads((ROOT / "content/maps/foundation.json").read_text())
    expected = migrate_map(legacy, config)
    snapshot = check_reload(template, expected)
    assert snapshot["map"]["width"] == snapshot["map"]["height"] == 200
    assert len(snapshot["units"]) == 7421
    counts = Counter(u["unit_const"] for u in snapshot["units"])
    assert counts[857] == 5578
    assert counts[1776] == 0
    assert counts[819] == 55
    assert counts[128] == 57
    assert len(expected.get("anchors", {})) == 359
    migration = expected.get("migration")
    assert migration is not None and migration["terrain_patch_tiles"] == 243
    assert (migration["placement_additions"], migration["placement_removals"]) == (29, 3)
    built = read_manifest(build_map(ROOT, tmp_path / "regression-build") / "manifest.json")
    assert scenario_digest(snapshot) == built["normalized_sha256"]
    assert len(built["validation"]["routes"]) == 74
    assert len(built["validation"]["isolation"]) == 57
    assert not built["validation"]["in_game_verified"]


def test_plain_export_matches_original_when_available() -> None:
    legacy = json.loads((ROOT / "content/maps/legacy-map.json").read_text())
    source_name = legacy["source"]["path"]
    source = ROOT / source_name
    if not source.is_file():
        pytest.skip("Original package is intentionally not committed")
    assert extract_map(source, source_name=source_name) == legacy
    provenance = json.loads((ROOT / "legacy/provenance.json").read_text())
    record = next(r for r in provenance["files"] if r["path"] == source_name)
    assert legacy["source"]["sha256"] == record["sha256"]
