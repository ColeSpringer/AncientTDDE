import os
import re
import shutil
from pathlib import Path

import pytest
from conftest import new_scenario

from ancienttdde.common.data import asset_text
from ancienttdde.common.layers import ASSETS
from ancienttdde.scenario.xs import check_xs

# DE's XS does not promote an int argument to float, and the parser's XS check does not
# report it, so packaged scripts write a float literal wherever XS expects a float.
INT_FOR_FLOAT = re.compile(r"\bfloat\s+\w+\s*=\s*-?\d+(?![\d.])")
VECTOR_SET = re.compile(r"xsVectorSet\(([^()]*)\)")
SCRIPTS = sorted(name for names in ASSETS.values() for name in names if name.endswith(".xs"))


def make_scenario():
    return new_scenario("1.59")


def test_xs_errors_fail_validation() -> None:
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string="void broken() { unknownFunction(); }")
    with pytest.raises(Exception, match="Xs-Check failed validation"):
        check_xs(scenario)


def test_xs_validation_needs_the_parser_xs_check() -> None:
    scenario = make_scenario()
    scenario.xs_manager.xs_check.enabled = False
    with pytest.raises(ValueError, match="^The parser's xs-check must be enabled to check XS$"):
        check_xs(scenario)


@pytest.mark.skipif(os.name != "posix", reason="Executable permissions are a POSIX concern")
def test_xs_checker_handles_a_bundled_binary_without_execute_permission(tmp_path: Path) -> None:
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string='void valid() { xsChatData("ok"); }')
    binary = tmp_path / "xs-check"
    bundled = scenario.xs_manager.xs_check.path
    assert bundled is not None
    shutil.copyfile(bundled, binary)
    binary.chmod(0o700)
    scenario.xs_manager.xs_check.path = binary
    binary.chmod(0o600)
    check_xs(scenario)
    assert binary.stat().st_mode & 0o111 == 0


@pytest.mark.parametrize("name", SCRIPTS)
def test_packaged_scripts_write_floats_where_xs_expects_them(name: str) -> None:
    text = asset_text(name)
    assert INT_FOR_FLOAT.findall(text) == []
    components = [part for found in VECTOR_SET.findall(text) for part in found.split(",")]
    assert [part for part in components if re.fullmatch(r"\s*-?\d+\s*", part)] == []
