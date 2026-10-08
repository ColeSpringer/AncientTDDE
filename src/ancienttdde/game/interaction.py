"""Native triggers for competition: PvP diplomacy, siege countdowns and protected Kings."""

from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.config import Balance
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import condition, effect


def pvp_diplomacy(game: Game) -> None:
    """With PvP on, every defense slot becomes every other's enemy once the options are fixed."""
    trigger = game.trigger("game.pvp", looping=False)
    game.value(trigger, "game.pvp", 1)
    game.value(trigger, "game.locked", 1)
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
