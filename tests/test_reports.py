from ancienttdde.reports import table


def test_report_tables_keep_literal_trigger_labels_and_control_characters_readable():
    result = table(["Trigger", "Name"], [[0, "left|right\rnext\x00"]])
    assert "| 0 | left\\|right<br>next |" in result
    assert "\x00" not in result
