"""Stock object and technology identities the game and the probes share."""

from collections.abc import Mapping

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.support.info_dataset_base import InfoDatasetBase
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.units import UnitInfo

type ObjectTable = Mapping[str, tuple[type[InfoDatasetBase], str]]

OBJECTS: dict[str, tuple[type[InfoDatasetBase], str]] = {
    "king": (UnitInfo, "KING"),
    "villager": (UnitInfo, "VILLAGER_MALE"),
    "scout": (UnitInfo, "SCOUT_CAVALRY"),
    "spearman": (UnitInfo, "SPEARMAN"),
    "galley": (UnitInfo, "GALLEY"),
    "cart": (UnitInfo, "TRADE_CART_EMPTY"),
    "cog": (UnitInfo, "TRADE_COG"),
    "trebuchet": (UnitInfo, "TREBUCHET"),
    "packed-trebuchet": (UnitInfo, "TREBUCHET_PACKED"),
    "market": (BuildingInfo, "MARKET"),
    "dock": (BuildingInfo, "DOCK"),
    "mill": (BuildingInfo, "MILL"),
    "town-center": (BuildingInfo, "TOWN_CENTER"),
    "watch-tower": (BuildingInfo, "WATCH_TOWER"),
    "guard-tower": (BuildingInfo, "GUARD_TOWER"),
    "keep": (BuildingInfo, "KEEP"),
    "bombard-tower": (BuildingInfo, "BOMBARD_TOWER"),
    "blocker": (OtherInfo, "BLOCKER"),
    "sign": (OtherInfo, "SIGN"),
    "tree": (OtherInfo, "TREE_A"),
}


def stock(key: str, objects: ObjectTable = OBJECTS) -> int:
    dataset, name = objects[key]
    return dataset[name].ID


def technology(name: str) -> int:
    return TechInfo[name].ID
