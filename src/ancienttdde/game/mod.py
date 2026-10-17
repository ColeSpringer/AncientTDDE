"""The files DE's Mod Center reads from a local mod folder besides the scenario."""

import json
from collections.abc import Mapping, Sized
from pathlib import Path

from ancienttdde.common.credits import NAME
from ancienttdde.game.config import Balance

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_END = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def game_facts(balance: Balance, lanes: Sized) -> dict[str, int]:
    """The numbers a description may name as {lanes}, {waves}, {bosses} and {population}."""
    return {
        "lanes": len(lanes),
        "waves": len(balance.waves),
        "bosses": sum(1 for wave in balance.waves if wave.boss),
        "population": balance.population_cap,
    }


def load_description(path: Path, facts: Mapping[str, int]) -> str:
    """The mod page text, one line with the game's numbers filled in. DE drops line breaks."""
    text = path.read_text(encoding="utf-8-sig").strip()
    if len(text.splitlines()) != 1:
        raise ValueError(f"Mod description must be one line of text: {path}")
    try:
        return text.format_map(facts)
    except (KeyError, IndexError, ValueError, AttributeError) as error:
        names = ", ".join(f"{{{name}}}" for name in facts)
        raise ValueError(f"Mod description placeholder must be one of {names}: {error}") from error


def load_thumbnail(path: Path) -> bytes:
    """The image DE uploads with the mod. Its dialog accepts PNG only."""
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE) or not data.endswith(PNG_END):
        raise ValueError(f"Mod thumbnail must be a complete PNG image: {path}")
    return data


def mod_info(description: str) -> str:
    """DE's info.json as DE writes it, one compact line. DE fills in the author on publishing."""
    info = {"Author": "", "CacheStatus": 0, "Description": description, "Title": NAME}
    return json.dumps(info, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
