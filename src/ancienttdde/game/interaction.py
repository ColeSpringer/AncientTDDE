"""Native triggers for competition: PvP diplomacy and pads, siege countdowns, and protected
Kings and trebuchets."""

from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.catalog import Shop
from ancienttdde.game.config import Balance
from ancienttdde.game.script import SIEGE_PHASE_ACTIVE
from ancienttdde.game.triggers import Game
from ancienttdde.game.waves import LANE_SLOTS, SIEGE_TIMER
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect


def pvp_diplomacy(game: Game) -> None:
    """With PvP on, every two lanes that play become enemies when the first wave starts. A
    cleared lane, the enemy's own among them, or a closed one never plays, so no effect names
    a player who is not in the game."""
    for source in LANE_SLOTS:
        for target in LANE_SLOTS:
            if source == target:
                continue
            trigger = game.trigger(f"game.pvp.p{source}.p{target}", looping=False)
            game.value(trigger, "game.pvp", 1)
            game.value(trigger, "game.wave", 0, Comparison.LARGER_OR_EQUAL)
            game.value(trigger, f"lane.p{source}.active", 1)
            game.value(trigger, f"lane.p{target}.active", 1)
            effect(
                trigger,
                "change_diplomacy",
                source_player=source,
                target_player=target,
                diplomacy=DiplomacyState.ENEMY,
            )


def open_pvp_pads(game: Game, shop: Shop) -> None:
    """Selecting PvP on removes the Hay Stacks that seal the raider and siege pads; only that
    selection, which fixes the options, switches PvP on."""
    gates = [
        identifier
        for purchase in shop.purchases
        for identifier in game.names.registered("object", f"shop.{purchase.key}.gate.")
    ]
    # Selecting nothing would remove every Gaia object.
    if not gates:
        raise ValueError("No PvP pad gates to open")
    trigger = game.trigger("game.pvp.open", looping=False)
    game.value(trigger, "game.pvp", 1)
    effect(trigger, "remove_object", source_player=0, selected_object_ids=gates)


def siege_countdowns(game: Game, balance: Balance) -> None:
    """Show everyone how long the siege warning, the siege and the shared cooldown last."""
    siege = balance.interaction.siege
    for code, seconds, message in (
        (1, siege.warning_seconds, "Siege arrives in %d"),
        (2, siege.active_seconds, "Siege ends in %d"),
        (3, siege.shared_cooldown, "Siege for sale again in %d"),
    ):
        trigger = game.trigger(f"game.siege.display.{code}", looping=True)
        game.value(trigger, "game.siege_display", code)
        effect(
            trigger,
            "display_timer",
            display_time=seconds,
            time_unit=TimeUnit.SECONDS,
            message=message,
            reset_timer=1,
            timer=SIEGE_TIMER,
        )
        game.set_value(trigger, "game.siege_display", 0)


def unattackable(game: Game, trigger: TriggerHandle, player: int, units: tuple[str, ...]) -> None:
    """Make a lane's units of these kinds unattackable whenever the trigger fires."""
    for unit in units:
        effect(
            trigger,
            "disable_unit_attackable",
            source_player=player,
            object_list_unit_id=game.stock(unit),
        )


def protect_kings(game: Game, player: int) -> None:
    """Kings are currency, not targets: every second, a lane's Kings become unattackable."""
    trigger = game.trigger(f"lane.p{player}.kings.protect", looping=True)
    condition(trigger, "timer", timer=1)
    game.value(trigger, f"lane.p{player}.active", 1)
    unattackable(game, trigger, player, ("king",))


def protect_siege(game: Game, player: int) -> None:
    """While a lane's siege is active, every trigger pass makes its trebuchets, packed or not,
    unattackable."""
    trigger = game.trigger(f"lane.p{player}.siege.protect", looping=True)
    game.value(trigger, "game.siege_owner", player)
    game.value(trigger, "game.siege_phase", SIEGE_PHASE_ACTIVE)
    unattackable(game, trigger, player, ("trebuchet", "packed-trebuchet"))
