import json
from pathlib import Path
from typing import Literal

import pytest

from ancienttdde.common.manifest import (
    ManifestKind,
    parse_manifest,
    read_kind,
    rebuild_command,
    require_current_versions,
    versions,
)

BUILD = Path("/builds/suite")


def manifest(kind: str, schema: int = 2) -> dict[str, object]:
    return {
        "schema_version": schema,
        "kind": kind,
        **versions(),
        "inputs": [{"path": "content/maps/foundation.json", "sha256": "0" * 64}],
        "artifacts": [{"path": "map.json", "sha256": "1" * 64}],
    }


def test_manifests_parse_the_fields_every_pipeline_shares() -> None:
    raw = manifest("ancient-td-game")
    rebuild = rebuild_command("ancient-td-game", BUILD)
    assert parse_manifest(raw, kind="ancient-td-game", rebuild=rebuild) == {
        key: value for key, value in raw.items() if key != "kind"
    }


@pytest.mark.parametrize(
    ("kind", "command"),
    [
        ("stock-de-map", "ancienttdde build --map-only"),
        ("ancient-td-game", "ancienttdde build"),
        ("mechanics-probes", "ancienttdde probe"),
        ("legacy-audit", "ancienttdde audit"),
    ],
)
def test_older_manifest_schemas_name_the_command_that_rebuilds_them(
    kind: ManifestKind, command: str
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            f"^Unsupported {kind} manifest schema 1; expected 2, "
            f"rebuild with {command} --output /builds/suite$"
        ),
    ):
        parse_manifest(manifest(kind, schema=1), kind=kind, rebuild=rebuild_command(kind, BUILD))


def test_a_rebuild_command_keeps_the_options_that_made_the_build() -> None:
    command = rebuild_command("mechanics-probes", BUILD, ["--only payments"])
    assert command == "ancienttdde probe --output /builds/suite --only payments"


@pytest.mark.parametrize(
    ("field", "tool"),
    [
        ("tool_version", "ancienttdde"),
        ("parser_version", "AoE2ScenarioParser"),
        ("python_version", "Python"),
    ],
)
def test_a_build_made_with_other_tools_must_be_rebuilt(
    field: Literal["tool_version", "parser_version", "python_version"], tool: str
) -> None:
    rebuild = rebuild_command("stock-de-map", BUILD)
    built = parse_manifest(manifest("stock-de-map"), kind="stock-de-map", rebuild=rebuild)
    require_current_versions(built, kind="stock-de-map", rebuild=rebuild)
    current = built[field]
    built[field] = "0.0.1"
    with pytest.raises(
        ValueError,
        match=(
            f"^stock-de-map was built with {tool} 0.0.1, but this environment has {current}; "
            f"rebuild with ancienttdde build --map-only --output /builds/suite$"
        ),
    ):
        require_current_versions(built, kind="stock-de-map", rebuild=rebuild)


def test_manifests_of_another_kind_are_rejected() -> None:
    with pytest.raises(ValueError, match="stock-de-map"):
        parse_manifest(
            manifest("ancient-td-game"),
            kind="stock-de-map",
            rebuild=rebuild_command("stock-de-map", BUILD),
        )


def test_manifest_versions_identify_the_tools_that_built_them() -> None:
    current = versions()
    assert set(current) == {"tool_version", "parser_version", "python_version"}
    assert current["parser_version"] == "0.9.4"
    assert all(current.values())


def test_the_kind_names_the_pipeline_that_owns_a_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "kind": "mechanics-probes"}))
    assert read_kind(path) == "mechanics-probes"
    path.write_text("{}")
    assert read_kind(path) is None
    path.write_text(json.dumps({"schema_version": 1, "summary": {}, "inputs": [], "artifacts": []}))
    assert read_kind(path) == "legacy-audit"


def test_older_audit_manifests_without_a_kind_name_the_rebuild_command() -> None:
    raw = manifest("legacy-audit", schema=1)
    del raw["kind"]
    raw["summary"] = {}
    expected = (
        "Unsupported legacy-audit manifest schema 1; expected 2, "
        "rebuild with ancienttdde audit --output /builds/suite"
    )
    with pytest.raises(ValueError, match=f"^{expected}$"):
        parse_manifest(raw, kind="legacy-audit", rebuild=rebuild_command("legacy-audit", BUILD))
