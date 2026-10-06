"""Execute the generated XS with a small implementation of DE's query API."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def engine_runner(tmp_path_factory):
    from ancienttdde.engine.config import load_balance, load_lanes
    from ancienttdde.engine.script import render_xs

    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("XS behavioral checks require a C++ compiler")
    output = tmp_path_factory.mktemp("engine-xs")
    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    script = render_xs(ROOT, balance, load_lanes(anchors))
    # XS counted loops implicitly declare/increment their integer counter.
    script = re.sub(
        r"for \((\w+) = ([^;]+); ([<]=?) (.+)\) \{",
        r"for (int \1 = \2; \1 \3 \4; ++\1) {",
        script,
    )
    harness = (ROOT / "tests/support/engine_xs_harness.cpp").read_text()
    source = output / "engine.cpp"
    source.write_text(harness.replace("// EMBEDDED_XS", script))
    exe = output / "engine"
    result = subprocess.run(
        [compiler, "-std=c++17", str(source), "-o", str(exe)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return exe


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
def test_shared_engine(engine_runner, case):
    result = subprocess.run([str(engine_runner), case], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
