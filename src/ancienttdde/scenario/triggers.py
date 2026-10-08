"""Typed native-trigger operations over the pinned parser's dynamic factories."""

from collections.abc import Mapping
from typing import Literal, Protocol, cast

from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.models import Rect
from ancienttdde.registry import NameTable
from ancienttdde.scenario.objects import OBJECTS, ObjectTable, stock, technology

type FieldValue = int | float | str | bool | list[int]

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
    "create_garrisoned_object",
    "change_ownership",
    "change_object_name",
    "enable_disable_technology",
    "clear_timer",
    "change_view",
]
type ConditionName = Literal[
    "timer",
    "objects_in_area",
    "own_fewer_objects",
    "own_objects",
    "variable_value",
    "player_defeated",
    "object_selected_multiplayer",
    "technology_state",
]


class TriggerHandle(Protocol):
    @property
    def trigger_id(self) -> int: ...
    @property
    def new_effect(self) -> object: ...
    @property
    def new_condition(self) -> object: ...


class ComponentFactory(Protocol):
    def __call__(self, **attributes: FieldValue) -> object: ...


def effect(trigger: TriggerHandle, name: EffectName, **attributes: FieldValue) -> None:
    factory = cast(ComponentFactory, getattr(trigger.new_effect, name))
    factory(**attributes)


def condition(trigger: TriggerHandle, name: ConditionName, **attributes: FieldValue) -> None:
    factory = cast(ComponentFactory, getattr(trigger.new_condition, name))
    factory(**attributes)


def area(region: Rect) -> dict[str, FieldValue]:
    x1, y1, x2, y2 = region
    return {"area_x1": x1, "area_y1": y1, "area_x2": x2, "area_y2": y2}


# Resource storage attributes by resource name, in DE's attribute order.
STORAGE: dict[str, int] = {
    "food": Attribute.FOOD_STORAGE,
    "wood": Attribute.WOOD_STORAGE,
    "stone": Attribute.STONE_STORAGE,
    "gold": Attribute.GOLD_STORAGE,
}
# DE's attack and armour class for pierce.
PIERCE = 3


class Builder:
    """Named triggers and variables, and the native operations generated scenarios share."""

    def __init__(self, scenario: AoE2DEScenario, objects: ObjectTable = OBJECTS) -> None:
        self.scenario = scenario
        self.objects = objects
        self.names = NameTable()

    def stock(self, kind: str) -> int:
        """Return the stock object ID that this builder's object table gives `kind`."""
        return stock(kind, self.objects)

    def trigger(self, key: str, *, looping: bool, enabled: bool = True) -> TriggerHandle:
        """Add a named trigger; every caller states whether it repeats."""
        trigger = self.scenario.trigger_manager.add_trigger(
            key,
            enabled=enabled,
            looping=looping,
            execute_on_load=False,
        )
        self.names.register("trigger", key, trigger.trigger_id)
        return trigger

    def variable(self, key: str, variable_id: int = -1) -> int:
        variable = self.scenario.trigger_manager.add_variable(key, variable_id=variable_id)
        self.names.register("variable", key, variable.variable_id)
        return variable.variable_id

    def value(
        self, trigger: TriggerHandle, key: str, amount: int, comparison: int = Comparison.EQUAL
    ) -> None:
        condition(
            trigger,
            "variable_value",
            variable=self.names.resolve("variable", key),
            quantity=amount,
            comparison=comparison,
        )

    def set_value(
        self, trigger: TriggerHandle, key: str, amount: int, operation: int = Operation.SET
    ) -> None:
        effect(
            trigger,
            "change_variable",
            variable=self.names.resolve("variable", key),
            quantity=amount,
            operation=operation,
        )

    def owners(self) -> dict[int, int]:
        """Return the owning player of every placed object, by instance ID."""
        units = self.scenario.unit_manager.units
        return {unit.reference_id: player for player, placed in enumerate(units) for unit in placed}

    def protect(self, trigger: TriggerHandle, identifiers: list[int]) -> None:
        """Make placed objects unattackable and undeletable.

        DE applies these effects only to the source player's objects, so each owner gets
        its own pair of effects.
        """
        owners = self.owners()
        by_owner: dict[int, list[int]] = {}
        for identifier in identifiers:
            if identifier not in owners:
                raise ValueError(f"Cannot protect an object that was never placed: {identifier}")
            by_owner.setdefault(owners[identifier], []).append(identifier)
        for owner, selected in by_owner.items():
            for name in ("disable_unit_attackable", "disable_object_deletion"):
                effect(trigger, name, source_player=owner, selected_object_ids=selected)

    def rename(
        self,
        trigger: TriggerHandle,
        target: int,
        text: str,
        *,
        owners: Mapping[int, int] | None = None,
    ) -> None:
        """Name a placed object when the trigger fires; DE shows the name on selection.

        Pass `owners` from one owners() call when naming many objects.
        """
        owners = self.owners() if owners is None else owners
        if target not in owners:
            raise ValueError(f"Cannot name an object that was never placed: {target}")
        effect(
            trigger,
            "change_object_name",
            source_player=owners[target],
            selected_object_ids=[target],
            message=text,
        )

    def resources(
        self,
        trigger: TriggerHandle,
        amount: int,
        *,
        player: int = 1,
        operation: int = Operation.SET,
    ) -> None:
        for resource in STORAGE.values():
            effect(
                trigger,
                "modify_resource",
                source_player=player,
                tribute_list=resource,
                quantity=amount,
                operation=operation,
            )

    def research(self, trigger: TriggerHandle, name: str, *, player: int = 1) -> None:
        effect(
            trigger,
            "research_technology",
            source_player=player,
            technology=technology(name),
            force_research_technology=1,
        )

    def attack_bonus(
        self, trigger: TriggerHandle, player: int, units: tuple[int, ...], amount: int
    ) -> None:
        """Add pierce attack to object definitions, so later copies and upgrades keep it too."""
        for unit in units:
            effect(
                trigger,
                "modify_attribute",
                source_player=player,
                object_list_unit_id=unit,
                object_attributes=ObjectAttribute.ATTACK,
                operation=Operation.ADD,
                armour_attack_class=PIERCE,
                armour_attack_quantity=amount,
            )

    def set_attribute(
        self, trigger: TriggerHandle, player: int, unit: int, attribute: int, quantity: float
    ) -> None:
        """Set an attribute of a player's object definition, for copies made now and later."""
        effect(
            trigger,
            "modify_attribute",
            source_player=player,
            object_list_unit_id=unit,
            object_attributes=attribute,
            operation=Operation.SET,
            quantity=quantity,
        )

    def tower_attack_bonus(self, trigger: TriggerHandle, amount: int, *, player: int = 1) -> None:
        """Add pierce attack to the stock arrow-tower definitions."""
        towers = tuple(self.stock(kind) for kind in ("watch-tower", "guard-tower", "keep"))
        self.attack_bonus(trigger, player, towers, amount)

    def on_pad(self, trigger: TriggerHandle, region: Rect, player: int = 1, price: int = 1) -> None:
        condition(
            trigger,
            "objects_in_area",
            source_player=player,
            object_list=self.stock("king"),
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
            object_list=self.stock(kind),
            quantity=count,
        )

    def pay(self, trigger: TriggerHandle, region: Rect, player: int, price: int) -> None:
        effect(
            trigger,
            "remove_object",
            source_player=player,
            object_list_unit_id=self.stock("king"),
            max_units_affected=price,
            **area(region),
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
