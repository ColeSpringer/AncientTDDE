"""Generate fresh native gameplay over the migrated stock-DE map."""

import contextlib
import io
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from AoE2ScenarioParser.datasets.object_support import StartingAge
from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance
from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.engine.config import Balance, EngineLane, load_balance, load_lanes
from ancienttdde.engine.script import State, render_xs, variable_names
from ancienttdde.generation.scenario import construct_scenario
from ancienttdde.probes.native import TriggerHandle, area, condition, effect, stock, technology
from ancienttdde.probes.serialization import object_value, read_object
from ancienttdde.probes.xs import check_xs, xs_checker
from ancienttdde.registry import ReferenceRegistry

# DE's Fast lobby speed runs game time at twice real time.
FAST_GAME_SPEED = 2
# Lumber-camp trees hold more wood than a run uses. DE applies this effect value as a
# 16-bit number (1,000,000 arrived as 16,960), so it stays below 32,768.
LUMBER_TREE_WOOD = 32_000


class Game:
    def __init__(self, scenario: AoE2DEScenario) -> None:
        self.scenario = scenario
        self.registry = ReferenceRegistry([])
        for index, name in enumerate(variable_names()):
            variable = scenario.trigger_manager.add_variable(name, variable_id=index)
            self.registry.register("variable", name, variable.variable_id)
        for unit in scenario.unit_manager.get_all_units():
            self.registry.register("object", f"placement.{unit.reference_id}", unit.reference_id)

    def trigger(self, name: str, *, looping: bool = True) -> TriggerHandle:
        trigger = self.scenario.trigger_manager.add_trigger(
            name,
            enabled=True,
            looping=looping,
            execute_on_load=False,
        )
        self.registry.register("trigger", name, trigger.trigger_id)
        return trigger

    def value(
        self, trigger: TriggerHandle, key: str, amount: int, comparison: int = Comparison.EQUAL
    ) -> None:
        condition(
            trigger,
            "variable_value",
            variable=self.registry.resolve("variable", key),
            quantity=amount,
            comparison=comparison,
        )

    def set(self, trigger: TriggerHandle, key: str, amount: int) -> None:
        effect(
            trigger,
            "change_variable",
            variable=self.registry.resolve("variable", key),
            quantity=amount,
            operation=Operation.SET,
        )

    def protect(self, trigger: TriggerHandle, owner: int, identifiers: list[int]) -> None:
        if identifiers:
            for name in ("disable_unit_attackable", "disable_object_deletion"):
                effect(trigger, name, source_player=owner, selected_object_ids=identifiers)


def instructions(balance: Balance) -> str:
    schedule = "\n".join(
        f"{i}. {w.key}: {w.batches * w.count} enemies, {w.duration} game seconds"
        + (" (boss)" if w.boss else "")
        for i, w in enumerate(balance.waves, 1)
    )
    return (
        "# Ancient TD DE\n\n"
        "Host with the standard DE data set and all eight player slots. Put humans in "
        "any of slots 1–7 and fill the remaining slots with computers. Keep player 8 as "
        "the computer enemy. The embedded passive AI handles every computer slot. "
        "Only human-controlled defense lanes participate; computer-filled defense lanes "
        "are cleared automatically, and do not affect victory. "
        "Use fixed start positions, locked teams and Fast (the highest lobby game speed). "
        "The host must select game speed in the lobby; the scenario cannot set that control. "
        "Civilizations remain selectable. Set Reveal Map to All Visible.\n\n"
        "All seven defense players have a mill beside their berries, owned by that player. "
        f"Each human lane starts with {balance.lives} lives, two Watch Towers, its original "
        f"builders/economy, and {balance.starting_resources} of each resource. "
        f"Build more Watch Towers with the villagers beside your lane. Arrow towers receive "
        f"+{balance.tower_attack_bonus} pierce attack once, including future towers. "
        f"You receive {balance.income_amount} of each resource every {balance.income_interval} "
        "game seconds while your lane survives. Your eight carts and four cogs start trading "
        "automatically with their assigned partners. Gathering is also available, and the "
        "trees beside your lumber camps never run out.\n\n"
        f"Preparation lasts {balance.preparation_seconds} game seconds, about "
        f"{balance.preparation_seconds / FAST_GAME_SPEED:.0f} real seconds at Fast. "
        "Each enemy reaching the exit flags at the right-hand end of a lane costs one life. "
        "Computer-filled and eliminated lanes receive no waves or income. "
        "Enemies spawn in pairs on the same schedule in all surviving lanes. "
        f"There are {balance.intermission_seconds} game seconds between waves after the "
        "remaining enemies are cleared. The schedule lasts about "
        f"{balance.scheduled_seconds / 60:.1f} game minutes plus enemy cleanup.\n\n"
        "Solo victory requires clearing the entire finale. In competition the last survivor "
        "wins; multiple survivors after the finale enter sudden death. "
        f"Sudden death removes increasing lives from every survivor every "
        f"{balance.sudden_death_interval} game seconds, up to 10 lives per pulse. "
        "Simultaneous elimination of the entire field is a shared defeat. "
        "Resignation or disconnect eliminates that lane when DE reports it out of the game.\n\n"
        "The original King shop displays are closed. King purchases and generation, special "
        "tower purchases, trade raiders, siege purchases, Practice and Endless controls are "
        "unavailable in this ruleset. The two central Hay Stack pads in each lane remain "
        "reserved for special towers; ordinary towers cannot be built there. "
        "Do not use the gallery displays as purchase instructions.\n\n"
        "Save normally during preparation, waves or sudden death. Progress, life totals and "
        "countdowns are stored in the scenario.\n\n"
        "## Waves\n\n" + schedule + "\n\n"
        "Original Ancient Tower Defense map by DRAX6869 / DRAX.\n"
    )


