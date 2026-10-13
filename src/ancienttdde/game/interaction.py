"""Native triggers for competition: PvP diplomacy and pads, siege countdowns and protected
Kings."""

from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.catalog import Shop
from ancienttdde.game.config import Balance
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import condition, effect


def pvp_diplomacy(game: Game) -> None:
    """With PvP on, every defense slot becomes every other's enemy when the first wave starts."""
    trigger = game.trigger("game.pvp", looping=False)
    game.value(trigger, "game.pvp", 1)
    game.value(trigger, "game.wave", 0, Comparison.LARGER_OR_EQUAL)
    for source in range(1, 8):
        for target in range(1, 8):
            if source != target:
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
            timer=1,
        )
        game.set_value(trigger, "game.siege_display", 0)


def protect_kings(game: Game, player: int) -> None:
    """Kings are currency, not targets: every second, a lane's Kings become unattackable."""
    trigger = game.trigger(f"lane.p{player}.kings.protect", looping=True)
    condition(trigger, "timer", timer=1)
    game.value(trigger, f"lane.p{player}.active", 1)
    effect(
        trigger,
        "disable_unit_attackable",
        source_player=player,
        object_list_unit_id=game.stock("king"),
    )
