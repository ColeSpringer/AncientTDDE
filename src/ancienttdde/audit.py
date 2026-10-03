"""Build reproducible evidence reports from immutable sources and reviewed decisions."""

import json
import tempfile
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from ancienttdde.inspection.behavior import activation_times, extract_purchases, extract_waves
from ancienttdde.inspection.dat import inspect_dat
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.provenance import hash_file, project_path
from ancienttdde.validation import (
    input_paths,
    validate_inputs,
    validate_inventory,
    validate_references,
)


def inspect_evidence(root: Path, config: dict) -> tuple[dict, dict]:
    """Extract the scenario and civilization-aware DAT evidence for coverage checks."""
    scenario = inspect_scenario(project_path(root, config["scenario"]))
    dat = inspect_dat(
        project_path(root, config["dat_reference"]),
        set(scenario["references"]["object_ids"]) | set(config.get("extra_object_ids", [])),
        set(scenario["references"]["technology_ids"]),
        project_path(root, config["graphics"]),
    )
    return scenario, dat


def write_json(path: Path, value) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        handle.write("\n")


def run_audit(root: Path, output: Path | None = None) -> dict:
    root = root.resolve()
    config, classification, mappings = validate_inputs(root)
    output = output.resolve() if output else project_path(root, config["report_directory"])
    if output == root or any(
        output.is_relative_to(root / name)
        for name in ("legacy", "content", "src", "tools", "docs", "tests", ".git")
    ):
        raise ValueError("Audit output must be outside source and immutable input directories")
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
    summary = {
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
        for name, value in [
            ("scenario.json", scenario),
            ("dat.json", dat),
            ("behavior.json", behavior),
            ("summary.json", summary),
            ("migration.json", mappings),
        ]:
            write_json(stage / name, value)
        from ancienttdde.reports import render_reports

        for name, value in render_reports(scenario, dat, behavior, summary).items():
            (stage / name).write_text(value, encoding="utf-8")
        artifacts = [
            {"path": p.name, "sha256": hash_file(p), "size_bytes": p.stat().st_size}
            for p in sorted(stage.iterdir())
        ]
        manifest = {
            "schema_version": 1,
            "tool_version": version("ancienttdde"),
            "parser_version": version("AoE2ScenarioParser"),
            "summary": summary,
            "inputs": [
                {"path": path, "sha256": hash_file(project_path(root, path))}
                for path in input_paths(config)
            ],
            "artifacts": artifacts,
        }
        write_json(stage / "manifest.json", manifest)
        # Publish only after all extraction, checks and rendering have succeeded.
        output.mkdir(parents=True, exist_ok=True)
        for path in sorted(stage.iterdir(), key=lambda p: p.name == "manifest.json"):
            path.replace(output / path.name)
    return manifest
