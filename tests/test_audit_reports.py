import pytest

from ancienttdde.audit.reports import enemy_name, table


def test_report_tables_keep_literal_trigger_labels_and_control_characters_readable() -> None:
    result = table(["Trigger", "Name"], [[0, "left|right\rnext\x00"]])
    assert "| 0 | left\\|right<br>next |" in result
    assert "\x00" not in result


def test_an_enemy_object_missing_from_the_dat_is_reported() -> None:
    with pytest.raises(ValueError, match="DAT has no object 434"):
        enemy_name({12: {"id": 12, "civilizations": {}}}, 1, 434)
