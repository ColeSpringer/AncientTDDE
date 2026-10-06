"""Typed native-trigger operations over the pinned parser's dynamic factories."""

from typing import Literal, Protocol, cast

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.support.info_dataset_base import InfoDatasetBase
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.probes.models import FieldValue
from ancienttdde.registry import ReferenceRegistry

type Region = tuple[int, int, int, int]
type EffectName = Literal[
    "send_chat",
    "change_diplomacy",
    "research_technology",
    "modify_resource",
    "remove_object",
    "create_object",
    "task_object",
    "modify_attribute",
    "disable_unit_attackable",
    "disable_object_deletion",
    "change_object_stance",
    "change_variable",
    "activate_trigger",
    "deactivate_trigger",
    "display_timer",
    "kill_object",
    "enable_disable_object",
    "script_call",
    "declare_victory",
]
type ConditionName = Literal[
    "timer",
    "objects_in_area",
    "own_fewer_objects",
    "own_objects",
    "variable_value",
    "player_defeated",
]


class TriggerHandle(Protocol):
    trigger_id: int
    new_effect: object
    new_condition: object


class ComponentFactory(Protocol):
    def __call__(self, **attributes: FieldValue) -> object: ...


def effect(trigger: TriggerHandle, name: EffectName, **attributes: FieldValue) -> None:
    factory = cast(ComponentFactory, getattr(trigger.new_effect, name))
    factory(**attributes)


def condition(trigger: TriggerHandle, name: ConditionName, **attributes: FieldValue) -> None:
    factory = cast(ComponentFactory, getattr(trigger.new_condition, name))
    factory(**attributes)


def area(region: Region) -> dict[str, FieldValue]:
    x1, y1, x2, y2 = region
    return {"area_x1": x1, "area_y1": y1, "area_x2": x2, "area_y2": y2}


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
    "life": (BuildingInfo, "BARRACKS"),
    "blocker": (OtherInfo, "BLOCKER"),
    "sign": (OtherInfo, "SIGN"),
    "tree": (OtherInfo, "TREE_A"),
}

# The engine defeats a player who owns nothing but towers (including Outposts), walls,
# gates, farms, fish traps, trade units, fishing or transport ships. A defeated enemy
# satisfies conquest, so every active player must keep one of these counted objects.
SURVIVAL_OBJECTS: frozenset[str] = frozenset(
    {
        "king",
        "villager",
        "scout",
        "spearman",
        "galley",
        "trebuchet",
        "packed-trebuchet",
        "market",
        "dock",
        "town-center",
        "life",
    }
)

# Stock footprints in tiles. A building's position is the center of its footprint, so
# even sizes sit on tile corners (whole coordinates) and odd sizes on tile centers.
FOOTPRINTS: dict[str, int] = {
    "market": 4,
    "dock": 3,
    "mill": 2,
    "town-center": 4,
    "watch-tower": 1,
    "guard-tower": 1,
    "keep": 1,
    "bombard-tower": 1,
    "life": 3,
    "blocker": 1,
    "sign": 1,
}


def stock(key: str) -> int:
    dataset, name = OBJECTS[key]
    return dataset[name].ID


def survival_ids() -> frozenset[int]:
    return frozenset(stock(key) for key in SURVIVAL_OBJECTS)


def footprint_sizes() -> dict[int, int]:
    return {stock(key): size for key, size in FOOTPRINTS.items()}


def grid_offset(size: int) -> float:
    return 0.5 if size % 2 else 0.0


def center(key: str, x: int, y: int) -> tuple[float, float]:
    """Return the stored position for an object anchored at tile (x, y).

    Units and odd footprints are centered on that tile; even footprints are centered on
    the tile's corner, so the footprint covers tiles x - size / 2 through x + size / 2 - 1.
    """
    dataset, _ = OBJECTS[key]
    if dataset is UnitInfo:
        return x + 0.5, y + 0.5
    if key not in FOOTPRINTS:
        raise ValueError(f"Unknown footprint for placed object: {key}")
    offset = grid_offset(FOOTPRINTS[key])
    return x + offset, y + offset


def technology(name: str) -> int:
    return TechInfo[name].ID


