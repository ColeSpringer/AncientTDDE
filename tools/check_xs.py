"""Validate embedded-source files with AoE2ScenarioParser's bundled xs-check."""

import contextlib
import os
from pathlib import Path

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.probes.xs import check_xs


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "src/ancienttdde/xs").rglob("*.xs"))
    if not files:
        print("XS check: no gameplay scripts to validate.")
        return
    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        scenario = AoE2DEScenario.from_default()
    check_xs(scenario, files)
    print(f"XS check: {len(files)} files validated.")


if __name__ == "__main__":
    main()
