"""Objectives that appear once they apply: the run's mode, sudden death, the siege, the result."""

from ancienttdde.game.controls import MODES
from ancienttdde.game.script import STAGES, State
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import effect


def objective(game: Game, key: str, text: str, description: str, *, shown: bool = False) -> int:
    """An objective that shows its text, with live variables, from the start or once revealed."""
    trigger = game.scenario.trigger_manager.add_trigger(
        key,
        short_description=text,
        description=description,
        display_as_objective=True,
        display_on_screen=True,
        enabled=shown,
        execute_on_load=False,
    )
    game.names.register("trigger", key, trigger.trigger_id)
    # Never fires: it only displays its text.
    game.value(trigger, "game.phase", -1)
    return trigger.trigger_id


def reveal(game: Game, key: str, target: int, values: dict[str, int]) -> None:
    trigger = game.trigger(key, looping=False)
    for name, value in values.items():
        game.value(trigger, name, value)
    effect(trigger, "activate_trigger", trigger_id=target)


def run_objectives(game: Game) -> None:
    def variable(name: str) -> str:
        return f"<Variable {game.names.resolve('variable', name)}>"

    fixed = {"game.locked": 1}
    practice = objective(
        game,
        "game.objective.practice",
        "Practice run: assisted, not a standard result",
        "Practice controls below the shop were available in this run.",
    )
    reveal(game, "game.reveal.practice", practice, {"game.mode": MODES.index("practice")} | fixed)
    endless = objective(
        game,
        "game.objective.endless",
        "Endless run: the waves continue after the finale",
        "The waves keep growing until the lane falls.",
    )
    reveal(game, "game.reveal.endless", endless, {"game.mode": MODES.index("endless")} | fixed)
    sudden = objective(
        game,
        "game.objective.sudden",
        f"Sudden death: lives lost in {variable('game.drain')} s",
        "Every survivor loses lives at each interval, more each time, while the waves grow.",
    )
    reveal(game, "game.reveal.sudden", sudden, {"game.stage": STAGES.index("sudden")})
    siege = objective(
        game,
        "game.objective.siege",
        f"Siege power-up: holder P{variable('game.siege_owner')} (P0: none), "
        f"{variable('game.siege_left')} s left; for sale again in "
        f"{variable('game.siege_cooldown')} s",
        "One player at a time holds the siege; its buyer waits longer than everyone else.",
    )
    reveal(game, "game.reveal.siege", siege, {"game.pvp": 1} | fixed)
    result = objective(
        game,
        "game.objective.result",
        f"Result: {variable('game.cleared')} waves cleared",
        "The chat summarizes the run.",
    )
    for ending, phase in (("victory", State.VICTORY), ("defeat", State.DEFEAT)):
        reveal(game, f"game.reveal.result.{ending}", result, {"game.phase": phase})