class Arena:
    def __init__(self, scenario: AoE2DEScenario) -> None:
        self.scenario = scenario
        self.registry = ReferenceRegistry([])
        self.owners: dict[int, int] = {}
        self.triggers: dict[str, TriggerHandle] = {}
        self.scenario.map_manager.map_size = 64
        for tile in self.scenario.map_manager.terrain:
            tile.terrain_id, tile.elevation, tile.layer = 0, 0, -1

    def terrain(self, region: Region, terrain: int) -> None:
        x1, y1, x2, y2 = region
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self.scenario.map_manager.terrain[y * 64 + x].terrain_id = terrain

    def unit(
        self,
        key: str,
        kind: str,
        player: int,
        x: int,
        y: int,
        caption: str = "",
        *,
        capture_flag: int = CaptureFlag.DEFAULT,
    ) -> int:
        position_x, position_y = center(kind, x, y)
        unit = self.scenario.unit_manager.add_unit(
            player=player,
            unit_const=stock(kind),
            x=position_x,
            y=position_y,
            caption_string=caption,
            capture_flag=capture_flag,
        )
        self.registry.register("object", key, unit.reference_id)
        self.owners[unit.reference_id] = player
        return unit.reference_id

    def kings(self, key: str, player: int, count: int, x: int, y: int) -> None:
        for index in range(count):
            self.unit(f"{key}.{index}", "king", player, x + index % 6, y + index // 6)

    def trigger(self, key: str, *, enabled: bool = True, looping: bool = False) -> TriggerHandle:
        trigger = self.scenario.trigger_manager.add_trigger(
            key,
            enabled=enabled,
            looping=looping,
            execute_on_load=False,
        )
        self.registry.register("trigger", key, trigger.trigger_id)
        self.triggers[key] = trigger
        return trigger

    def objective(self, title: str, description: str) -> None:
        # Objectives are listed only while their trigger is enabled, and the entry is marked
        # complete once the trigger fires. A condition no trigger satisfies keeps the setup
        # text listed and open; the title is the short line shown on screen.
        pinned = self.scenario.trigger_manager.add_trigger(
            "Probe instructions",
            description=description,
            short_description=title,
            display_as_objective=True,
            display_on_screen=True,
        )
        self.variable("probe.instructions.complete")
        self.value(pinned, "probe.instructions.complete", 1)

    def variable(self, key: str) -> int:
        variable = self.scenario.trigger_manager.add_variable(key)
        self.registry.register("variable", key, variable.variable_id)
        return variable.variable_id

    def value(
        self, trigger: TriggerHandle, key: str, value: int, comparison: int = Comparison.EQUAL
    ) -> None:
        condition(
            trigger,
            "variable_value",
            variable=self.registry.resolve("variable", key),
            quantity=value,
            comparison=comparison,
        )

    def set_value(
        self, trigger: TriggerHandle, key: str, value: int, operation: int = Operation.SET
    ) -> None:
        effect(
            trigger,
            "change_variable",
            variable=self.registry.resolve("variable", key),
            quantity=value,
            operation=operation,
        )

    def clock(self, key: str, counter: str, operation: int, *, while_positive: str) -> None:
        """Adjust a seconds counter once per game second while another variable is positive.

        A Timer condition keeps its elapsed count while its trigger is disabled, so a stage
        trigger that is activated again fires immediately. Counting seconds in variables
        with a looping one-second clock gives every stage a fresh duration instead.
        """
        tick = self.trigger(key, looping=True)
        condition(tick, "timer", timer=1)
        self.value(tick, while_positive, 0, Comparison.LARGER)
        self.set_value(tick, counter, 1, operation)

    def activate(self, trigger: TriggerHandle, key: str) -> None:
        effect(trigger, "activate_trigger", trigger_id=self.registry.resolve("trigger", key))

    def deactivate(self, trigger: TriggerHandle, key: str) -> None:
        effect(trigger, "deactivate_trigger", trigger_id=self.registry.resolve("trigger", key))

    def pad(self, key: str, x: int, y: int, label: str) -> Region:
        self.unit(key, "sign", 0, x - 1, y, label)
        region = (x, y, x + 5, y + 4)
        # A terrain contrast marks a purchase region without blocking movement.
        self.terrain(region, 4)
        return region

    def on_pad(
        self, trigger: TriggerHandle, region: Region, player: int = 1, price: int = 1
    ) -> None:
        condition(
            trigger,
            "objects_in_area",
            source_player=player,
            object_list=stock("king"),
            quantity=price,
            **area(region),
        )

    def at_most(self, trigger: TriggerHandle, player: int, kind: str, count: int) -> None:
        """Require that the player owns no more than `count` objects of the kind.

        Own Fewer Objects holds at its quantity or below, so the quantity is the highest
        count that still satisfies the condition: a living cap of n uses n - 1, and zero
        describes a removed marker.
        """
        condition(
            trigger,
            "own_fewer_objects",
            source_player=player,
            object_list=stock(kind),
            quantity=count,
        )

    def pay(self, trigger: TriggerHandle, region: Region, player: int, price: int) -> None:
        effect(
            trigger,
            "remove_object",
            source_player=player,
            object_list_unit_id=stock("king"),
            max_units_affected=price,
            **area(region),
        )

    def protect(self, trigger: TriggerHandle, identifiers: list[int]) -> None:
        by_owner: dict[int, list[int]] = {}
        for identifier in identifiers:
            by_owner.setdefault(self.owners[identifier], []).append(identifier)
        for owner, selected in by_owner.items():
            effect(
                trigger,
                "disable_unit_attackable",
                source_player=owner,
                selected_object_ids=selected,
            )
            effect(
                trigger,
                "disable_object_deletion",
                source_player=owner,
                selected_object_ids=selected,
            )

    def resources(self, trigger: TriggerHandle, amount: int) -> None:
        for resource in (
            Attribute.FOOD_STORAGE,
            Attribute.WOOD_STORAGE,
            Attribute.STONE_STORAGE,
            Attribute.GOLD_STORAGE,
        ):
            effect(
                trigger,
                "modify_resource",
                source_player=1,
                tribute_list=resource,
                quantity=amount,
                operation=Operation.SET,
            )

    def research(self, trigger: TriggerHandle, name: str) -> None:
        effect(
            trigger,
            "research_technology",
            source_player=1,
            technology=technology(name),
            force_research_technology=1,
        )