def settings(game: Game, root: Path) -> None:
    scenario = game.scenario
    scenario.player_manager.active_players = 8
    for player in scenario.player_manager.players[1:]:
        player.human = player.player_id != 8
        player.civilization = "RANDOM" if player.human else "BRITONS"
        player.lock_civ = False
        player.lock_personality = True
        player.starting_age = StartingAge.FEUDAL_AGE
        player.population_cap = 200
        player.allied_victory = False
        player.food = player.wood = player.gold = player.stone = 0
        diplomacy: list[int] = [DiplomacyState.NEUTRAL] * 16
        diplomacy[7] = DiplomacyState.ENEMY
        if not player.human:
            diplomacy[:7] = [DiplomacyState.ENEMY] * 7
        diplomacy[player.player_id - 1] = DiplomacyState.ALLY
        player.diplomacy = diplomacy
    scenario.option_manager.victory_condition = VictoryCondition.CUSTOM
    scenario.option_manager.victory_custom_conditions_required = False
    victory = scenario.sections["GlobalVictory"]
    victory.conquest_required = victory.ruins = victory.artifacts_required = 0
    victory.discovery = victory.explored_percent_of_map_required = victory.gold_required = 0
    scenario.option_manager.lock_teams = True
    scenario.option_manager.allow_players_choose_teams = False
    scenario.option_manager.random_start_points = False
    scenario.option_manager.secondary_game_modes = 0
    scenario.option_manager.legacy_execution_order = False
    scenario.sections["Options"].all_techs = 0
    scenario.xs_manager.script_name = ""
    data = scenario.sections["PlayerDataTwo"]
    passive = (root / "src/ancienttdde/ai/passive.per").read_text()
    for index in range(8):
        data.ai_names[index] = "Ancient TD Passive"
        data.ai_files[index].ai_per_file_text = passive
        data.ai_type[index] = 0
    for unit in scenario.unit_manager.units[0]:
        unit.capture_flag = CaptureFlag.NEVER
        if unit.unit_const == stock("sign"):
            unit.caption_string = "Shop closed; build towers with your lane villagers"
    # A protected counted unit keeps the scenario-controlled enemy alive between waves.
    keeper = scenario.unit_manager.add_unit(player=8, unit_const=stock("king"), x=25.5, y=2.5)
    game.registry.register("object", "enemy.keeper", keeper.reference_id)
    init = game.trigger("game.initialize", looping=False)
    game.protect(init, 8, [keeper.reference_id])
    effect(
        init,
        "modify_attribute",
        source_player=8,
        object_list_unit_id=stock("king"),
        object_attributes=ObjectAttribute.MOVEMENT_SPEED,
        quantity=0,
        operation=Operation.SET,
    )
    endpoints = {stock("market"), stock("dock")}
    game.protect(
        init,
        0,
        [u.reference_id for u in scenario.unit_manager.units[0] if u.unit_const in endpoints],
    )


