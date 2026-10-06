"""Fields every build manifest records, and the schema check that guards them."""

import platform
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Literal, TypedDict

from ancienttdde.common.data import HashRecord, hashes, read_object, text_field

SCHEMA_VERSION = 2

type ManifestKind = Literal["stock-de-map", "ancient-td-game", "mechanics-probes", "legacy-audit"]

REBUILD_COMMANDS: dict[ManifestKind, str] = {
    "stock-de-map": "ancienttdde build --map-only",
    "ancient-td-game": "ancienttdde build",
    "mechanics-probes": "ancienttdde probe",
    "legacy-audit": "ancienttdde audit",
}


class Versions(TypedDict):
    tool_version: str
    parser_version: str
    python_version: str


TOOLS: dict[str, str] = {
    "tool_version": "ancienttdde",
    "parser_version": "AoE2ScenarioParser",
    "python_version": "Python",
}


class ManifestBase(Versions):
    """Each pipeline adds its own `kind` literal and extra fields."""

    schema_version: int
    inputs: list[HashRecord]
    artifacts: list[HashRecord]


class AuditManifest(ManifestBase):
    kind: Literal["legacy-audit"]
    summary: dict[str, object]


def versions() -> Versions:
    """Identify the tools that produced a build instead of hashing project configuration."""
    return Versions(
        tool_version=version("ancienttdde"),
        parser_version=version("AoE2ScenarioParser"),
        python_version=platform.python_version(),
    )


def rebuild_command(kind: ManifestKind, directory: Path, options: Sequence[str] = ()) -> str:
    """Name the command that rebuilds a build directory in place."""
    return " ".join([REBUILD_COMMANDS[kind], "--output", str(directory), *options])


def require_current_versions(manifest: Versions, *, kind: ManifestKind, rebuild: str) -> None:
    """Reject a build that other tools made, since they may write different output."""
    current = versions()
    for field, tool in TOOLS.items():
        recorded, installed = manifest.get(field), current.get(field)
        if recorded != installed:
            raise ValueError(
                f"{kind} was built with {tool} {recorded}, but this environment has "
                f"{installed}; rebuild with {rebuild}"
            )


def manifest_kind(raw: dict[str, object]) -> str | None:
    """Return the pipeline kind a manifest declares, whatever its schema."""
    kind = raw.get("kind")
    if isinstance(kind, str):
        return kind
    # Schema-1 audit manifests predate the kind field.
    if raw.get("schema_version") == 1 and "summary" in raw:
        return "legacy-audit"
    return None


def parse_manifest(raw: dict[str, object], *, kind: ManifestKind, rebuild: str) -> ManifestBase:
    """Check the fields every pipeline shares; `rebuild` names the command for older schemas."""
    if manifest_kind(raw) != kind:
        raise ValueError(f"Not a {kind} manifest")
    schema = raw.get("schema_version")
    if type(schema) is not int or schema != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported {kind} manifest schema {schema}; expected {SCHEMA_VERSION}, "
            f"rebuild with {rebuild}"
        )
    return ManifestBase(
        schema_version=SCHEMA_VERSION,
        tool_version=text_field(raw, "tool_version"),
        parser_version=text_field(raw, "parser_version"),
        python_version=text_field(raw, "python_version"),
        inputs=hashes(raw.get("inputs"), "inputs"),
        artifacts=hashes(raw.get("artifacts"), "artifacts"),
    )


def read_kind(path: Path) -> str | None:
    """Return the pipeline kind a manifest file declares, whatever its schema."""
    return manifest_kind(read_object(path))
