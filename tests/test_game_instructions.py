"""The objectives tabs follow the balance and the catalog."""

import json
import re
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


def profiles(current: Any = None):
    from ancienttdde.game.civilizations import load_profiles

    return load_profiles(ROOT / "content/balance/civilizations.json", current or balance(), shop())


def tabs(game: Path | None = None) -> tuple[str, str, str]:
    """The Instructions, Hints and Scouts texts, from another balance file if given."""
    from ancienttdde.game.instructions import hints, instructions, scouts

    current = balance(game) if game else balance()
    return (
        instructions(current, shop()),
        hints(current, shop(), profiles(current)),
        scouts(current),
    )


def altered(tmp_path: Path, change: Any) -> Path:
    raw: dict[str, Any] = json.loads((ROOT / "content/balance/game.json").read_text())
    change(raw)
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw))
    return path


def test_instructions_state_the_hosting_rules() -> None:
    text, _, _ = tabs()
    assert text.startswith(
        "Hosting\nStandard data set, fixed positions, locked teams, Fast game speed, Reveal Map "
        "All Visible and Population 200."
    )
    assert (
        "Put humans in slots 1 to 7 and a computer in at least one other: the highest-numbered "
        "computer is the enemy, whichever slot it sits in" in text
    )
    assert (
        "The lobby's Difficulty sets the level. Easiest plays Easy. Standard and Moderate play "
        "Normal. Hard, Hardest and Extreme play Hard." in text
    )
    assert not re.search(r"[Cc]ompetitive games (always )?play (Easy|Normal|Hard)", text)


def test_instructions_state_the_goal() -> None:
    text, _, _ = tabs()
    assert (
        "Hold your lane: each enemy reaching the exit flags costs a life, a boss 5, and at 0 "
        "lives the lane falls. Solo, clearing all 56 waves wins" in text
    )
    assert (
        "sudden death drains every survivor's lives every 30 game seconds, more each time and "
        "up to 10 at once, until one remains" in text
    )


def test_instructions_explain_the_run_options() -> None:
    text, _, _ = tabs()
    assert (
        "The first human lane has 60 game seconds to select one Outpost in the row below the "
        "shop. Its first selection is final, and preparation starts at once. With no selection "
        "in time, the run is Standard with PvP off." in text
    )
    assert "Any human lane" not in text
    assert (
        "Standard, Endless (the waves go on after the finale) or Practice (assisted, with "
        "controls beside the options that start the next wave, add 5 Kings, add 5000 of each "
        "resource and restore all lives, each once per selection)" in text
    )
    assert "PvP on, which sells raiders and the siege power-up from the first wave" in text


def test_instructions_explain_kings_and_buying() -> None:
    from ancienttdde.game.script import STILL_SAMPLES

    text, _, _ = tabs()
    assert (
        "Every 1500 gold on Easy, 2000 on Normal or 3000 on Hard becomes a King at your stall "
        "above the shop. Surviving a wave earns 1 King, every 25 wave kills pay 125 stone and "
        "25 wood, and every 100 earn a King." in text
    )
    assert f"let them stand about {STILL_SAMPLES + 1} seconds" in text
    assert "a refusal nothing, and Kings left standing buy again" in text


def test_instructions_explain_building_and_population() -> None:
    text, _, _ = tabs()
    assert (
        "Villagers build towers, mills, camps and farms or pastures only. Towers stand in the "
        "build rows, and one built elsewhere is removed. Markets train trade carts and docks "
        "trade cogs, and nothing else trains or converts." in text
    )
    assert (
        "Bought villagers, traders and raiders, and the traders markets and docks train, need "
        "population room. A lane starts with room for 25 more, and only the shop's +65 "
        "population (again and again, up to 200), the castle and some profiles add more. "
        "Kings, monks and trebuchets take none." in text
    )
    assert "per shop purchase" not in text


def test_instructions_end_with_the_credit() -> None:
    from ancienttdde.game.instructions import CREDIT

    text, _, _ = tabs()
    assert text.rstrip().endswith(f"{CREDIT}.")


def test_the_tabs_carry_no_markdown() -> None:
    for text in tabs():
        assert "#" not in text and "**" not in text
        assert text[0].isalpha() and text.endswith("\n") and not text.endswith("\n\n")


def test_hints_explain_the_resources() -> None:
    _, text, _ = tabs()
    assert text.startswith("Resources\nGold comes from trade, relics, mining and the market.")
    assert (
        "Mining or foraging to the end of the gold, berry or stone rows pays 10000 gold, 1000 "
        "food or 3000 stone once and opens deposits that never run out" in text
    )
    assert "reach only you. Saving works at any point." in text


