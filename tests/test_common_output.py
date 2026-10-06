import json
from pathlib import Path

import pytest

from ancienttdde.common.output import prepare_output, project_path, publish

KIND = "ancient-td-game"
NAMES = ("scenario.aoe2scenario", "scenario.json")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for name in ("content", "src", "docs", "legacy"):
        (root / name).mkdir(parents=True)
    return root


def prepare(root: Path, output: Path | None) -> Path:
    return prepare_output(root, output, ".build/game", NAMES, kind=KIND)


def test_the_default_output_is_inside_the_project(project: Path) -> None:
    assert prepare(project, None) == (project / ".build/game").resolve()


@pytest.mark.parametrize(
    "destination", ["content/out", "src/probes", "docs", "legacy", "typings/x", ".", ".."]
)
def test_output_cannot_overwrite_sources_the_project_or_its_ancestors(
    project: Path, destination: str
) -> None:
    with pytest.raises(ValueError, match="outside source"):
        prepare(project, project / destination)


@pytest.mark.parametrize("default", ["../reports", "/tmp/reports", ".build/../../reports"])
def test_a_default_output_cannot_leave_the_project(project: Path, default: str) -> None:
    with pytest.raises(ValueError, match="inside the project"):
        prepare_output(project, None, default, NAMES, kind=KIND)


def test_the_default_output_may_live_on_another_disk(project: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (project / ".build").symlink_to(elsewhere, target_is_directory=True)
    assert prepare(project, None) == (elsewhere / "game").resolve()


def test_output_rejects_source_directories_reached_through_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    shared = tmp_path / "shared-docs"
    shared.mkdir()
    (root / "docs").symlink_to(shared, target_is_directory=True)
    with pytest.raises(ValueError, match="outside source"):
        prepare(root, root / "docs")


def test_output_must_be_a_directory(project: Path, tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("")
    with pytest.raises(ValueError, match="directory"):
        prepare(project, path)


def test_output_does_not_replace_artifact_symlinks(project: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "scenario.json").symlink_to(tmp_path / "elsewhere.json")
    with pytest.raises(ValueError, match="symlink"):
        prepare(project, output)


@pytest.mark.parametrize("content", ['{"kind": "stock-de-map"}', "{}"])
def test_output_does_not_take_over_another_manifest(
    project: Path, tmp_path: Path, content: str
) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "manifest.json").write_text(content)
    with pytest.raises(ValueError, match="unrelated manifest"):
        prepare(project, output)


def test_output_does_not_overwrite_unrelated_artifacts(project: Path, tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "scenario.json").write_text("{}")
    with pytest.raises(ValueError, match="unrelated artifacts"):
        prepare(project, output)


def test_an_output_of_the_same_kind_is_reused_whatever_its_schema(
    project: Path, tmp_path: Path
) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "kind": KIND, "inputs": ["from an older build"]})
    )
    (output / "scenario.json").write_text("{}")
    assert prepare(project, output) == output.resolve()


def test_publishing_moves_artifacts_and_writes_the_manifest_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    for name in (*NAMES, "manifest.json"):
        (staging / name).write_text(name)
    moved: list[str] = []
    replace = Path.replace

    def record(self: Path, target: Path) -> Path:
        moved.append(self.name)
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", record)
    publish(staging, tmp_path / "out", NAMES)
    assert moved == [*NAMES, "manifest.json"]
    published = {path.name: path.read_text() for path in (tmp_path / "out").iterdir()}
    assert published == {name: name for name in (*NAMES, "manifest.json")}


def test_project_paths_cannot_leave_their_base(tmp_path: Path) -> None:
    assert project_path(tmp_path, "a/b.json") == (tmp_path / "a/b.json").resolve()
    with pytest.raises(ValueError, match="outside"):
        project_path(tmp_path, "../elsewhere")
