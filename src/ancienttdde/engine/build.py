"""Build and independently reconstruct self-contained playable game artifacts."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, TypedDict, cast

from ancienttdde.engine.config import load_balance
from ancienttdde.engine.scenario import instructions
from ancienttdde.generation.build import INPUTS as MAP_INPUTS
from ancienttdde.generation.build import content_inputs, write_json
from ancienttdde.generation.foundation import migrate_map, validate_map
from ancienttdde.generation.models import HashRecord
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.probes.build import probe_digest
from ancienttdde.probes.models import ProbeSnapshot
from ancienttdde.probes.serialization import digest, hashes, read_object
from ancienttdde.provenance import hash_file, project_path
from ancienttdde.validation import validate_references

SCENARIO_NAME = "ancient-td-de.aoe2scenario"
ARTIFACTS = (SCENARIO_NAME, "map.json", "scenario.json", "instructions.md", "validation.json")
INPUTS = MAP_INPUTS + (
    "content/balance/game.json",
    "pyproject.toml",
    "src/ancienttdde/ai/passive.per",
    "src/ancienttdde/engine/config.py",
    "src/ancienttdde/engine/script.py",
    "src/ancienttdde/engine/runtime.xs",
    "src/ancienttdde/engine/scenario.py",
    "src/ancienttdde/engine/build.py",
    "src/ancienttdde/registry.py",
    "src/ancienttdde/probes/native.py",
    "src/ancienttdde/probes/xs.py",
    "src/ancienttdde/probes/build.py",
    "src/ancienttdde/probes/serialization.py",
    "src/ancienttdde/generation/scenario.py",
    "src/ancienttdde/generation/foundation.py",
    "src/ancienttdde/generation/geometry.py",
    "src/ancienttdde/generation/build.py",
    "src/ancienttdde/inspection/scenario.py",
)


class GameManifest(TypedDict):
    schema_version: int
    kind: Literal["ancient-td-game"]
    inputs: list[HashRecord]
    artifacts: list[HashRecord]
    normalized_sha256: str
    xs_checked: Literal[True]
    in_game_verified: Literal[False]


def read_manifest(path: Path) -> GameManifest:
    raw = read_object(path)
    if (
        type(raw.get("schema_version")) is not int
        or raw["schema_version"] != 1
        or raw.get("kind") != "ancient-td-game"
        or raw.get("xs_checked") is not True
        or raw.get("in_game_verified") is not False
    ):
        raise ValueError("Unsupported game manifest")
    inputs, artifacts = (
        hashes(raw.get("inputs"), "inputs"),
        hashes(raw.get("artifacts"), "artifacts"),
    )
    if {r["path"] for r in inputs} != set(INPUTS):
        raise ValueError("Game manifest must record every current input")
    if {r["path"] for r in artifacts} != set(ARTIFACTS):
        raise ValueError("Game manifest must record every artifact")
    return GameManifest(
        schema_version=1,
        kind="ancient-td-game",
        inputs=inputs,
        artifacts=artifacts,
        normalized_sha256=digest(raw.get("normalized_sha256")),
        xs_checked=True,
        in_game_verified=False,
    )


def output_directory(root: Path, output: Path | None) -> Path:
    directory = (output or root / ".build/game").resolve()
    protected = (
        "content",
        "legacy",
        "src",
        "tests",
        "tools",
        "docs",
        ".git",
        ".agents",
        ".codex",
        ".venv",
    )
    if root.is_relative_to(directory) or any(
        directory.is_relative_to((root / p).resolve()) for p in protected
    ):
        raise ValueError("Game output cannot overwrite source directories or their ancestors")
    if directory.exists() and not directory.is_dir():
        raise ValueError("Game output must be a directory")
    names = (*ARTIFACTS, "manifest.json")
    if any((directory / name).is_symlink() for name in names):
        raise ValueError("Game output cannot replace artifact symlinks")
    if (directory / "manifest.json").exists():
        read_manifest(directory / "manifest.json")
    elif any((directory / name).exists() for name in names):
        raise ValueError("Game output cannot overwrite unrelated artifacts")
    return directory


def worker(root: Path, data: Path, path: Path, *, check_only: bool = False) -> None:
    arguments = ["--check-xs", str(path)] if check_only else [str(root), str(data), str(path)]
    result = subprocess.run(
        [sys.executable, "-m", "ancienttdde.engine.scenario", *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"Game generation/XS validation failed: {result.stderr.strip()}")


def inspect_game(path: Path) -> ProbeSnapshot:
    raw = inspect_scenario(path, include_terrain=True, include_game_settings=True)
    if findings := validate_references(raw):
        raise ValueError(f"Game contains dangling references: {findings}")
    snapshot = cast(ProbeSnapshot, raw)
    if (
        snapshot["scenario_version"] != "1.59"
        or snapshot["map"]["width"] != 200
        or snapshot["map"]["height"] != 200
    ):
        raise ValueError("Game must use the migrated 200x200 map in format 1.59")
    if (
        snapshot["victory_condition"] != 4
        or snapshot["options"]["victory_custom_conditions_required"]
        or any(snapshot["global_victory"].values())
    ):
        raise ValueError("Game must disable automatic victory conditions")
    dependency = snapshot["dependencies"]
    if (
        dependency["external_xs"]
        or dependency["ai_files"]
        or any(dependency["cinematics"])
        or dependency["background_image"]
    ):
        raise ValueError("Game must have no external gameplay dependencies")
    ids = [u["reference_id"] for u in snapshot["units"]]
    if len(ids) != len(set(ids)) or snapshot["next_unit_id"] <= max(ids, default=-1):
        raise ValueError("Game placement IDs or allocator are invalid")
    if not snapshot["triggers"] or not snapshot["variables"]:
        raise ValueError("Game is missing its engine")
    return snapshot


def build_game(root: Path, output: Path | None = None) -> GameManifest:
    root = root.resolve()
    directory = output_directory(root, output)
    legacy, config, _ = content_inputs(root)
    data = migrate_map(legacy, config)
    report = validate_map(data, config)
    balance = load_balance(root / "content/balance/game.json")
    for relative in INPUTS:
        if not project_path(root, relative).is_file():
            raise ValueError(f"Missing game input: {relative}")
    inputs = [HashRecord(path=p, sha256=hash_file(root / p)) for p in INPUTS]
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ancienttdde-game-", dir=directory.parent) as temporary:
        staging = Path(temporary)
        write_json(staging / "map.json", data)
        write_json(staging / "validation.json", report)
        worker(root, staging / "map.json", staging / SCENARIO_NAME)
        snapshot = inspect_game(staging / SCENARIO_NAME)
        write_json(staging / "scenario.json", snapshot)
        (staging / "instructions.md").write_text(instructions(balance), encoding="utf-8")
        manifest = GameManifest(
            schema_version=1,
            kind="ancient-td-game",
            inputs=inputs,
            artifacts=[HashRecord(path=p, sha256=hash_file(staging / p)) for p in ARTIFACTS],
            normalized_sha256=probe_digest(snapshot),
            xs_checked=True,
            in_game_verified=False,
        )
        write_json(staging / "manifest.json", manifest)
        directory.mkdir(parents=True, exist_ok=True)
        for name in (*ARTIFACTS, "manifest.json"):
            (staging / name).replace(directory / name)
    return manifest


def validate_game(directory: Path, root: Path) -> GameManifest:
    root, directory = root.resolve(), directory.resolve()
    manifest = read_manifest(project_path(directory, "manifest.json"))
    for key, base in (("inputs", root), ("artifacts", directory)):
        records = manifest["inputs"] if key == "inputs" else manifest["artifacts"]
        for record in records:
            if hash_file(project_path(base, record["path"])) != record["sha256"]:
                raise ValueError(f"Game {key} SHA-256 mismatch: {record['path']}")
    snapshot = inspect_game(directory / SCENARIO_NAME)
    if probe_digest(snapshot) != manifest["normalized_sha256"]:
        raise ValueError("Game normalized content differs after reload")
    if snapshot != json.loads((directory / "scenario.json").read_text(encoding="utf-8")):
        raise ValueError("Game reload differs from the inspection sidecar")
    worker(root, directory / "map.json", directory / SCENARIO_NAME, check_only=True)
    with TemporaryDirectory(prefix="ancienttdde-game-validation-") as temporary:
        expected = build_game(root, Path(temporary))
        if expected["normalized_sha256"] != manifest["normalized_sha256"]:
            raise ValueError("Game logic differs from current definitions")
        for name in ("map.json", "validation.json", "instructions.md"):
            if (directory / name).read_bytes() != (Path(temporary) / name).read_bytes():
                raise ValueError(f"Game sidecar differs from current definitions: {name}")
    return manifest
