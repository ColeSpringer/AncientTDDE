"""Validate embedded-source files with AoE2ScenarioParser's bundled xs-check."""

import contextlib
import os
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "src/ancienttdde/xs").rglob("*.xs"))
    if not files:
        print("XS check: no gameplay scripts to validate.")
        return
    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        scenario = AoE2DEScenario.from_default()
    checker = scenario.xs_manager.xs_check
    if checker.is_disabled:
        raise RuntimeError("xs-check must be enabled for source validation")
    for path in files:
        checker.validate(path)
    print(f"XS check: {len(files)} files validated.")


if __name__ == "__main__":
    main()
