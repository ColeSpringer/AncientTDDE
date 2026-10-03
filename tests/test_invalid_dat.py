import pytest

from ancienttdde.inspection.dat import read_json


def test_corrupted_dat_reference_names_the_input_and_requires_regeneration(tmp_path):
    source = tmp_path / "corrupted.json"
    source.write_bytes(b'{"Missile": {"ProjectileType": 0,\xf9\xe8\x84garbage}}')
    with pytest.raises(ValueError, match="corrupted.json.*regenerate"):
        read_json(source)
