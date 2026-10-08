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


def profiles():
    from ancienttdde.game.civilizations import load_profiles

    return load_profiles(ROOT / "content/balance/civilizations.json", balance(), shop())


def test_special_tower_text_follows_the_configured_tower(tmp_path: Path) -> None:
    from ancienttdde.game.instructions import instructions

    assert "with 240 pierce attack and a range of 13" in instructions(balance(), shop(), profiles())
    raw: dict[str, Any] = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["towers"]["special"].update({"attack": 10, "range": 9, "pierce_bonus": 100})
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw))
    assert "with 110 pierce attack and a range of 9" in instructions(
        balance(path), shop(), profiles()
    )


def test_kings_are_told_to_stand_still_for_the_sampled_seconds() -> None:
    from ancienttdde.game.instructions import instructions
    from ancienttdde.game.script import STILL_SAMPLES

    text = instructions(balance(), shop(), profiles())
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

    text = instructions(balance(), shop(), profiles())
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
    text = instructions(balance(path), shop(), profiles())
    assert "Every lane starts with" not in text


def test_instructions_and_the_hero_share_the_credit() -> None:
    from ancienttdde.game.instructions import CREDIT, instructions

    assert instructions(balance(), shop(), profiles()).rstrip().endswith(f"{CREDIT}.")


def test_instructions_explain_the_run_options_and_difficulty() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "row of Outposts below the shop" in text
    assert "Standard, Endless or Practice" in text
    assert (
        "Competitive games start with PvP off; selecting PvP on puts raiders and the siege "
        "power-up on sale" in text
    )
    assert (
        "Easiest plays Easy; Standard and Moderate play Normal; Hard, Hardest and Extreme "
        "play Hard" in text
    )
    assert "Competitive games always play Normal" in text
    assert "Every 1500 gold on Easy, 2000 on Normal or 3000 on Hard" in text
    assert "Every 2000 gold you hold" not in text


def test_instructions_scale_the_schedule_by_difficulty() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "Hit points below are for Normal: 80% on Easy and 125% on Hard" in text
    assert "1. Villagers: 60 enemies with 150 HP each" in text


def test_the_schedule_shows_hit_points_at_the_competitive_level(tmp_path: Path) -> None:
    from ancienttdde.game.instructions import instructions

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["difficulty"]["competitive"] = "hard"
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw))
    text = instructions(balance(path), shop(), profiles())
    assert "Hit points below are for Hard: 80% on Easy and 100% on Normal" in text
    # 150 hit points at 125%, rounded half up.
    assert "1. Villagers: 60 enemies with 188 HP each" in text


def test_instructions_explain_endless_practice_and_sudden_death() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "Two-Handed Swords, Cavaliers, Champions, Paladins and Elephant Finale repeat" in text
    assert "50% more hit points each round" in text and "+25 pierce armor" in text
    assert "5 more Kings" in text and "5000 more of each resource" in text
    assert "assisted" in text
    assert "every 30 game seconds" in text and "the waves keep growing" in text


def test_instructions_explain_raiders_and_the_siege() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "at most 2 land and 2 naval raiders alive" in text
    from ancienttdde.scenario.objects import display_name

    for medium in ("land", "naval"):
        names = [
            display_name(key) for key, found, _ in profiles().raider_bonuses() if found == medium
        ]
        listed = ", ".join(names[:-1]) + " and " + names[-1]
        assert f"{listed} keep one more {medium} raider" in text
    assert "2 trebuchets beside every surviving rival's towers" in text
    assert "10 game seconds" in text and "for 60 game seconds" in text
    assert "60 game seconds for everyone and 120 for its buyer" in text
    assert "no military buildings, docks, monasteries or town centers" in text


def test_instructions_explain_what_keeps_lanes_apart() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "every 25 wave kills pay 125 stone and 25 wood" in text
    assert "every 100 wave kills earn a King" in text
    assert "Towers stand only in your build rows" in text
    assert "Competitive games rule out Eupseong and Artillery" in text
    assert "Markets, docks, Kings, life Outposts and yurts cannot be attacked" in text
    assert "a bought castle never fires" in text
    assert "Each new selection of an Outpost acts once" in text
    assert "then the run options leave the row" in text


def test_instructions_list_every_civilization_profile() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    section = text.split("## Civilizations")[1].split("## ")[0]
    listed = profiles()
    for civilization in listed.civilizations:
        assert f"- {civilization.name}: {listed.text(civilization)}." in section
    assert "+1 land raider with PvP on" in section and "+1 naval raider with PvP on" in section
    assert f"- Any other civilization: {listed.text(None)}." in section
    assert "adjustments: +1 starting King" in listed.text(None)
    assert section.count("\n- ") == len(listed.civilizations) + 1


def test_the_kill_king_message_counts_wave_kills() -> None:
    from ancienttdde.game.messages import message_texts

    text = message_texts(balance())["kill_king"]
    assert text == "Kill reward: every 100 wave kills earn a King; one arrives at your stall."


def test_instructions_explain_what_villagers_build_and_where_population_comes_from() -> None:
    from ancienttdde.game.instructions import instructions

    text = instructions(balance(), shop(), profiles())
    assert "Your houses" not in text and "houses" in text
    assert (
        "Villagers build towers and economy buildings only: no houses, walls, gates, outposts, "
        "markets, blacksmiths or universities" in text
    )
    assert (
        "Population comes only from the shop's +80 population and castle, and from the "
        "civilization profiles that add some below" in text
    )
    assert "Every game rules out Yasama and Stronghold" in text
