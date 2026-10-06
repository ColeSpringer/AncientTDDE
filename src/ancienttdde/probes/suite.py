"""Read a generated probe suite: its manifest and its reloaded, checked scenarios."""

import json
from collections.abc import Sequence
from pathlib import Path

from ancienttdde.common.data import digest, read_object, rows, text_field
from ancienttdde.common.manifest import parse_manifest, rebuild_command
from ancienttdde.common.output import project_path
from ancienttdde.probes.arena import PROBE_OBJECTS, footprint_sizes, grid_offset, survival_ids
from ancienttdde.probes.catalog import select_probes
from ancienttdde.probes.models import ProbeManifest, ProbeRecord
from ancienttdde.scenario.checks import (
    require_custom_victory,
    require_no_dependencies,
    require_unique_placements,
    require_version,
)
from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.objects import stock
from ancienttdde.scenario.snapshot import ScenarioSnapshot, content_digest, validate_references


def rebuild(directory: Path, selection: Sequence[str]) -> str:
    """Name the command that rebuilds a suite in place, with its selection when partial."""
    catalog = [p.id.value for p in select_probes(None)]
    options = [] if list(selection) == catalog else [f"--only {name}" for name in selection]
    return rebuild_command("mechanics-probes", directory, options)


def listed_probes(raw: dict[str, object]) -> list[str]:
    """Return the probe IDs a manifest of any schema lists, or none if it lists them oddly."""
    try:
        return [text_field(row, "id") for row in rows(raw.get("probes"), "probes")]
    except ValueError:
        return []


def read_manifest(path: Path) -> ProbeManifest:
    raw = read_object(path)
    base = parse_manifest(
        raw, kind="mechanics-probes", rebuild=rebuild(path.parent, listed_probes(raw))
    )
    records: list[ProbeRecord] = []
    for row in rows(raw.get("probes"), "probes"):
        name = text_field(row, "id")
        definition = select_probes([name])[0]
        expected_ids = [c.id for c in definition.cases]
        if row.get("case_ids") != expected_ids:
            raise ValueError(f"Probe case coverage differs from current definitions: {name}")
        if row.get("scenario") != f"{name}.aoe2scenario" or row.get("snapshot") != f"{name}.json":
            raise ValueError("Unexpected probe artifact path")
        records.append(
            ProbeRecord(
                id=name,
                scenario=f"{name}.aoe2scenario",
                snapshot=f"{name}.json",
                normalized_sha256=digest(row.get("normalized_sha256")),
                case_ids=expected_ids,
            )
        )
    if not records or len({p["id"] for p in records}) != len(records):
        raise ValueError("Probe manifest must list distinct, nonempty probes")
    if raw.get("xs_checked") is not True or raw.get("in_game_verified") is not False:
        raise ValueError("Probe manifest must distinguish static validation from game observations")
    return ProbeManifest(
        **base,
        kind="mechanics-probes",
        probes=records,
        xs_checked=True,
        in_game_verified=False,
    )


def inspect_probe(path: Path) -> ScenarioSnapshot:
    snapshot = inspect_scenario(path, include_terrain=True)
    findings = validate_references(snapshot)
    if findings:
        raise ValueError(f"Probe has dangling references: {findings}")
    require_version(snapshot)
    if snapshot["map"]["width"] != 64 or snapshot["map"]["height"] != 64:
        raise ValueError("Probe must be a 64x64 scenario")
    require_custom_victory(snapshot, conditions_required=False)
    if snapshot["options"] != {
        "lock_teams": True,
        "allow_players_choose_teams": False,
        "random_start_points": False,
        "secondary_game_modes": 0,
        "legacy_execution_order": False,
        "all_techs": False,
        "victory_custom_conditions_required": False,
        "computer_personalities_locked": True,
    }:
        raise ValueError("Probe settings must preserve fixed teams and standard technology rules")
    require_no_dependencies(snapshot, allow_embedded_xs=True)
    if not snapshot["players"][1]["human"] or any(p["human"] for p in snapshot["players"][2:]):
        raise ValueError("Probe must be testable solo as P1")
    active = {p["player_id"] for p in snapshot["players"] if p["active"]}
    counted = survival_ids()
    surviving = {u["player_id"] for u in snapshot["units"] if u["unit_const"] in counted}
    if defeated := active - surviving:
        raise ValueError(
            "Probe has active players the engine defeats at game start, which would satisfy "
            f"conquest or let them receive standard starts: {sorted(defeated)}"
        )
    for ai in snapshot["embedded_ai"][1:]:
        if (
            ai["name"] != "Ancient TD Passive"
            or not ai["script"].strip()
            # Type 0 runs the embedded custom script.
            or (ai["type"] != 0)
        ):
            raise ValueError("Every computer must contain its passive AI")
    require_unique_placements(snapshot)
    known = {stock(key, PROBE_OBJECTS) for key in PROBE_OBJECTS}
    if any(u["unit_const"] not in known for u in snapshot["units"]):
        raise ValueError("Probe contains an unknown stock object")
    sizes = footprint_sizes()
    for unit in snapshot["units"]:
        if (size := sizes.get(unit["unit_const"])) is not None:
            offset = grid_offset(size)
            if (unit["x"] % 1, unit["y"] % 1) != (offset, offset):
                raise ValueError(
                    f"Probe places object {unit['reference_id']} off its {size}x{size} footprint "
                    f"grid at ({unit['x']}, {unit['y']})"
                )
    if not snapshot["triggers"]:
        raise ValueError("Probe has no mechanic logic")
    return snapshot


def reload_probe(directory: Path, record: ProbeRecord) -> ScenarioSnapshot:
    snapshot = inspect_probe(project_path(directory, record["scenario"]))
    if content_digest(snapshot) != record["normalized_sha256"]:
        raise ValueError(f"Probe normalized content differs after reload: {record['id']}")
    expected = json.loads(project_path(directory, record["snapshot"]).read_text(encoding="utf-8"))
    if snapshot != expected:
        raise ValueError(f"Probe reload differs from its inspection sidecar: {record['id']}")
    return snapshot
