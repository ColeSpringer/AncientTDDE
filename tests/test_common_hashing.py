import hashlib
from pathlib import Path

import pytest

import ancienttdde
from ancienttdde.common.data import HashRecord
from ancienttdde.common.hashing import (
    hash_file,
    hash_inputs,
    hash_json,
    hash_records,
    package_inputs,
    verify_hashes,
    verify_inputs,
)


def test_changed_and_missing_files_fail_verification(tmp_path: Path) -> None:
    source = tmp_path / "original.dat"
    source.write_bytes(b"original")
    records = hash_records(tmp_path, ["original.dat"])
    assert records == [{"path": "original.dat", "sha256": hash_file(source)}]
    verify_hashes(tmp_path, records, "provenance input")
    source.write_bytes(b"modified")
    with pytest.raises(ValueError, match="Provenance input SHA-256 mismatch: original.dat"):
        verify_hashes(tmp_path, records, "provenance input")
    source.unlink()
    with pytest.raises(ValueError, match="Missing provenance input: original.dat"):
        verify_hashes(tmp_path, records, "provenance input")


def test_recorded_paths_cannot_leave_their_base(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        verify_hashes(tmp_path, [{"path": "../elsewhere", "sha256": "0" * 64}], "input")
    with pytest.raises(ValueError, match="outside"):
        hash_records(tmp_path, ["../elsewhere"])


def test_json_hashes_use_the_canonical_serialization() -> None:
    assert hash_json({"b": [1, 2], "a": "é"}) == hash_json({"a": "é", "b": [1, 2]})
    expected = hashlib.sha256('{"a": "é", "b": [1, 2]}'.encode()).hexdigest()
    assert hash_json({"b": [1, 2], "a": "é"}) == expected


def test_package_inputs_hash_the_code_and_assets_a_layer_can_reach() -> None:
    records = package_inputs("game")
    paths = [record["path"] for record in records]
    assert paths == sorted(paths)
    assert {
        "ancienttdde/__init__.py",
        "ancienttdde/models.py",
        "ancienttdde/common/data.py",
        "ancienttdde/map/build.py",
        "ancienttdde/game/build.py",
        "ancienttdde/assets/runtime.xs",
        "ancienttdde/assets/passive.per",
    } <= set(paths)
    # Probe code and scripts never run in a game build, so editing them cannot invalidate one.
    assert not any(path.startswith(("ancienttdde/probes/", "ancienttdde/audit/")) for path in paths)
    assert "ancienttdde/assets/probe-raider-purchases.xs" not in paths
    assert "ancienttdde/cli.py" not in paths
    base = Path(ancienttdde.__file__).parent.parent
    assert all(record["sha256"] == hash_file(base / record["path"]) for record in records)


def test_probe_inputs_leave_out_the_game_script() -> None:
    paths = {record["path"] for record in package_inputs("probes")}
    assert "ancienttdde/assets/probe-raider-purchases.xs" in paths
    assert "ancienttdde/assets/runtime.xs" not in paths
    assert not any(path.startswith("ancienttdde/game/") for path in paths)


def test_package_inputs_reject_unknown_layers() -> None:
    with pytest.raises(ValueError, match="Unknown package layer: missing"):
        package_inputs("missing")


def test_pipeline_inputs_need_their_content_and_add_the_package(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Missing map input: content/a.json"):
        hash_inputs(tmp_path, ["content/a.json"], "map", layer="map")
    content = tmp_path / "content/a.json"
    content.parent.mkdir()
    content.write_text("{}")
    records = hash_inputs(tmp_path, ["content/a.json"], "map", layer="map")
    assert records[0] == {"path": "content/a.json", "sha256": hash_file(content)}
    assert records[1:] == package_inputs("map")


def test_recorded_inputs_must_match_the_current_inputs_exactly() -> None:
    current: list[HashRecord] = [
        {"path": "content/a.json", "sha256": "0" * 64},
        {"path": "ancienttdde/models.py", "sha256": "1" * 64},
    ]
    verify_inputs(list(current), current, "map")
    changed: HashRecord = {"path": "ancienttdde/models.py", "sha256": "2" * 64}
    with pytest.raises(ValueError, match="Map input SHA-256 mismatch: ancienttdde/models.py"):
        verify_inputs([current[0], changed], current, "map")
    with pytest.raises(ValueError, match="Map manifest must record every current input"):
        verify_inputs(current[:1], current, "map")
    with pytest.raises(ValueError, match="Map manifest must record every current input"):
        verify_inputs([*current, current[0]], current, "map")
