"""Byte-level provenance for immutable legacy inputs and generated references."""

import hashlib
from pathlib import Path


def hash_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def project_path(root: Path, relative: str) -> Path:
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f"Path is outside the project: {relative}")
    return result


def verify_provenance(root: Path, manifest: dict) -> None:
    for record in manifest["files"]:
        path = project_path(root, record["path"])
        if not path.is_file():
            raise ValueError(f"Missing provenance input: {record['path']}")
        if hash_file(path) != record["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {record['path']}")
