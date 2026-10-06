"""Fail-closed checks using the parser's bundled XS linter."""

import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


@contextmanager
def xs_checker(scenario: AoE2DEScenario) -> Generator[None]:
    checker = scenario.xs_manager.xs_check
    if checker.is_disabled:
        raise ValueError("The parser's xs-check must be enabled to check XS")
    checker.raise_on_error = True
    original = checker.path
    if original is None or not original.is_file():
        raise ValueError("The parser's bundled xs-check binary is missing")
    with TemporaryDirectory(prefix="ancienttdde-xs-") as temporary:
        # Some wheels lose the executable bit. Run a private copy without modifying the package.
        if os.name == "posix" and not os.access(original, os.X_OK):
            executable = Path(temporary) / "xs-check"
            shutil.copyfile(original, executable)
            executable.chmod(0o700)
            checker.path = executable
        try:
            yield
        finally:
            # Setting a non-executable path would invoke it in the parser's version check.
            checker.path = original if os.access(original, os.X_OK) else None


def check_xs(scenario: AoE2DEScenario) -> None:
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