def lane_actions(game: Game, lane: EngineLane, balance: Balance) -> None:
    player = lane.player
    prefix = f"lane.p{player}"
    mill = game.scenario.unit_manager.add_unit(
        player=player, unit_const=stock("mill"), x=84, y=lane.center_y
    )
    game.registry.register("object", f"{prefix}.berry_mill", mill.reference_id)
    init = game.trigger(f"{prefix}.initialize")
    game.value(init, f"{prefix}.active", 1)
    game.value(init, f"{prefix}.initialized", 0)
    for resource in (
        Attribute.FOOD_STORAGE,
        Attribute.WOOD_STORAGE,
        Attribute.STONE_STORAGE,
        Attribute.GOLD_STORAGE,
    ):
        effect(
            init,
            "modify_resource",
            source_player=player,
            tribute_list=resource,
            quantity=balance.starting_resources,
            operation=Operation.SET,
        )
    effect(
        init,
        "modify_resource",
        source_player=player,
        tribute_list=Attribute.POPULATION_HEADROOM,
        quantity=200,
        operation=Operation.SET,
    )
    effect(
        init,
        "research_technology",
        source_player=player,
        technology=technology("FEUDAL_AGE"),
        force_research_technology=1,
    )
    effect(
        init,
        "enable_disable_object",
        source_player=player,
        object_list_unit_id=stock("watch-tower"),
        enabled=1,
    )
    for kind in ("watch-tower", "guard-tower", "keep"):
        effect(
            init,
            "modify_attribute",
            source_player=player,
            object_list_unit_id=stock(kind),
            object_attributes=ObjectAttribute.ATTACK,
            operation=Operation.ADD,
            armour_attack_class=3,
            armour_attack_quantity=balance.tower_attack_bonus,
        )
    for x in (26, 40):
        effect(
            init,
            "create_object",
            source_player=player,
            object_list_unit_id=stock("watch-tower"),
            location_x=x,
            location_y=lane.center_y - 3,
        )
    protected = [
        u.reference_id
        for u in game.scenario.unit_manager.units[player]
        if u.unit_const in {stock("market"), stock("dock")}
    ]
    protected.append(game.registry.resolve("object", f"placement.{lane.life_reference}"))
    game.protect(init, player, protected)
    for kind, partner in (("cart", lane.land_trade_partner), ("cog", lane.water_trade_partner)):
        traders = [
            u.reference_id
            for u in game.scenario.unit_manager.units[player]
            if u.unit_const == stock(kind)
        ]
        if traders:
            effect(
                init,
                "task_object",
                source_player=player,
                selected_object_ids=traders,
                location_object_reference=game.registry.resolve("object", f"placement.{partner}"),
                action_type=ActionType.DEFAULT,
            )
    game.set(init, f"{prefix}.initialized", 1)

    income = game.trigger(f"{prefix}.income")
    game.value(income, f"{prefix}.active", 1)
    game.value(income, f"{prefix}.income", 1)
    for resource in (
        Attribute.FOOD_STORAGE,
        Attribute.WOOD_STORAGE,
        Attribute.STONE_STORAGE,
        Attribute.GOLD_STORAGE,
    ):
        effect(
            income,
            "modify_resource",
            source_player=player,
            tribute_list=resource,
            quantity=balance.income_amount,
            operation=Operation.ADD,
        )
    game.set(income, f"{prefix}.income", 0)

    cleanup = game.trigger(f"{prefix}.cleanup")
    game.value(cleanup, f"{prefix}.cleanup", 1)
    effect(
        cleanup,
        "script_call",
        message=f"void ancientCleanupP{player}() {{ "
        f"ancientCleanupLane({player}, {mill.reference_id}); }}",
    )
    effect(cleanup, "remove_object", source_player=8, **area(lane.path))
    game.set(cleanup, f"{prefix}.cleanup", 0)

    for index, wave in enumerate(balance.waves, 1):
        spawn = game.trigger(f"{prefix}.wave.{index}")
        game.value(spawn, f"{prefix}.active", 1)
        game.value(spawn, f"{prefix}.spawn", index)
        game.value(spawn, "game.configured", index)
        for offset in range(wave.count):
            effect(
                spawn,
                "create_object",
                source_player=8,
                object_list_unit_id=wave.object_id,
                location_x=lane.spawn_x + offset,
                location_y=lane.center_y,
                disable_sound=1,
            )
        effect(
            spawn,
            "change_object_stance",
            source_player=8,
            object_list_unit_id=wave.object_id,
            attack_stance=AttackStance.STAND_GROUND,
            **area(lane.path),
        )
        effect(
            spawn,
            "task_object",
            source_player=8,
            object_list_unit_id=wave.object_id,
            location_x=lane.exit_x,
            location_y=lane.center_y,
            action_type=ActionType.MOVE,
            **area(lane.path),
        )
        game.set(spawn, f"{prefix}.spawn", 0)
    move = game.trigger(f"{prefix}.route")
    condition(move, "timer", timer=3)
    game.value(move, f"{prefix}.active", 1)
    effect(
        move,
        "task_object",
        source_player=8,
        location_x=lane.exit_x,
        location_y=lane.center_y,
        action_type=ActionType.MOVE,
        **area(lane.path),
    )

    lives = game.registry.resolve("variable", f"{prefix}.lives")
    objective = game.scenario.trigger_manager.add_trigger(
        f"{prefix}.status",
        short_description=f"P{player} lives: <Variable {lives}>",
        description=f"P{player}: prevent enemies reaching the right-hand exit.",
        display_as_objective=True,
        display_on_screen=True,
        enabled=True,
        execute_on_load=False,
    )
    # Never fires: its sole purpose is displaying the persisted life total.
    game.value(objective, "game.phase", -1)


