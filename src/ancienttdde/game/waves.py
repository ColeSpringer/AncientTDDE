"""The enemy, the wave clock, the AI rules that walk the waves, and results.

DE numbers a multiplayer game's players by their lobby colors and skips closed slots, so the
computer the host left in the last slot may hold any number. The XS takes the highest-numbered
computer in the game as the enemy. The native diplomacy and result effects exist once per
number it may hold, gated on the enemy variable. The XS creates the waves and sets their hit
points and armor itself. The enemy's own AI walks them, since a computer in a lane slot
ignores native orders online.
"""

from collections.abc import Sequence

from AoE2ScenarioParser.datasets.trigger_lists.diplomacy_state import DiplomacyState
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.game.config import Balance, EngineLane
from ancienttdde.game.objectives import objective
from ancienttdde.game.script import State
from ancienttdde.game.triggers import Game
from ancienttdde.models import Rect
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

# The player numbers the enemy may hold.
ENEMY_SLOTS = range(1, 9)
# The on-screen timers: every wave countdown shares one. The siege stages and the choice
# window, which can run beside it, have their own.
WAVE_TIMER = 0
SIEGE_TIMER = 1
CHOICE_TIMER = 2
# The player numbers that hold defense lanes.
LANE_SLOTS = range(1, 8)
# The AI goal pairs that hold the point a band is searched around and the point its standing
# enemies are sent to.
BAND_GOAL = 508
WALK_GOAL = 510
# The most units one AI search returns. A band's search stays within its lane's cap.
WALK_SEARCH = 240
# The DE AI script constants the walk rules use, with the values DE's own scripts define.
WALK_CONSTANTS = {
    "all-units-class": -1,
    "search-local": 1,
    "object-data-action": 5,
    "object-data-point-x": 8,
    "object-data-point-y": 9,
    "actionid-move": 610,
    "action-move": 1,
    "stance-no-attack": 3,
}


def game_clock(game: Game) -> None:
    clock = game.trigger("game.clock", looping=True)
    condition(clock, "timer", timer=1)
    effect(clock, "script_call", message="void ancientClockEffect() { ancientTick(); }")


def enemy_diplomacy(game: Game) -> None:
    """The original's one-way alliance for whichever number the enemy holds, set for each lane
    that plays: the lane treats the enemy as an enemy, and the enemy treats the lane as an
    ally, so its units attack nothing while the lane's towers fire at them. Cleared and closed
    lanes need none, so no effect names a player who is not in the game."""
    for lane in LANE_SLOTS:
        prefix = f"lane.p{lane}"
        for enemy in ENEMY_SLOTS:
            if enemy == lane:
                continue
            trigger = game.trigger(f"{prefix}.enemy.e{enemy}", looping=False)
            game.value(trigger, "game.enemy", enemy)
            game.value(trigger, f"{prefix}.active", 1)
            effect(
                trigger,
                "change_diplomacy",
                source_player=lane,
                target_player=enemy,
                diplomacy=DiplomacyState.ENEMY,
            )
            effect(
                trigger,
                "change_diplomacy",
                source_player=enemy,
                target_player=lane,
                diplomacy=DiplomacyState.ALLY,
            )


def show_status(game: Game, trigger: TriggerHandle, shown: str, hidden: str) -> None:
    """Switch the status line: the wait for the next wave, or the wave that is spawning."""
    effect(trigger, "activate_trigger", trigger_id=game.names.resolve("trigger", shown))
    effect(trigger, "deactivate_trigger", trigger_id=game.names.resolve("trigger", hidden))


def wave_countdown(game: Game, trigger: TriggerHandle, number: int, key: str, seconds: int) -> None:
    """Show the countdown to a wave and the status line that waits for it."""
    effect(
        trigger,
        "display_timer",
        display_time=seconds,
        time_unit=TimeUnit.SECONDS,
        message=f"Wave {number}: {key} in %d",
        reset_timer=1,
        timer=WAVE_TIMER,
    )
    show_status(game, trigger, "game.status.next", "game.status.spawning")


def wave_warnings(game: Game, balance: Balance) -> None:
    """Count down the choice window, then to each wave once its preparation or intermission
    begins. The script asks for the window's, the first wave's and each endless wave's
    countdown as it starts. The status line follows: the wait while it counts down, the wave
    once it starts."""
    # The engine asks for this countdown as it counts the window's first second off.
    choice = game.trigger("game.choice.warning", looping=True)
    game.value(choice, "game.wave_display", 3)
    effect(
        choice,
        "display_timer",
        display_time=balance.choice_seconds - 1,
        time_unit=TimeUnit.SECONDS,
        message="Run options close in %d",
        reset_timer=1,
        timer=CHOICE_TIMER,
    )
    game.set_value(choice, "game.wave_display", 0)
    endless = game.trigger("game.wave.endless.warning", looping=True)
    game.value(endless, "game.wave_display", 1)
    effect(
        endless,
        "display_timer",
        display_time=balance.intermission_seconds,
        time_unit=TimeUnit.SECONDS,
        message="Next wave in %d",
        reset_timer=1,
        timer=WAVE_TIMER,
    )
    show_status(game, endless, "game.status.next", "game.status.spawning")
    game.set_value(endless, "game.wave_display", 0)
    clear = game.trigger("game.wave.timer.clear", looping=True)
    game.value(clear, "game.wave_display", 2)
    effect(clear, "clear_timer", timer=WAVE_TIMER)
    show_status(game, clear, "game.status.spawning", "game.status.next")
    game.set_value(clear, "game.wave_display", 0)
    # A selection cuts the choice countdown short, and DE's Reset Timer keeps a running
    # timer's text, so the window's timer is cleared before the first wave's shows.
    first, *later = balance.waves
    opening = game.trigger("game.wave.1.warning", looping=True)
    game.value(opening, "game.wave_display", 4)
    effect(opening, "clear_timer", timer=CHOICE_TIMER)
    wave_countdown(game, opening, 1, first.key, balance.preparation_seconds)
    game.set_value(opening, "game.wave_display", 0)
    for number, wave in enumerate(later, 2):
        trigger = game.trigger(f"game.wave.{number}.warning", looping=False)
        game.value(trigger, "game.phase", State.PREPARATION)
        game.value(trigger, "game.wave", number - 2)
        wave_countdown(game, trigger, number, wave.key, balance.intermission_seconds)


