import json
from pathlib import Path

import pytest

from ancienttdde.audit import run_audit
from ancienttdde.validation import validate_report


@pytest.fixture(scope="module")
def real_audits(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    if not (root / "legacy/reference/dat-verified/manifest.json").is_file():
        pytest.skip("Ignored original package and verified DAT export are required")
    destination = tmp_path_factory.mktemp("audit")
    first = run_audit(root, destination / "first")
    second = run_audit(root, destination / "second")
    return root, destination, first, second


def test_real_audit_is_reproducible_and_reloadable(real_audits):
    root, destination, first, second = real_audits
    assert first == second
    assert validate_report(destination / "first", root) == first
    assert "content/audit.toml" in {record["path"] for record in first["inputs"]}
    assert first["summary"]["triggers"] == 1018
    assert first["summary"]["waves"] == 56
    assert first["summary"]["purchase_triggers"] == 252
    assert first["summary"]["civilizations_including_gaia"] == 40
    assert first["summary"]["referenced_object_types"] == 292
    assert first["summary"]["dangling_references"] == []


def test_reviewed_behavior_snapshots_match_the_real_scenario(real_audits):
    root, destination, _, _ = real_audits
    behavior = json.loads((destination / "first/behavior.json").read_text())
    assert (
        behavior["waves"] == json.loads((root / "content/legacy/waves.json").read_text())["waves"]
    )
    assert (
        behavior["purchases"]
        == json.loads((root / "content/legacy/purchases.json").read_text())["purchases"]
    )
    assert behavior["timer_chain_fire_seconds"]["1010"] == 6435
    waves = {row["key"]: row for row in behavior["waves"]}
    assert waves["9-B"]["stop_trigger_id"] == 635
    assert waves["1-E"]["interval_seconds"] == 5
    assert waves["boss-10"]["start_seconds"] == 6365


def test_output_cannot_overwrite_immutable_inputs(real_audits):
    root, _, _, _ = real_audits
    with pytest.raises(ValueError, match="outside source"):
        run_audit(root, root / "legacy/original/reports")
