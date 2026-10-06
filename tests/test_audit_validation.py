import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from conftest import snapshot
from typer.testing import CliRunner

from ancienttdde.audit.validation import validate_inputs, validate_report, verify_provenance
from ancienttdde.cli import app
from ancienttdde.common.data import read_object, rows
from ancienttdde.common.hashing import hash_file, hash_inputs
from ancienttdde.common.manifest import versions
from ancienttdde.scenario.snapshot import validate_references

type Inventory = dict[str, object]
type ProjectReport = tuple[Path, Path]


@pytest.fixture
def project_report(tmp_path: Path) -> ProjectReport:
    content = tmp_path / "content"
    content.mkdir()
    (content / "audit.toml").write_text(
        'schema_version = 1\nscenario = "original.aoe2scenario"\n'
        'format_seed = "seed.aoe2scenario"\nprovenance = "provenance.json"\n'
        'classification = "content/classification.json"\nmappings = "content/mappings.json"\n'
    )
    classification: Inventory = {
        "schema_version": 1,
        "mechanics": [
            {
                "key": "shop",
                "disposition": "replace",
                "reason": "Preserve the shop",
                "migration": "Exact payments",
                "trigger_ids": [0, 1],
            }
        ],
        "purchase_trigger_ids": [1],
    }
    mappings: Inventory = {
        "schema_version": 1,
        "objects": [
            {
                "key": "tower",
                "legacy_id": 79,
                "civilization_ids": [0, 8],
                "disposition": "replace",
                "stock_id": 79,
                "status": "candidate",
            }
        ],
    }
    (content / "classification.json").write_text(json.dumps(classification))
    (content / "mappings.json").write_text(json.dumps(mappings))
    sources = ["original.aoe2scenario", "seed.aoe2scenario"]
    for name in sources:
        (tmp_path / name).write_bytes(b"immutable scenario fixture")
    (tmp_path / "provenance.json").write_text(
        json.dumps({"files": [{"path": p, "sha256": hash_file(tmp_path / p)} for p in sources]})
    )
    report = tmp_path / ".build/audit"
    report.mkdir(parents=True)
    scenario: Inventory = {
        "triggers": [{"id": 0}, {"id": 1}],
        "units": [],
        "variables": [],
        "references": {"trigger_ids": [0], "instance_ids": [], "variable_ids": []},
    }
    (report / "scenario.json").write_text(json.dumps(scenario))
    (report / "dat.json").write_text(
        json.dumps({"objects": [{"id": 79, "civilizations": {"0": {}, "8": {}}}]})
    )
    inputs = [
        "content/audit.toml",
        *sources,
        "provenance.json",
        "content/classification.json",
        "content/mappings.json",
    ]
    manifest = {
        "schema_version": 2,
        "kind": "legacy-audit",
        **versions(),
        "summary": {"triggers": 2},
        "inputs": hash_inputs(tmp_path, inputs, "audit", layer="audit"),
        "artifacts": [
            {"path": p, "sha256": hash_file(report / p)} for p in ("scenario.json", "dat.json")
        ],
    }
    (report / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path, report


def items(inventory: Inventory, key: str) -> list[Inventory]:
    return rows(inventory.get(key), key)


def numbers(row: Inventory, key: str) -> list[int]:
    value = row.get(key)
    assert isinstance(value, list)
    return cast(list[int], value)


def without_mechanics(classification: Inventory) -> None:
    classification["mechanics"] = []


def without_objects(mappings: Inventory) -> None:
    mappings["objects"] = []


def unknown_disposition(classification: Inventory) -> None:
    items(classification, "mechanics")[0]["disposition"] = "ignore"


def trigger_classified_twice(classification: Inventory) -> None:
    numbers(items(classification, "mechanics")[0], "trigger_ids").append(0)


def purchase_listed_twice(classification: Inventory) -> None:
    numbers(classification, "purchase_trigger_ids").append(1)


def unclassified_trigger(classification: Inventory) -> None:
    numbers(items(classification, "mechanics")[0], "trigger_ids").pop(0)


def civilization_unmapped(mappings: Inventory) -> None:
    numbers(items(mappings, "objects")[0], "civilization_ids").pop()


def unknown_purchase(classification: Inventory) -> None:
    numbers(classification, "purchase_trigger_ids").append(9)


def edit_inventory(
    root: Path, report: Path, filename: str, change: Callable[[Inventory], None]
) -> None:
    path = root / "content" / filename
    data = read_object(path)
    change(data)
    path.write_text(json.dumps(data))
    manifest_path = report / "manifest.json"
    manifest = read_object(manifest_path)
    for record in rows(manifest.get("inputs"), "inputs"):
        if record.get("path") == f"content/{filename}":
            record["sha256"] = hash_file(path)
    manifest_path.write_text(json.dumps(manifest))


def test_changed_and_missing_provenance_inputs_fail_verification(tmp_path: Path) -> None:
    source = tmp_path / "original.dat"
    source.write_bytes(b"original")
    manifest = {"files": [{"path": "original.dat", "sha256": hash_file(source)}]}
    verify_provenance(tmp_path, manifest)
    source.write_bytes(b"modified")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_provenance(tmp_path, manifest)
    source.unlink()
    with pytest.raises(ValueError, match="Missing"):
        verify_provenance(tmp_path, manifest)


def test_report_validation_rejects_older_manifest_schemas(project_report: ProjectReport) -> None:
    root, report = project_report
    manifest_path = report / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    # Schema-1 audit manifests carried no kind.
    manifest["schema_version"] = 1
    del manifest["kind"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="schema 1; expected 2, rebuild with ancienttdde audit"):
        validate_report(report, root)


def test_dangling_references_are_not_treated_as_success(payments_suite: Path) -> None:
    scenario = snapshot(payments_suite / "payments.aoe2scenario")
    assert validate_references(scenario) == []
    scenario["references"]["trigger_ids"].append(9999)
    scenario["references"]["instance_ids"].append(8888)
    assert validate_references(scenario) == [
        {"kind": "trigger", "id": 9999},
        {"kind": "instance", "id": 8888},
    ]


def test_a_report_made_by_other_audit_code_must_be_rerun(project_report: ProjectReport) -> None:
    root, report = project_report
    manifest_path = report / "manifest.json"
    manifest = read_object(manifest_path)
    records = rows(manifest.get("inputs"), "inputs")
    record = next(r for r in records if r.get("path") == "ancienttdde/audit/run.py")
    record["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Audit input SHA-256 mismatch: ancienttdde/audit/run.py"):
        validate_report(report, root)
    manifest["inputs"] = [r for r in records if not str(r.get("path")).startswith("ancienttdde/")]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="must record every current input"):
        validate_report(report, root)