def endless_lumber(game: Game, lanes: tuple[EngineLane, ...]) -> None:
    # New objects take their owner's current attributes, so the lumber trees are replaced
    # at the start, before any unit or building can occupy their tiles.
    trigger = game.trigger("game.lumber", looping=False)
    effect(
        trigger,
        "modify_attribute",
        source_player=0,
        object_list_unit_id=stock("tree"),
        object_attributes=ObjectAttribute.AMOUNT_OF_1ST_RESOURCE_STORAGE,
        operation=Operation.SET,
        quantity=LUMBER_TREE_WOOD,
    )
    for lane in lanes:
        x1, y1, x2, y2 = lane.economy
        trees = [
            u
            for u in game.scenario.unit_manager.units[0]
            if u.unit_const == stock("tree") and x1 <= int(u.x) <= x2 and y1 <= int(u.y) <= y2
        ]
        if len(trees) != 4:
            raise ValueError(f"P{lane.player} economy needs four lumber trees, found {len(trees)}")
        for tree in trees:
            placement = game.registry.resolve("object", f"placement.{tree.reference_id}")
            effect(trigger, "remove_object", source_player=0, selected_object_ids=[placement])
            effect(
                trigger,
                "create_object",
                source_player=0,
                object_list_unit_id=stock("tree"),
                location_x=int(tree.x),
                location_y=int(tree.y),
            )


def add_logic(game: Game, balance: Balance, lanes: tuple[EngineLane, ...]) -> None:
    endless_lumber(game, lanes)
    clock = game.trigger("game.clock")
    condition(clock, "timer", timer=1)
    effect(clock, "script_call", message="void ancientClockEffect() { ancientTick(); }")
    for index, wave in enumerate(balance.waves, 1):
        configure = game.trigger(f"game.wave.{index}.configure", looping=False)
        game.value(configure, "game.wave", index - 1)
        effect(
            configure,
            "modify_attribute",
            source_player=8,
            object_list_unit_id=wave.object_id,
            object_attributes=ObjectAttribute.HIT_POINTS,
            operation=Operation.SET,
            quantity=wave.hit_points,
        )
        effect(
            configure,
            "modify_attribute",
            source_player=8,
            object_list_unit_id=wave.object_id,
            object_attributes=ObjectAttribute.MOVEMENT_SPEED,
            operation=Operation.SET,
            quantity=0.65,
        )
        game.set(configure, "game.configured", index)
    for lane in lanes:
        lane_actions(game, lane, balance)
    for winner in range(1, 9):
        finish = game.trigger(f"game.result.p{winner}", looping=False)
        game.value(finish, "game.winner", winner)
        game.value(finish, "game.phase", State.DEFEAT if winner == 8 else State.VICTORY)
        effect(finish, "declare_victory", source_player=winner, enabled=1)


def construct_game(root: Path, map_path: Path, destination: Path) -> None:
    balance = load_balance(root / "content/balance/game.json")
    lanes = load_lanes(object_value(read_object(map_path).get("anchors"), "anchors"))
    with TemporaryDirectory(prefix="ancienttdde-map-") as temporary:
        foundation = Path(temporary) / "foundation.aoe2scenario"
        construct_scenario(root / "content/maps/format-seed.aoe2scenario", map_path, foundation)
        scenario = AoE2DEScenario.from_file(str(foundation))
    game = Game(scenario)
    settings(game, root)
    scenario.xs_manager.add_script(xs_string=render_xs(root, balance, lanes))
    add_logic(game, balance, lanes)
    scenario.message_manager.instructions = instructions(balance).replace("\n", "\r")
    with xs_checker(scenario):
        scenario.xs_manager.validate_scenario_xs()
        scenario.write_to_file(str(destination))
    check_xs(AoE2DEScenario.from_file(str(destination)))


if __name__ == "__main__":
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            if sys.argv[1] == "--check-xs":
                check_xs(AoE2DEScenario.from_file(sys.argv[2]))
            else:
                construct_game(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    except Exception:
        print(log.getvalue()[-18000:], file=sys.stderr)
        raise
