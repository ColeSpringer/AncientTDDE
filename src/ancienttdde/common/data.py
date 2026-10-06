"""Validate JSON structure as it enters typed interfaces, and read packaged assets."""

import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class HashRecord(TypedDict):
    path: str
    sha256: str
    size_bytes: NotRequired[int]


def object_value(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def read_object(path: Path) -> dict[str, object]:
    return object_value(json.loads(path.read_text(encoding="utf-8")), path.name)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Invalid JSON reference {path}; regenerate it from the original DAT"
        ) from error


def write_json(path: Path, data: object, *, compact: bool = False) -> None:
    """Write sorted, indented JSON; compact output keeps key order on one line."""
    if compact:
        path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        return
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def rows(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [object_value(row, label) for row in cast(list[object], value)]


def text_field(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value


def integer(row: dict[str, object], key: str, low: int, high: int) -> int:
    value = row.get(key)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer between {low} and {high}")
    return value


def digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid SHA-256 digest")
    return value


def hashes(value: object, label: str) -> list[HashRecord]:
    records: list[HashRecord] = []
    for row in rows(value, label):
        record = HashRecord(path=text_field(row, "path"), sha256=digest(row.get("sha256")))
        if "size_bytes" in row:
            record["size_bytes"] = integer(row, "size_bytes", 0, 2**63 - 1)
        records.append(record)
    if len({r["path"] for r in records}) != len(records):
        raise ValueError(f"Duplicate paths in {label}")
    return records


def asset_text(name: str) -> str:
    """Read a script or AI file shipped in the package's assets directory."""
    return (files("ancienttdde") / "assets" / name).read_text(encoding="utf-8")
