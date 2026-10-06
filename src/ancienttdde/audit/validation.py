"""Validate audit artifacts and references without claiming engine correctness."""

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ancienttdde.common.data import HashRecord, object_value, read_json, read_object
from ancienttdde.common.hashing import hash_inputs, verify_hashes, verify_inputs
from ancienttdde.common.manifest import (
    AuditManifest,
    parse_manifest,
    rebuild_command,
    require_current_versions,
)
from ancienttdde.common.output import project_path
from ancienttdde.registry import ObjectMappings
from ancienttdde.scenario.snapshot import validate_references


def load_config(root: Path) -> dict[str, Any]:
    path = root / "content/audit.toml"
    if not path.is_file():
        raise ValueError(f"Missing audit configuration: {path}")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    if config["schema_version"] != 1:
        raise ValueError("Unsupported content schema")
    return config


def input_paths(config: dict[str, Any]) -> list[str]:
    return [
        "content/audit.toml",
        *(
            config[key]
            for key in ("scenario", "format_seed", "provenance", "classification", "mappings")
        ),
    ]


def current_inputs(root: Path, config: dict[str, Any]) -> list[HashRecord]:
    return hash_inputs(root, input_paths(config), "audit", layer="audit")


def validate_inventory(
    classification: dict[str, Any],
    mappings: dict[str, Any],
    scenario: Mapping[str, Any] | None = None,
    dat: dict[str, Any] | None = None,
) -> None:
    """Check reviewed decisions, then coverage when extracted evidence is available."""
    if classification["schema_version"] != 1 or mappings["schema_version"] != 1:
        raise ValueError("Unsupported inventory schema")
    if not classification["mechanics"] or not mappings["objects"]:
        raise ValueError("Mechanic and object inventories must be nonempty")
    objects = ObjectMappings(mappings["objects"])
    keys: set[str] = set()
    assigned: list[int] = []
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
        missing: list[tuple[int, int]] = []
        for obj in dat["objects"]:
            for cid in obj["civilizations"]:
                if objects.find_legacy(obj["id"], int(cid)) is None:
                    missing.append((obj["id"], int(cid)))
        if missing:
            raise ValueError(f"Missing civilization-aware migration mappings: {missing[:10]}")


def verify_provenance(root: Path, manifest: dict[str, Any]) -> None:
    verify_hashes(root, manifest["files"], "provenance input")


def validate_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = load_config(root)
    provenance = read_json(project_path(root, config["provenance"]))
    verify_provenance(root, provenance)
    classification = read_json(project_path(root, config["classification"]))
    mappings = read_json(project_path(root, config["mappings"]))
    validate_inventory(classification, mappings)
    return config, classification, mappings


def read_audit_manifest(path: Path) -> AuditManifest:
    raw = read_object(path)
    base = parse_manifest(
        raw, kind="legacy-audit", rebuild=rebuild_command("legacy-audit", path.parent)
    )
    summary = object_value(raw.get("summary"), "summary")
    return AuditManifest(**base, kind="legacy-audit", summary=summary)


def validate_report(directory: Path, root: Path) -> AuditManifest:
    """Validate report integrity, current inputs and complete evidence coverage."""
    directory = directory.resolve()
    manifest = read_audit_manifest(project_path(directory, "manifest.json"))
    rebuild = rebuild_command("legacy-audit", directory)
    require_current_versions(manifest, kind="legacy-audit", rebuild=rebuild)
    config, classification, mappings = validate_inputs(root)
    verify_inputs(manifest["inputs"], current_inputs(root, config), "audit")
    if not {"scenario.json", "dat.json"}.issubset(p["path"] for p in manifest["artifacts"]):
        raise ValueError("Audit manifest must record scenario and DAT evidence")
    verify_hashes(directory, manifest["artifacts"], "audit artifact")
    scenario = json.loads((directory / "scenario.json").read_text(encoding="utf-8"))
    dat = json.loads((directory / "dat.json").read_text(encoding="utf-8"))
    validate_inventory(classification, mappings, scenario, dat)
    dangling = validate_references(scenario)
    if dangling:
        raise ValueError(f"Dangling scenario references: {dangling}")
    return manifest
