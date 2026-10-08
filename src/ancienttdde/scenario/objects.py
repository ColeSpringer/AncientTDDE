"""Stock object and technology identities the game and the probes share."""

from collections.abc import Mapping

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.heroes import HeroInfo
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.support.info_dataset_base import InfoDatasetBase
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.units import UnitInfo

type ObjectTable = Mapping[str, tuple[type[InfoDatasetBase], str]]

OBJECTS: dict[str, tuple[type[InfoDatasetBase], str]] = {
    "king": (UnitInfo, "KING"),
    "villager": (UnitInfo, "VILLAGER_MALE"),
    "villager-female": (UnitInfo, "VILLAGER_FEMALE"),
    "monk": (UnitInfo, "MONK"),
    "scout": (UnitInfo, "SCOUT_CAVALRY"),
    "spearman": (UnitInfo, "SPEARMAN"),
    "galley": (UnitInfo, "GALLEY"),
    "cart": (UnitInfo, "TRADE_CART_EMPTY"),
    "cog": (UnitInfo, "TRADE_COG"),
    "trebuchet": (UnitInfo, "TREBUCHET"),
    "packed-trebuchet": (UnitInfo, "TREBUCHET_PACKED"),
    "william": (HeroInfo, "WILLIAM_THE_CONQUEROR"),
    "market": (BuildingInfo, "MARKET"),
    "monastery": (BuildingInfo, "MONASTERY"),
    "castle": (BuildingInfo, "CASTLE"),
    "dock": (BuildingInfo, "DOCK"),
    "mill": (BuildingInfo, "MILL"),
    "outpost": (BuildingInfo, "OUTPOST"),
    "yurt": (BuildingInfo, "YURT_G"),
    "wide-yurt": (BuildingInfo, "YURT_H"),
    "town-center": (BuildingInfo, "TOWN_CENTER"),
    "watch-tower": (BuildingInfo, "WATCH_TOWER"),
    "guard-tower": (BuildingInfo, "GUARD_TOWER"),
    "keep": (BuildingInfo, "KEEP"),
    "bombard-tower": (BuildingInfo, "BOMBARD_TOWER"),
    "accursed-tower": (BuildingInfo, "THE_ACCURSED_TOWER"),
    "blocker": (OtherInfo, "BLOCKER"),
    "sign": (OtherInfo, "SIGN"),
    "tree": (OtherInfo, "TREE_A"),
    "relic": (OtherInfo, "RELIC"),
    "hay-stack": (OtherInfo, "HAY_STACK"),
    "gold-mine": (OtherInfo, "GOLD_MINE"),
    "stone-mine": (OtherInfo, "STONE_MINE"),
    "forage-bush": (OtherInfo, "FORAGE_BUSH"),
}


# Marker flags: scenario decoration that still obstructs collision-checked unit creation.
MARKER_FLAGS = ("FLAG_A", "FLAG_B", "FLAG_C", "FLAG_D", "FLAG_E", "FE_FLAG")


def marker_flags() -> frozenset[int]:
    return frozenset(OtherInfo[name].ID for name in MARKER_FLAGS)


def stock(key: str, objects: ObjectTable = OBJECTS) -> int:
    dataset, name = objects[key]
    return dataset[name].ID


def technology(name: str) -> int:
    """The technology ID for a dataset name; an unknown name is a content error."""
    try:
        return TechInfo[name].ID
    except KeyError as error:
        raise ValueError(f"Unknown technology: {name}") from error


def display_name(member: str) -> str:
    """A dataset member name as players read it: SPIES_AND_TREASON becomes Spies and Treason."""
    return member.replace("_", " ").title().replace(" And ", " and ").replace(" Of ", " of ")