def test_a_report_made_with_other_tools_must_be_rerun(project_report: ProjectReport) -> None:
    root, report = project_report
    manifest_path = report / "manifest.json"
    manifest = read_object(manifest_path)
    manifest["python_version"] = "3.0.0"
    manifest_path.write_text(json.dumps(manifest))
    expected = "legacy-audit was built with Python 3.0.0, .+ rebuild with ancienttdde audit"
    with pytest.raises(ValueError, match=expected):
        validate_report(report, root)


def test_report_validation_detects_modified_artifact(project_report: ProjectReport) -> None:
    root, report = project_report
    source = report / "scenario.json"
    validate_report(report, root)
    source.write_text("{}")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_report(report, root)


@pytest.mark.parametrize("filename", ["classification.json", "mappings.json", "audit.toml"])
def test_cli_rejects_report_after_content_input_changes(
    project_report: ProjectReport, filename: str
) -> None:
    root, report = project_report
    path = root / "content" / filename
    with path.open("a") as handle:
        handle.write("\n# changed config\n" if filename.endswith("toml") else "\n ")
    result = CliRunner().invoke(app, ["validate", "--root", str(root), "--report", str(report)])
    assert result.exit_code == 1
    assert "Audit input SHA-256 mismatch" in result.output


@pytest.mark.parametrize(
    ("filename", "change", "message"),
    [
        ("classification.json", without_mechanics, "nonempty"),
        ("mappings.json", without_objects, "nonempty"),
        ("classification.json", unknown_disposition, "disposition"),
        ("classification.json", trigger_classified_twice, "exactly once"),
        ("classification.json", purchase_listed_twice, "Duplicate purchase"),
    ],
)
def test_content_validation_rejects_invalid_inventories(
    project_report: ProjectReport,
    filename: str,
    change: Callable[[Inventory], None],
    message: str,
) -> None:
    root, report = project_report
    edit_inventory(root, report, filename, change)
    with pytest.raises(ValueError, match=message):
        validate_inputs(root)


@pytest.mark.parametrize(
    ("filename", "change", "message"),
    [
        ("classification.json", unclassified_trigger, "every trigger"),
        ("mappings.json", civilization_unmapped, "civilization-aware"),
        ("classification.json", unknown_purchase, "purchase trigger"),
    ],
)
def test_report_validation_checks_inventory_coverage(
    project_report: ProjectReport,
    filename: str,
    change: Callable[[Inventory], None],
    message: str,
) -> None:
    root, report = project_report
    edit_inventory(root, report, filename, change)
    result = CliRunner().invoke(app, ["validate", "--root", str(root), "--report", str(report)])
    assert result.exit_code == 1
    assert message in result.output