def game_status(game: Game, balance: Balance) -> None:
    """Two lines share the wave number and countdown: the wait for the next wave, shown from
    the start, and the wave that is spawning. The wave triggers switch between them."""
    wave = game.names.resolve("variable", "game.display_wave")
    countdown = game.names.resolve("variable", "game.countdown")
    goal = (
        f"Survive {len(balance.waves)} scheduled waves. Endless runs and sudden death "
        "continue past them."
    )
    objective(
        game,
        "game.status.next",
        f"Wave <Variable {wave}> arrives in <Variable {countdown}> s",
        f"{goal} The seconds until the next wave starts.",
        shown=True,
    )
    objective(
        game,
        "game.status.spawning",
        f"Wave <Variable {wave}>: <Variable {countdown}> s of spawning left",
        f"{goal} The seconds the wave's enemies keep spawning.",
    )


type Band = tuple[Rect, int]


def lane_rows(lane: EngineLane) -> tuple[Band, ...]:
    """The lane's path in three bands, each with the exit row its enemies walk to: enemies
    created side by side keep their files instead of converging on one tile."""
    x1, y1, x2, y2 = lane.path
    center = lane.center_y
    return (
        ((x1, y1, x2, center - 1), center - 1),
        ((x1, center, x2, center), center),
        ((x1, center + 1, x2, y2), center + 1),
    )


def walk_middle(lane: EngineLane) -> int:
    """The column halfway along the lane's path, where each band's search is centred."""
    x1, _, x2, _ = lane.path
    return (x1 + x2) // 2


def walk_radius(lane: EngineLane) -> int:
    """How far from a band's middle its search reaches: the path's whole length, no more."""
    x1, _, x2, _ = lane.path
    return (x2 - x1) // 2 + 1


def enemy_walk_rules(lanes: Sequence[EngineLane]) -> str:
    """AI rules that send the enemy's standing units in each lane band to the band's exit
    row. Online, a computer in a lane slot ignores the orders the native triggers give its
    units, while its own AI's orders reach them."""
    lines = [f"(defconst {name} {value})" for name, value in WALK_CONSTANTS.items()]
    for name, goal in (("band", BAND_GOAL), ("walk", WALK_GOAL)):
        lines.append(f"(defconst ancient-{name}-x {goal})")
        lines.append(f"(defconst ancient-{name}-y {goal + 1})")
    for lane in lanes:
        middle = walk_middle(lane)
        for (_, y1, _, y2), row in lane_rows(lane):
            lines += [
                "(defrule",
                "    (true)",
                "=>",
                f"    (set-goal ancient-band-x {middle})",
                f"    (set-goal ancient-band-y {row})",
                "    (up-full-reset-search)",
                "    (up-set-target-point ancient-band-x)",
                f"    (up-filter-distance c: -1 c: {walk_radius(lane)})",
                f"    (up-find-local c: all-units-class c: {WALK_SEARCH})",
                f"    (up-remove-objects search-local object-data-point-y < {y1})",
                f"    (up-remove-objects search-local object-data-point-y > {y2})",
                # From the tile before the exit on, the XS counts a unit as through.
                f"    (up-remove-objects search-local object-data-point-x > {lane.exit_x - 2})",
                "    (up-remove-objects search-local object-data-action == actionid-move)",
                f"    (set-goal ancient-walk-x {lane.exit_x})",
                f"    (set-goal ancient-walk-y {row})",
                "    (up-target-point ancient-walk-x action-move -1 stance-no-attack)",
                ")",
            ]
    return "\n".join(lines) + "\n"


def declare_results(game: Game) -> None:
    """A victory goes to the winning lane, a defeat to whichever number the enemy holds, and
    a fallen lane's player is declared defeated once the script marks the lane."""
    for winner in LANE_SLOTS:
        finish = game.trigger(f"game.result.p{winner}", looping=False)
        game.value(finish, "game.winner", winner)
        game.value(finish, "game.phase", State.VICTORY)
        effect(finish, "declare_victory", source_player=winner, enabled=1)
    for enemy in ENEMY_SLOTS:
        finish = game.trigger(f"game.result.e{enemy}", looping=False)
        game.value(finish, "game.winner", enemy)
        game.value(finish, "game.phase", State.DEFEAT)
        effect(finish, "declare_victory", source_player=enemy, enabled=1)
    for lane in LANE_SLOTS:
        fallen = game.trigger(f"game.defeat.p{lane}", looping=False)
        game.value(fallen, f"lane.p{lane}.fallen", 1)
        effect(fallen, "declare_victory", source_player=lane, enabled=0)
