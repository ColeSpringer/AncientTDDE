"""Validate audit artifacts and references without claiming engine correctness."""

import json
import tomllib
from pathlib import Path

from ancienttdde.inspection.dat import read_json
from ancienttdde.provenance import hash_file, project_path, verify_provenance
from ancienttdde.registry import ReferenceRegistry


def load_config(root: Path) -> dict:
    path = root / "content/audit.toml"
    if not path.is_file():
        raise ValueError(f"Missing audit configuration: {path}")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    if config["schema_version"] != 1:
        raise ValueError("Unsupported content schema")
    return config


def input_paths(config: dict) -> list[str]:
    return [
        "content/audit.toml",
        *(
            config[key]
            for key in ("scenario", "format_seed", "provenance", "classification", "mappings")
        ),
    ]


def validate_inventory(
    classification: dict,
    mappings: dict,
    scenario: dict | None = None,
    dat: dict | None = None,
) -> None:
    """Check reviewed decisions, then coverage when extracted evidence is available."""
    if classification["schema_version"] != 1 or mappings["schema_version"] != 1:
        raise ValueError("Unsupported inventory schema")
    if not classification["mechanics"] or not mappings["objects"]:
        raise ValueError("Mechanic and object inventories must be nonempty")
    registry = ReferenceRegistry(mappings["objects"])
    keys = set()
    assigned = []
    for row in classification["mechanics"]:
        if not row.get("key") or row["key"] in keys:
            raise ValueError("Every mechanic needs a unique nonempty key")
        keys.add(row["key"])
        if row["disposition"] not in {"keep", "replace", "drop"}:
            raise ValueError(f"Invalid mechanic disposition: {row['key']}")
        if not row.get("reason") or not row.get("migration"):
            raise ValueError("Every mechanic needs a review reason and migration decision")
        if not row["trigger_ids"]:
            raise ValueError(f"Missing mechanic trigger IDs: {row['key']}")
        assigned.extend(row["trigger_ids"])
    if any(type(identifier) is not int or identifier < 0 for identifier in assigned):
        raise ValueError("Invalid mechanic trigger ID")
    if len(assigned) != len(set(assigned)):
        raise ValueError("Mechanic inventory must classify every trigger exactly once")
    purchases = classification["purchase_trigger_ids"]
    if any(type(identifier) is not int or identifier < 0 for identifier in purchases):
        raise ValueError("Invalid purchase trigger ID")
    if len(purchases) != len(set(purchases)):
        raise ValueError("Duplicate purchase trigger ID")
    if not set(purchases).issubset(assigned):
        raise ValueError("Unknown purchase trigger IDs in mechanic inventory")
    if scenario is not None and set(assigned) != {t["id"] for t in scenario["triggers"]}:
        raise ValueError("Mechanic inventory must classify every trigger exactly once")
    if dat is not None:
        missing = []
        for obj in dat["objects"]:
            for cid in obj["civilizations"]:
                try:
                    registry.legacy(obj["id"], int(cid))
                except KeyError:
                    missing.append((obj["id"], int(cid)))
        if missing:
            raise ValueError(f"Missing civilization-aware migration mappings: {missing[:10]}")


def validate_inputs(root: Path) -> tuple[dict, dict, dict]:
    config = load_config(root)
    provenance = read_json(project_path(root, config["provenance"]))
    verify_provenance(root, provenance)
    classification = read_json(project_path(root, config["classification"]))
    mappings = read_json(project_path(root, config["mappings"]))
    validate_inventory(classification, mappings)
    return config, classification, mappings


def validate_references(scenario: dict) -> list[dict]:
    known = {
        "trigger": {t["id"] for t in scenario["triggers"]},
        "instance": {u["reference_id"] for u in scenario["units"]},
        "variable": {v["variable_id"] for v in scenario["variables"]},
    }
    return [
        {"kind": kind, "id": identifier}
        for kind, available in known.items()
        for identifier in scenario["references"][f"{kind}_ids"]
        if identifier not in available
    ]


def validate_report(directory: Path, root: Path) -> dict:
    """Validate report integrity, current inputs and complete evidence coverage."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported audit schema")
    config, classification, mappings = validate_inputs(root)
    inputs = manifest["inputs"]
    if len(inputs) != len(input_paths(config)) or {p["path"] for p in inputs} != set(
        input_paths(config)
    ):
        raise ValueError("Audit manifest must record all configured inputs; rerun audit")
    for record in inputs:
        path = project_path(root, record["path"])
        if not path.is_file() or hash_file(path) != record["sha256"]:
            raise ValueError(f"Audit input SHA-256 mismatch: {record['path']}")
    if not {"scenario.json", "dat.json"}.issubset(p["path"] for p in manifest["artifacts"]):
        raise ValueError("Audit manifest must record scenario and DAT evidence")
    for record in manifest["artifacts"]:
        path = project_path(directory, record["path"])
        if not path.is_file() or hash_file(path) != record["sha256"]:
            raise ValueError(f"Audit artifact SHA-256 mismatch: {record['path']}")
    scenario = json.loads((directory / "scenario.json").read_text(encoding="utf-8"))
    dat = json.loads((directory / "dat.json").read_text(encoding="utf-8"))
    validate_inventory(classification, mappings, scenario, dat)
    dangling = validate_references(scenario)
    if dangling:
        raise ValueError(f"Dangling scenario references: {dangling}")
    return manifest
