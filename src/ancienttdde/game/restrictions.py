"""What a defense lane may not build, train or research, so nothing reaches past the walls.

Raiders, traders and siege are confined by terrain and walls, so nothing may carry them across
(transport ships), outrange the walls (ranged castle units, warships, trebuchets, castle
arrows), take units from others (monks) or add units outside the purchase caps (production
buildings and their units). Villagers build towers and economy buildings only: population
comes from the shop, and every lane has its market, blacksmith and university from the start.
The tables themselves live in restricted.py.
"""

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.technology_state import TechnologyState
from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.game.config import RULED_OUT, TOWER_RANGE
from ancienttdde.game.restricted import AGE_UPGRADES, OBJECTS, TECHNOLOGIES, TOWER_BONUSES
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect


def disable_objects(trigger: TriggerHandle, player: int, objects: tuple[int, ...]) -> None:
    for unit in objects:
        effect(
            trigger,
            "enable_disable_object",
            source_player=player,
            object_list_unit_id=unit,
            enabled=0,
        )


def restrict(game: Game, trigger: TriggerHandle, player: int) -> None:
    """Disable the restricted objects and what would make them available again."""
    disable_objects(trigger, player, tuple(OBJECTS))
    technologies = [*TECHNOLOGIES, *TOWER_BONUSES, *(TechInfo[name].ID for name in RULED_OUT)]
    for technology in technologies:
        effect(
            trigger,
            "enable_disable_technology",
            source_player=player,
            technology=technology,
            enabled=0,
        )
    silence(game, trigger, player)
    # Siege power-up trebuchets stay on their islets, packed or not.
    for unit in ("TREBUCHET", "TREBUCHET_PACKED"):
        game.set_attribute(trigger, player, UnitInfo[unit].ID, ObjectAttribute.MOVEMENT_SPEED, 0)


def silence(game: Game, trigger: TriggerHandle, player: int) -> None:
    """A bought castle keeps its population and research but fires no arrows, and monks only
    carry relics."""
    castle = BuildingInfo["CASTLE"].ID
    for attribute in (
        ObjectAttribute.MAXIMUM_RANGE,
        ObjectAttribute.TOTAL_MISSILES,
        ObjectAttribute.MAXIMUM_TOTAL_MISSILES,
    ):
        game.set_attribute(trigger, player, castle, attribute, 0)
    game.set_attribute(trigger, player, UnitInfo["MONK"].ID, ObjectAttribute.MAXIMUM_RANGE, 0)


def restrict_reach(game: Game, player: int) -> None:
    """Blacksmith and unique technologies add castle and monk range back; every second, the
    lane's castle and monks lose it again."""
    trigger = game.trigger(f"lane.p{player}.restrict.reach", looping=True)
    condition(trigger, "timer", timer=1)
    game.value(trigger, f"lane.p{player}.active", 1)
    silence(game, trigger, player)


def restrict_competitive(game: Game) -> None:
    """With rivals beside every lane, no tower may reach the next lane."""
    trigger = game.trigger("game.restrict.competitive", looping=False)
    game.value(trigger, "game.participants", 2, Comparison.LARGER_OR_EQUAL)
    for player in range(1, 8):
        for name in TOWER_RANGE:
            effect(
                trigger,
                "enable_disable_technology",
                source_player=player,
                technology=TechInfo[name].ID,
                enabled=0,
            )


def restrict_ages(game: Game, player: int) -> None:
    """Once a lane reaches an age, disable the building forms that age upgraded into."""
    prefix = f"lane.p{player}"
    for age, objects in AGE_UPGRADES.items():
        trigger = game.trigger(f"{prefix}.restrict.{age.lower()}", looping=False)
        game.value(trigger, f"{prefix}.active", 1)
        condition(
            trigger,
            "technology_state",
            source_player=player,
            technology=TechInfo[age].ID,
            quantity=TechnologyState.DONE,
        )
        disable_objects(trigger, player, objects)
