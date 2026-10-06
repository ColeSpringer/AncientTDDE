from pathlib import Path

import pytest

from ancienttdde.common.data import asset_text, hashes, integer, read_json, write_json


def test_corrupted_dat_reference_names_the_input_and_requires_regeneration(tmp_path: Path) -> None:
    source = tmp_path / "corrupted.json"
    source.write_bytes(b'{"Missile": {"ProjectileType": 0,\xf9\xe8\x84garbage}}')
    with pytest.raises(ValueError, match="corrupted.json.*regenerate"):
        read_json(source)


def test_json_artifacts_are_sorted_indented_and_end_with_a_newline(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write_json(path, {"b": 1, "a": ["é"]})
    assert path.read_text(encoding="utf-8") == '{\n  "a": [\n    "é"\n  ],\n  "b": 1\n}\n'


def test_compact_json_keeps_key_order_on_one_line(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write_json(path, {"b": 1, "a": "é"}, compact=True)
    assert path.read_text(encoding="utf-8") == '{"b": 1, "a": "é"}'


def test_json_artifacts_reject_non_finite_numbers(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_json(tmp_path / "data.json", {"a": float("nan")})


def test_assets_are_read_from_the_installed_package() -> None:
    assert "(disable-self)" in asset_text("passive.per")
    assert "void ancientPurchaseRaider(" in asset_text("probe-raider-purchases.xs")
    assert "rule ancientProbeHeartbeat" in asset_text("probe-heartbeat.xs")
    assert "void ancientInitialize()" in asset_text("runtime.xs")


@pytest.mark.parametrize("value", [True, 0, 6, 2.0, None, "3"])
def test_integers_reject_booleans_other_types_and_out_of_range_values(value: object) -> None:
    assert integer({"n": 3}, "n", 1, 5) == 3
    with pytest.raises(ValueError, match="n must be an integer between 1 and 5"):
        integer({"n": value}, "n", 1, 5)


def test_hash_records_keep_recorded_sizes_and_reject_duplicate_paths() -> None:
    rows = [{"path": "a.json", "sha256": "0" * 64, "size_bytes": 3}]
    assert hashes(rows, "artifacts") == rows
    with pytest.raises(ValueError, match="Duplicate paths in artifacts"):
        hashes(rows * 2, "artifacts")
    with pytest.raises(ValueError, match="SHA-256"):
        hashes([{"path": "a.json", "sha256": "not a digest"}], "artifacts")
