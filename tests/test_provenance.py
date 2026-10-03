import pytest

from ancienttdde.provenance import hash_file, verify_provenance


def test_changed_and_missing_sources_fail_verification(tmp_path):
    source = tmp_path / "original.dat"
    source.write_bytes(b"original")
    manifest = {"files": [{"path": "original.dat", "sha256": hash_file(source)}]}
    verify_provenance(tmp_path, manifest)
    source.write_bytes(b"modified")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_provenance(tmp_path, manifest)
    source.unlink()
    with pytest.raises(ValueError, match="Missing"):
        verify_provenance(tmp_path, manifest)


def test_provenance_cannot_reference_files_outside_project(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        verify_provenance(tmp_path, {"files": [{"path": "../elsewhere", "sha256": "0"}]})
