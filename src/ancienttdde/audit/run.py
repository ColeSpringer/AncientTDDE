"""Build reproducible evidence reports from immutable sources and reviewed decisions."""

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ancienttdde.audit.behavior import activation_times, extract_purchases, extract_waves
from ancienttdde.audit.dat import inspect_dat
from ancienttdde.audit.reports import REPORTS, render_reports
from ancienttdde.audit.validation import current_inputs, validate_inputs, validate_inventory
from ancienttdde.common.data import HashRecord, write_json
from ancienttdde.common.hashing import hash_file
from ancienttdde.common.manifest import SCHEMA_VERSION, AuditManifest, versions
from ancienttdde.common.output import prepare_output, project_path, publish
from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.snapshot import ScenarioSnapshot, validate_references

EVIDENCE = ("scenario.json", "dat.json", "behavior.json", "summary.json", "migration.json")


def inspect_evidence(root: Path, config: dict[str, Any]) -> tuple[ScenarioSnapshot, dict[str, Any]]:
    """Extract the scenario and civilization-aware DAT evidence for coverage checks."""
    scenario = inspect_scenario(project_path(root, config["scenario"]))
    dat = inspect_dat(
        project_path(root, config["dat_reference"]),
        set(scenario["references"]["object_ids"]) | set(config.get("extra_object_ids", [])),
        set(scenario["references"]["technology_ids"]),
        project_path(root, config["graphics"]),
    )
    return scenario, dat


def run_audit(root: Path, output: Path | None = None) -> Path:
    """Publish the evidence and reports, and return the directory that holds them."""
    root = root.resolve()
    config, classification, mappings = validate_inputs(root)
    output = prepare_output(
        root, output, config["report_directory"], (*EVIDENCE, *REPORTS), kind="legacy-audit"
    )
    inputs = current_inputs(root, config)
    scenario, dat = inspect_evidence(root, config)
    validate_inventory(classification, mappings, scenario, dat)
    dangling = validate_references(scenario)
    waves = [asdict(w) for w in extract_waves(scenario["triggers"])]
    shop = [
        asdict(p)
        for p in extract_purchases(
            scenario["triggers"], set(classification["purchase_trigger_ids"])
        )
    ]
    _, fires = activation_times(scenario["triggers"])
    behavior = {
        "waves": waves,
        "purchases": shop,
        "mechanics": classification["mechanics"],
        "timer_chain_fire_seconds": {str(k): v for k, v in sorted(fires.items())},
        "reference_findings": dangling,
        "timing_note": (
            "Static timer chains in game-seconds; engine tick ordering requires playtests."
        ),
        "instructions_note": (
            "Messages are evidence of displayed claims, not authoritative behavior."
        ),
    }
    summary: dict[str, object] = {
        "scenario_version": scenario["scenario_version"],
        "map": scenario["map"],
        "triggers": len(scenario["triggers"]),
        "placed_objects": len(scenario["units"]),
        "waves": len(waves),
        "purchase_triggers": len(shop),
        "civilizations_including_gaia": len(dat["civilizations"]),
        "referenced_object_types": len(dat["objects"]),
        "custom_graphic_definitions": len(dat["custom_graphics"]),
        "dangling_references": dangling,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ancienttdde-audit-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, value in zip(EVIDENCE, (scenario, dat, behavior, summary, mappings), strict=True):
            write_json(stage / name, value)
        for name, value in render_reports(scenario, dat, behavior, summary).items():
            (stage / name).write_text(value, encoding="utf-8")
        artifacts = [
            HashRecord(path=p.name, sha256=hash_file(p), size_bytes=p.stat().st_size)
            for p in sorted(stage.iterdir())
        ]
        manifest = AuditManifest(
            schema_version=SCHEMA_VERSION,
            kind="legacy-audit",
            **versions(),
            summary=summary,
            inputs=inputs,
            artifacts=artifacts,
        )
        write_json(stage / "manifest.json", manifest)
        # Publish only after all extraction, checks and rendering have succeeded.
        publish(stage, output, (*EVIDENCE, *REPORTS))
    return output
