"""SHA-256 records for inputs, artifacts and canonical JSON content."""

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from ancienttdde.common.data import HashRecord
from ancienttdde.common.layers import ASSETS, reachable
from ancienttdde.common.output import project_path

# The installed package: the code a build runs, whatever project root it reads content from.
PACKAGE = Path(__file__).resolve().parents[1]


def hash_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def hash_json(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def hash_records(base: Path, paths: Iterable[str]) -> list[HashRecord]:
    return [HashRecord(path=path, sha256=hash_file(project_path(base, path))) for path in paths]


def verify_hashes(base: Path, records: Iterable[HashRecord], label: str) -> None:
    for record in records:
        path = project_path(base, record["path"])
        if not path.is_file():
            raise ValueError(f"Missing {label}: {record['path']}")
        if hash_file(path) != record["sha256"]:
            raise ValueError(f"{label.capitalize()} SHA-256 mismatch: {record['path']}")


def verify_inputs(recorded: list[HashRecord], current: list[HashRecord], label: str) -> None:
    """Require a manifest's inputs to match the current content and package files."""
    expected = {record["path"]: record["sha256"] for record in current}
    if len(recorded) != len(expected) or {r["path"] for r in recorded} != expected.keys():
        raise ValueError(f"{label.capitalize()} manifest must record every current input")
    for record in recorded:
        if expected[record["path"]] != record["sha256"]:
            raise ValueError(f"{label.capitalize()} input SHA-256 mismatch: {record['path']}")


def package_inputs(layer: str) -> list[HashRecord]:
    """Hash the package code a layer can run and the assets that code reads.

    Paths start with the package's own name, `ancienttdde/`, wherever it is installed;
    project content paths are relative to the project root instead.
    """
    files = {PACKAGE / "__init__.py"}
    for name in reachable(layer):
        directory = PACKAGE / name
        files.update(directory.rglob("*.py") if directory.is_dir() else [PACKAGE / f"{name}.py"])
        files.update(PACKAGE / "assets" / asset for asset in ASSETS.get(name, ()))
    relative = sorted(path.relative_to(PACKAGE.parent).as_posix() for path in files)
    return hash_records(PACKAGE.parent, relative)


def hash_inputs(root: Path, content: Iterable[str], label: str, *, layer: str) -> list[HashRecord]:
    """Hash a pipeline's project content, then the package code and assets it runs."""
    paths = list(content)
    for relative in paths:
        if not project_path(root, relative).is_file():
            raise ValueError(f"Missing {label} input: {relative}")
    return hash_records(root, paths) + package_inputs(layer)
