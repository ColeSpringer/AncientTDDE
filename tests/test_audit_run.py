import json
from functools import partial
from pathlib import Path

import pytest

from ancienttdde.audit.run import run_audit
from ancienttdde.audit.validation import read_audit_manifest, validate_report
from ancienttdde.common.manifest import AuditManifest
from ancienttdde.common.worker import run_module, run_parallel

type Audits = tuple[Path, Path, AuditManifest, AuditManifest]


@pytest.fixture(scope="module")
def real_audits(tmp_path_factory: pytest.TempPathFactory) -> Audits:
    root = Path(__file__).resolve().parents[1]
    if not (root / "legacy/reference/dat-verified/manifest.json").is_file():
        pytest.skip("Ignored original package and verified DAT export are required")
    destination = tmp_path_factory.mktemp("audit")
    # Two independent runs, the second through the CLI in its own process, show the audit
    # is reproducible.
    directory, output = run_parallel(
        (
            partial(run_audit, root, destination / "first"),
            partial(
                run_module,
                "ancienttdde",
                "audit",
                "--root",
                str(root),
                "--output",
                str(destination / "unused/../second"),
                label="Audit",
            ),
        )
    )
    # Both name the directory they published, resolved, without reading the configuration
    # again after publishing.
    assert directory == destination / "first"
    assert f"Reports: {destination / 'second'}\n" in output
    first = read_audit_manifest(directory / "manifest.json")
    second = read_audit_manifest(destination / "second/manifest.json")
    return root, destination, first, second


def test_real_audit_is_reproducible_and_reloadable(real_audits: Audits) -> None:
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


def test_reviewed_behavior_snapshots_match_the_real_scenario(real_audits: Audits) -> None:
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


def test_output_cannot_overwrite_immutable_inputs(real_audits: Audits) -> None:
    root, _, _, _ = real_audits
    with pytest.raises(ValueError, match="outside source"):
        run_audit(root, root / "legacy/original/reports")
