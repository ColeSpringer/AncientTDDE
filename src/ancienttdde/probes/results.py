"""Keep attributed observations separate from automated artifact validation."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ancienttdde.common.data import digest, read_object, rows, text_field, write_json
from ancienttdde.common.output import project_path
from ancienttdde.probes.models import (
    CaseResults,
    Outcome,
    ProbeManifest,
    ProbeResults,
    ProbeRun,
)
from ancienttdde.probes.suite import read_manifest, reload_probe


def empty_results(manifest: ProbeManifest) -> ProbeResults:
    return {
        "schema_version": 1,
        "cases": [
            CaseResults(id=case_id, runs=[])
            for probe in manifest["probes"]
            for case_id in probe["case_ids"]
        ],
    }


def case_ids(manifest: ProbeManifest) -> list[str]:
    return [case_id for probe in manifest["probes"] for case_id in probe["case_ids"]]


def read_results(directory: Path, expected: list[str]) -> ProbeResults:
    """Read recorded observations, which must cover the expected case IDs in order."""
    value = read_object(project_path(directory, "results.json"))
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported probe results schema")
    cases: list[CaseResults] = []
    for row in rows(value.get("cases"), "cases"):
        runs: list[ProbeRun] = []
        for run in rows(row.get("runs"), "runs"):
            status = Outcome(text_field(run, "status"))
            recorded_at = text_field(run, "recorded_at")
            if datetime.fromisoformat(recorded_at).tzinfo is None:
                raise ValueError("Recorded result time must include a timezone")
            runs.append(
                ProbeRun(
                    status=status.value,
                    game_build=text_field(run, "game_build"),
                    tester=text_field(run, "tester"),
                    notes=text_field(run, "notes"),
                    recorded_at=recorded_at,
                    scenario_sha256=digest(run.get("scenario_sha256")),
                )
            )
        cases.append(CaseResults(id=text_field(row, "id"), runs=runs))
    if [c["id"] for c in cases] != expected:
        raise ValueError("Probe results must cover the current case list exactly once")
    return ProbeResults(schema_version=1, cases=cases)


def record_result(
    directory: Path, case_id: str, status: str, *, game_build: str, tester: str, notes: str
) -> ProbeRun:
    directory = directory.resolve()
    outcome = Outcome(status)
    if not game_build.strip() or not tester.strip():
        raise ValueError("A game build and tester are required for an observed result")
    if not notes.strip():
        raise ValueError("Observation notes are required")
    manifest = read_manifest(project_path(directory, "manifest.json"))
    probe = next((p for p in manifest["probes"] if case_id in p["case_ids"]), None)
    if probe is None:
        raise ValueError(f"Unknown probe case: {case_id}")
    # A result belongs to the inspected scenario, not just to an editable manifest label.
    reload_probe(directory, probe)
    results = read_results(directory, case_ids(manifest))
    destination = project_path(directory, "results.json")
    if (directory / "results.json").is_symlink():
        raise ValueError("Probe results must be a regular file, not a symlink")
    run: ProbeRun = {
        "status": outcome.value,
        "game_build": game_build.strip(),
        "tester": tester.strip(),
        "notes": notes.strip(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "scenario_sha256": probe["normalized_sha256"],
    }
    next(c for c in results["cases"] if c["id"] == case_id)["runs"].append(run)
    with TemporaryDirectory(prefix=".observations-", dir=directory) as temporary:
        pending = Path(temporary) / "results.json"
        write_json(pending, results)
        pending.replace(destination)
    return run
