import contextlib
import io
import os
import shutil

import pytest
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.probes.xs import check_xs


def make_scenario():
    with contextlib.redirect_stdout(io.StringIO()):
        return AoE2DEScenario.from_default("1.59")


def test_xs_errors_fail_validation():
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string="void broken() { unknownFunction(); }")
    with pytest.raises(Exception, match="Xs-Check failed validation"):
        check_xs(scenario)


@pytest.mark.skipif(os.name != "posix", reason="Executable permissions are a POSIX concern")
def test_xs_checker_handles_a_bundled_binary_without_execute_permission(tmp_path):
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string='void valid() { xsChatData("ok"); }')
    binary = tmp_path / "xs-check"
    shutil.copyfile(scenario.xs_manager.xs_check.path, binary)
    binary.chmod(0o700)
    scenario.xs_manager.xs_check.path = binary
    binary.chmod(0o600)
    check_xs(scenario)
    assert binary.stat().st_mode & 0o111 == 0
