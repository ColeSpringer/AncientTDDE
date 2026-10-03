import json

import pytest
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.provenance import hash_file
from ancienttdde.validation import validate_inputs, validate_references, validate_report


@pytest.fixture
def project_report(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "audit.toml").write_text(
        'schema_version = 1\nscenario = "original.aoe2scenario"\n'
        'format_seed = "seed.aoe2scenario"\nprovenance = "provenance.json"\n'
        'classification = "content/classification.json"\nmappings = "content/mappings.json"\n'
    )
    classification = {
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
    mappings = {
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
    scenario = {
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
        "schema_version": 1,
        "inputs": [{"path": p, "sha256": hash_file(tmp_path / p)} for p in inputs],
        "artifacts": [
            {"path": p, "sha256": hash_file(report / p)} for p in ("scenario.json", "dat.json")
        ],
    }
    (report / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path, report


def edit_inventory(root, report, filename, change):
    path = root / "content" / filename
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))
    manifest_path = report / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["inputs"]:
        if record["path"] == f"content/{filename}":
            record["sha256"] = hash_file(path)
    manifest_path.write_text(json.dumps(manifest))


def test_dangling_references_are_not_treated_as_success():
    scenario = {
        "triggers": [{"id": 0}],
        "units": [{"reference_id": 7}],
        "variables": [{"variable_id": 0}],
        "references": {"trigger_ids": [0, 9], "instance_ids": [7, 8], "variable_ids": [0]},
    }
    assert validate_references(scenario) == [
        {"kind": "trigger", "id": 9},
        {"kind": "instance", "id": 8},
    ]


def test_report_validation_detects_modified_artifact(project_report):
    root, report = project_report
    source = report / "scenario.json"
    validate_report(report, root)
    source.write_text("{}")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_report(report, root)


@pytest.mark.parametrize("filename", ["classification.json", "mappings.json", "audit.toml"])
def test_cli_rejects_report_after_content_input_changes(project_report, filename):
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
        ("classification.json", lambda d: d.update(mechanics=[]), "nonempty"),
        ("mappings.json", lambda d: d.update(objects=[]), "nonempty"),
        (
            "classification.json",
            lambda d: d["mechanics"][0].update(disposition="ignore"),
            "disposition",
        ),
        (
            "classification.json",
            lambda d: d["mechanics"][0]["trigger_ids"].append(0),
            "exactly once",
        ),
        (
            "classification.json",
            lambda d: d["purchase_trigger_ids"].append(1),
            "Duplicate purchase",
        ),
    ],
)
def test_content_validation_rejects_invalid_inventories(project_report, filename, change, message):
    root, report = project_report
    edit_inventory(root, report, filename, change)
    with pytest.raises(ValueError, match=message):
        validate_inputs(root)


@pytest.mark.parametrize(
    ("filename", "change", "message"),
    [
        (
            "classification.json",
            lambda d: d["mechanics"][0]["trigger_ids"].pop(0),
            "every trigger",
        ),
        (
            "mappings.json",
            lambda d: d["objects"][0]["civilization_ids"].pop(),
            "civilization-aware",
        ),
        (
            "classification.json",
            lambda d: d["purchase_trigger_ids"].append(9),
            "purchase trigger",
        ),
    ],
)
def test_report_validation_checks_inventory_coverage(project_report, filename, change, message):
    root, report = project_report
    edit_inventory(root, report, filename, change)
    result = CliRunner().invoke(app, ["validate", "--root", str(root), "--report", str(report)])
    assert result.exit_code == 1
    assert message in result.output
