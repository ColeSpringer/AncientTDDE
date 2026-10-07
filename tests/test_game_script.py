"""Execute the generated XS with a small implementation of DE's query API."""

import re
import subprocess
from pathlib import Path
from typing import cast

import pytest
from conftest import ROOT, compile_harness

from ancienttdde.common.data import object_value, read_object
from ancienttdde.game.catalog import Shop
from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.map.models import MapAnchor


def content() -> tuple[Balance, tuple[EngineLane, ...], Shop]:
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.config import load_balance, load_lanes

    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = object_value(read_object(ROOT / "content/maps/foundation.json")["anchors"], "anchors")
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(
        ROOT / "content/balance/shop.json", cast(dict[str, MapAnchor], anchors), families
    )
    return balance, load_lanes(anchors), shop


def prelude() -> str:
    from ancienttdde.game.script import render_prelude

    balance, lanes, shop = content()
    return render_prelude(balance, lanes, shop)


def harness_constants() -> str:
    """Purchase and tower technology names the harness cases use; the game needs none."""
    from ancienttdde.game.script import camel, tower_access

    balance, _, shop = content()
    lines = [f"const int cBuy{camel(p.key)} = {p.index};" for p in shop.purchases]
    lines += [
        f"const int c{name.replace(' ', '')}Tech = {tech};"
        for name, tech in tower_access(balance.towers)
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def engine_runner(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from ancienttdde.game.script import render_xs

    balance, lanes, shop = content()
    script = harness_constants() + render_xs(balance, lanes, shop)
    # XS counted loops implicitly declare/increment their integer counter.
    script = re.sub(
        r"for \((\w+) = ([^;]+); ([<]=?) (.+)\) \{",
        r"for (int \1 = \2; \1 \3 \4; ++\1) {",
        script,
    )
    return compile_harness(
        tmp_path_factory.mktemp("engine-xs"), "engine_xs_harness.cpp", {"// EMBEDDED_XS": script}
    )


def test_prelude_lists_tower_access_from_the_tower_families() -> None:
    from ancienttdde.game.config import Towers
    from ancienttdde.game.script import tower_access

    balance, _, _ = content()
    assert tower_access(balance.towers) == (
        ("Guard Tower", 140),
        ("Keep", 63),
        ("Bombard Tower", 64),
    )
    donjons = Towers((("donjons", ("WATCH_TOWER", "DONJON")),), "DONJON", 0, 0, 1)
    assert tower_access(donjons) == ()
    text = prelude()
    assert "const int cTowerKinds = 3;" in text
    assert 'if (index == 2) return ("Bombard Tower");' in text.split("string towerName")[1]


def test_prelude_passes_the_whole_relic_column() -> None:
    _, lanes, _ = content()
    text = prelude()
    x1, _, x2, _ = lanes[0].sites.relic_column
    assert f"if (index == 1) return ({x1});" in text.split("int laneRelicX1")[1]
    assert f"if (index == 1) return ({x2});" in text.split("int laneRelicX2")[1]


def test_prelude_counts_transfers_and_still_samples() -> None:
    from ancienttdde.game.script import STILL_SAMPLES
    from ancienttdde.game.sites import TRANSFERS

    text = prelude()
    assert f"const int cTransferCount = {len(TRANSFERS)};" in text
    assert f"const int cStillSamples = {STILL_SAMPLES};" in text and STILL_SAMPLES >= 2


def test_prelude_declares_message_codes_and_ownership_masks() -> None:
    from ancienttdde.game.messages import MESSAGES, message_code

    _, _, shop = content()
    text = prelude()
    for key, _ in MESSAGES:
        assert (
            f"const int cMessage{''.join(w.title() for w in key.split('_'))} = {message_code(key)};"
            in text
        )
    assert "const int cRepairMask = " in text and "shopBit" not in text
    masks = text.split("int shopMask")[1].split("}")[0]
    once = [p for p in shop.purchases if p.once]
    assert all(f"return ({2**p.bit});" in masks for p in once)
    assert "int shopName" not in text


def test_prelude_holds_no_test_only_names() -> None:
    text = prelude()
    assert "cBuy" not in text and "Tech =" not in text


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
        "shop_exact",
        "shop_repeat",
        "shop_walking",
        "shop_insufficient",
        "shop_once",
        "shop_requires",
        "shop_pending",
        "shop_relics",
        "shop_inactive",
        "gold_kings",
        "kill_rewards",
        "wave_kings",
        "investments",
        "attack_investment",
        "repair",
        "life_display",
        "tower_access",
        "shop_walk_across",
        "shop_walk_rows",
        "shop_single_file",
        "shop_settle",
        "spawn_blocked",
        "transfer",
        "king_stall_blocked",
        "shop_civ_lacks",
        "age_upgrades",
        "status_display",
        "pending_elimination",
        "tower_access_none",
        "shop_pause",
        "shop_requires_together",
        "notice_change",
        "transfer_type",
    ],
)
def test_shared_engine(engine_runner: Path, case: str) -> None:
    result = subprocess.run([str(engine_runner), case], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