def test_hints_list_the_catalog_and_its_rules() -> None:
    _, text, _ = tabs()
    assert (
        "Purchases marked once are once per player, and some need another purchase first. "
        "Investments pay on every multiple of their period, counted from the start of "
        "preparation. The repair crew restores one life every 20 game seconds for 50 stone, up "
        "to the starting total. The castle brings population and its research but never fires."
        "\n\n- Tower attack +4: 1 King\n" in text
    )
    assert "- 2000 wood: 1 King\n- 1500 stone: 1 King\n" in text
    assert "- Siege power-up: 20 Kings, when PvP is on\n" in text
    for purchase in shop().purchases:
        assert f"- {purchase.caption}\n" in text


def test_hints_explain_the_towers(tmp_path: Path) -> None:
    _, text, _ = tabs()
    assert (
        "Tower attack raises Watch Towers, Guard Towers, Keeps and Bombard Towers, built now or "
        "later. Bombard Tower attack raises Bombard Towers alone." in text
    )
    assert "with 240 pierce attack and a range of 13" in text
    assert (
        "With Imperial Age and Chemistry, the Bombard Tower research completes on its own at "
        "no cost. Every game rules out Yasama, Stronghold and Siege Engineers, and competitive "
        "games Eupseong and Artillery. Towers fire one arrow of their own whatever the "
        "civilization." in text
    )

    def special(raw: dict[str, Any]) -> None:
        raw["towers"]["special"].update({"attack": 10, "range": 9, "pierce_bonus": 100})

    _, text, _ = tabs(altered(tmp_path, special))
    assert "with 110 pierce attack and a range of 9" in text


def test_hints_explain_raiders_and_the_siege() -> None:
    from ancienttdde.scenario.objects import display_name

    _, text, _ = tabs()
    assert "Each player keeps at most 2 land and 2 naval raiders alive. " in text
    for medium in ("land", "naval"):
        names = [
            display_name(key) for key, found, _ in profiles().raider_bonuses() if found == medium
        ]
        listed = ", ".join(names[:-1]) + " and " + names[-1]
        assert f". {listed} keep one more {medium} raider. " in text
    assert (
        "The siege power-up puts 2 trebuchets on each of the 8 islet rows flanking the lanes "
        "10 game seconds after purchase, for 60 game seconds, and they fire at every enemy "
        "tower and unit in reach. One player holds it at a time, and it is for sale again "
        "after 180 game seconds for everyone and 240 for its buyer." in text
    )


def test_hints_list_every_civilization_profile() -> None:
    _, text, _ = tabs()
    section = text.split("\nCivilizations\n")[1]
    assert section.startswith(
        "Each civilization keeps its technology tree and bonuses. Its profile adds the "
        "adjustments listed here, announced with your towers when preparation begins. Starting "
        "towers stand in mirrored pairs on the build rows beside the path.\n\n- "
    )
    listed = profiles()
    for civilization in listed.civilizations:
        assert f"- {civilization.name}: {listed.text(civilization)}." in section
    assert "+1 land raider with PvP on" in section and "+1 naval raider with PvP on" in section
    assert "+2 starting Keeps" in section and "+2 starting Bombard Towers" in section
    assert f"- Any other civilization: {listed.text(None)}." in section
    assert "Adjustments: +3 starting Kings" in listed.text(None)
    assert section.count("\n- ") == len(listed.civilizations) + 1


def test_civilizations_are_listed_alphabetically_with_the_default_last() -> None:
    _, text, _ = tabs()
    section = text.split("\nCivilizations\n")[1]
    names = [line[2:].split(":")[0] for line in section.splitlines() if line.startswith("- ")]
    *civilizations, default = names
    assert civilizations == sorted(civilizations)
    assert civilizations[:3] == ["Achaemenids", "Armenians", "Athenians"]
    assert default == "Any other civilization"


def test_scouts_name_the_enemy() -> None:
    _, _, text = tabs()
    assert text.startswith(
        "Enemy\nThe highest-numbered computer player, named in the chat at the start. Its units "
        "walk each lane's path at their native speed, never attack, and leave by the exit "
        "flags at the right-hand end."
    )


