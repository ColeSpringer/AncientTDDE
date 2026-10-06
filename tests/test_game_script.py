"""Execute the generated XS with a small implementation of DE's query API."""

import re
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT, compile_harness

from ancienttdde.common.data import object_value, read_object


@pytest.fixture(scope="module")
def engine_runner(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from ancienttdde.game.config import load_balance, load_lanes
    from ancienttdde.game.script import render_xs

    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = read_object(ROOT / "content/maps/foundation.json")["anchors"]
    script = render_xs(balance, load_lanes(object_value(anchors, "anchors")))
    # XS counted loops implicitly declare/increment their integer counter.
    script = re.sub(
        r"for \((\w+) = ([^;]+); ([<]=?) (.+)\) \{",
        r"for (int \1 = \2; \1 \3 \4; ++\1) {",
        script,
    )
    return compile_harness(
        tmp_path_factory.mktemp("engine-xs"), "engine_xs_harness.cpp", {"// EMBEDDED_XS": script}
    )


@pytest.mark.parametrize(
    "case",
    [
        "berry_mills",
        "slots",
        "ai_departures",
        "no_humans",
        "initialize",
        "solo",
        "defeat",
        "simultaneous",
        "survivor",
        "sudden",
        "resume",
        "cap",
        "resign",
        "leaks",
        "exit_arrival",
        "first_wave",
    ],
)
def test_shared_engine(engine_runner: Path, case: str) -> None:
    result = subprocess.run([str(engine_runner), case], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
