"""Validate JSON structure as it enters the typed probe interfaces."""

import json
import re
from pathlib import Path
from typing import cast

from ancienttdde.generation.models import HashRecord


def object_value(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def read_object(path: Path) -> dict[str, object]:
    return object_value(json.loads(path.read_text(encoding="utf-8")), path.name)


def rows(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [object_value(row, label) for row in cast(list[object], value)]


def text_field(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid SHA-256 digest")
    return value


def hashes(value: object, label: str) -> list[HashRecord]:
    records = [
        HashRecord(path=text_field(row, "path"), sha256=digest(row.get("sha256")))
        for row in rows(value, label)
    ]
    if len({r["path"] for r in records}) != len(records):
        raise ValueError(f"Duplicate {label} paths")
    return records
