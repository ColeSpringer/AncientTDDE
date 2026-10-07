"""The hosting instructions and sign texts follow the balance and the catalog."""

import json
from pathlib import Path
from typing import Any, cast

from ancienttdde.map.models import MapAnchor

ROOT = Path(__file__).resolve().parents[1]


def balance(path: Path = ROOT / "content/balance/game.json"):
    from ancienttdde.game.config import load_balance

    return load_balance(path)


def shop():
    from ancienttdde.game.catalog import load_shop

    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text())["anchors"]
    families = [name for name, _ in balance().towers.families]
    return load_shop(
        ROOT / "content/balance/shop.json", cast(dict[str, MapAnchor], anchors), families
    )


def test_special_tower_text_follows_the_configured_tower(tmp_path: Path) -> None:
    from ancienttdde.game.instructions import instructions

    assert "with 240 pierce attack and a range of 13" in instructions(balance(), shop())
    raw: dict[str, Any] = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["towers"]["special"].update({"attack": 10, "range": 9, "pierce_bonus": 100})
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw))
    assert "with 110 pierce attack and a range of 9" in instructions(balance(path), shop())


def test_kings_are_told_to_stand_still_for_the_sampled_seconds() -> None:
    from ancienttdde.game.instructions import instructions
    from ancienttdde.game.script import STILL_SAMPLES

    text = instructions(balance(), shop())
    assert f"stand for about {STILL_SAMPLES + 1} seconds" in text
    assert "pausing briefly" in text


def test_bonus_delivery_message_quotes_the_reward() -> None:
    from ancienttdde.game.instructions import bonus_delivered, bonus_reward

    reward = bonus_reward(balance(), "gold")
    assert reward == "10000 gold and endless gold mines"
    assert bonus_delivered(balance(), "gold") == (
        f"Gold bonus delivered: {reward} beside your mining camp."
    )
    assert bonus_delivered(balance(), "food").startswith(
        f"Food bonus delivered: {bonus_reward(balance(), 'food')} "
    )


def test_instructions_state_the_starting_grant_and_research() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop())
    assert "Starting Resources" not in text and "lobby's resources" not in text
    assert "starts with 750 food, 1500 wood, 1500 stone and 400 gold" in text
    assert "Ballistics, Murder Holes, Caravan, Wheelbarrow, Hand Cart and Spies and Treason" in text
    assert "The shop sells 2000 wood for 1 King and 1500 stone for 1 King." in text
    assert "right pad" not in text


def test_instructions_cope_with_no_starting_research(tmp_path: Path) -> None:
    from ancienttdde.game.instructions import instructions

    raw: dict[str, Any] = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["economy"]["starting_technologies"] = []
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw))
    text = instructions(balance(path), shop())
    assert "researched" not in text


def test_instructions_and_the_hero_share_the_credit() -> None:
    from ancienttdde.game.instructions import CREDIT, instructions

    assert instructions(balance(), shop()).rstrip().endswith(f"{CREDIT}.")