def test_scouts_describe_the_lane() -> None:
    _, _, text = tabs()
    assert (
        "You start with 750 food, 1500 wood, 1500 stone and 400 gold, 30 lives, three Kings in "
        "the shop, villagers in the build and resource areas, eight trade carts and four trade "
        "cogs already trading, and 2 relics in the monasteries, with Ballistics, Murder Holes, "
        "Caravan, Wheelbarrow, Hand Cart and Spies and Treason researched." in text
    )
    assert (
        "one standing on the flag at the end of a walkway crosses (its relic names where it "
        "goes) and arrives on a flag. The life Outpost below the shop shows your lives.\n" in text
    )
    assert "stall" not in text and "Starting Resources" not in text


def test_scouts_cope_with_no_starting_research(tmp_path: Path) -> None:
    def none(raw: dict[str, Any]) -> None:
        raw["economy"]["starting_technologies"] = []

    _, _, text = tabs(altered(tmp_path, none))
    assert "researched" not in text
    assert "2 relics in the monasteries. Villagers" in text


def test_scouts_scale_the_schedule_by_difficulty() -> None:
    _, _, text = tabs()
    assert (
        "The first wave comes after 293 game seconds of preparation, about 146 real seconds at "
        "Fast. Enemies spawn in pairs on the same schedule in every surviving lane, in threes "
        "from wave 31, and each boss alone. The next wave follows 30 game seconds" in text
    )
    assert (
        "Hit points below are for Normal: 80% on Easy and 110% on Hard, up to 32767 for "
        "regular enemies. The time is each wave's spawning span in game seconds, and pierce "
        "armor is listed where the schedule sets it." in text
    )
    assert "refilled from its whole amount as it takes damage" in text
    assert "\n\n1. Villagers: 30 enemies, 45 HP each, 45 s\n" in text
    assert "\n26. Hrolf the Ganger: 30 enemies, 24750 HP each, 119 pierce armor, 45 s\n" in text
    assert "\n47. Charlemagne: boss, 1274000 HP, 180 pierce armor\n" in text
    assert "\n56. Abraha Elephant: boss, 1870000 HP, " in text
    assert "game seconds, and pierce armor is listed where the schedule sets it." in text


def test_the_schedule_shows_hit_points_at_the_default_level(tmp_path: Path) -> None:
    def hard(raw: dict[str, Any]) -> None:
        raw["difficulty"]["default"] = "hard"

    _, _, text = tabs(altered(tmp_path, hard))
    assert "Hit points below are for Hard: 80% on Easy and 100% on Normal" in text
    # 45 hit points at 110%, rounded.
    assert "1. Villagers: 30 enemies, 50 HP each" in text


def test_scouts_explain_the_waves_after_the_finale() -> None:
    _, _, text = tabs()
    assert (
        "After the finale, Endless runs and sudden death repeat Elite Conquistadors, Attila the "
        "Hun, Master of the Templar, Lancelot and Henry V in turn at 32767 hit points, each "
        "wave with +25 pierce armor more." in text
    )


def test_scouts_place_the_rivals() -> None:
    _, _, text = tabs()
    assert (
        "With PvP on, land raiders (light cavalry) fight in the land trade field below the "
        "markets and naval raiders (fire galley) in the trade channel below the docks. They "
        "attack every rival's traders and raiders there and cannot leave. Markets, docks, "
        "Kings, life Outposts, yurts and trebuchets cannot be attacked, but traders can." in text
    )
    assert "islet rows" not in text and "between the lanes" not in text


def test_the_document_collects_the_tabs() -> None:
    from ancienttdde.game.instructions import CREDIT, document

    text = document(balance(), shop(), profiles())
    assert text.startswith("# Ancient TD DE\n\n## Instructions\n\n### Hosting\n\nStandard data set")
    assert "\n\n## Hints\n\n### Resources\n\n" in text
    assert "\n\n## Scouts\n\n### Enemy\n\n" in text
    assert text.rstrip().endswith(f"{CREDIT}.") and text.count(CREDIT) == 1
    parts = text.split("\n## ")
    assert [part.split("\n")[0] for part in parts[1:]] == ["Instructions", "Hints", "Scouts"]
    # Each tab's lines appear under its own heading, in the tab's order. The credit is last.
    for part, tab in zip(parts[1:], tabs(), strict=True):
        position = 0
        for line in tab.splitlines():
            if line and line != f"{CREDIT}.":
                position = part.index(line, position) + len(line)


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


def test_the_kill_king_message_counts_wave_kills() -> None:
    from ancienttdde.game.messages import message_texts

    text = message_texts(balance())["kill_king"]
    assert text == "Kill reward: every 100 wave kills earn a King. One arrives at your stall."
