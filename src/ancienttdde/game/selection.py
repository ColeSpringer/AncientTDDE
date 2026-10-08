"""Native triggers that tell each lane which control below the shop its player selects."""

from collections.abc import Mapping
from typing import cast

from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison

from ancienttdde.common.data import object_value
from ancienttdde.game.config import Balance
from ancienttdde.game.controls import (
    CONTROLS,
    MODES,
    ControlGroup,
    control_code,
    control_labels,
    controls,
)
from ancienttdde.game.objectives import listed
from ancienttdde.game.sites import numbers
from ancienttdde.game.triggers import Game
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect


def control_points(anchors: Mapping[str, object]) -> tuple[tuple[float, float], ...]:
    """Where each control stands, in code order: the run options, then the practice controls."""
    points: list[tuple[float, float]] = []
    for group in ("run", "practice"):
        key = f"controls.{group}"
        found = object_value(anchors.get(key), key).get("points")
        items = cast(list[object], found) if isinstance(found, list) else []
        points.extend((x, y) for x, y in (numbers(item, key, 2) for item in items))
    if len(points) != len(CONTROLS):
        raise ValueError(f"The map places {len(points)} controls for {len(CONTROLS)}")
    return tuple(points)


def place_controls(game: Game, anchors: Mapping[str, object], balance: Balance) -> None:
    """Gaia Outposts below the shop stand for the controls; players select them. Each carries
    its short label as a caption, which goes with the Outpost."""
    labels = control_labels(balance)
    for control, (x, y) in zip(CONTROLS, control_points(anchors), strict=True):
        outpost = game.scenario.unit_manager.add_unit(
            player=0,
            unit_const=game.stock("outpost"),
            x=x,
            y=y,
            caption_string=labels[control.key],
        )
        game.names.register("object", f"control.{control.key}", outpost.reference_id)


def chooser_view(game: Game, anchors: Mapping[str, object]) -> None:
    """The chooser's view starts on the run options, whichever lane the chooser is. The role
    passes to the next lane when the chooser falls, so only an open choice moves a view."""
    points = control_points(anchors)[: len(controls("run"))]
    x = int(sum(x for x, _ in points) / len(points))
    y = int(sum(y for _, y in points) / len(points))
    for player in range(1, 8):
        trigger = game.trigger(f"game.view.p{player}", looping=False)
        game.value(trigger, "game.chooser", player)
        game.value(trigger, "game.locked", 0)
        effect(trigger, "change_view", source_player=player, location_x=x, location_y=y, scroll=0)


def options_objectives(game: Game, balance: Balance) -> None:
    """On-screen lines naming the controls left to right, listed while they stand: an
    objective completes, and leaves the screen, once its conditions hold."""
    labels = control_labels(balance)
    run = ", ".join(labels[c.key] for c in controls("run"))
    practice = ", ".join(labels[c.key] for c in controls("practice"))
    options = listed(
        game,
        "game.objective.options",
        f"Run options below the shop, left to right: {run}",
        "The first human lane selects one; Standard and PvP off are taken after "
        f"{balance.choice_seconds} game seconds.",
        shown=True,
    )
    game.value(options, "game.locked", 1)
    helpers = listed(
        game,
        "game.objective.practice_controls",
        f"Practice controls (solo Practice runs) to their right: {practice}",
        "They work in a Practice run and leave with the options otherwise.",
        shown=True,
    )
    game.value(helpers, "game.locked", 1)
    condition(
        helpers,
        "variable_value",
        variable=game.names.resolve("variable", "game.mode"),
        quantity=MODES.index("practice"),
        comparison=Comparison.EQUAL,
        inverted=1,
    )


def lane_controls(game: Game, player: int) -> None:
    """Each new selection of a control records its code in the lane's control field once.

    The XS acts on the code and clears it. The held field keeps the control still selected, so
    holding it records nothing more, and selecting it again after anything else records it
    again, however quickly that happens.
    """
    prefix = f"lane.p{player}"
    held = game.names.resolve("variable", f"{prefix}.control_held")
    outposts = {c.key: game.names.resolve("object", f"control.{c.key}") for c in CONTROLS}
    for control in CONTROLS:
        code = control_code(control.key)
        trigger = game.trigger(f"{prefix}.control.{control.key}", looping=True)
        game.value(trigger, f"{prefix}.active", 1)
        # Run options act until they are fixed, practice controls only in Practice runs.
        if control.group == "run":
            game.value(trigger, "game.locked", 0)
        else:
            game.value(trigger, "game.mode", MODES.index("practice"))
        condition(
            trigger,
            "variable_value",
            variable=held,
            quantity=code,
            comparison=Comparison.EQUAL,
            inverted=1,
        )
        condition(
            trigger,
            "object_selected_multiplayer",
            unit_object=outposts[control.key],
            source_player=player,
        )
        game.set_value(trigger, f"{prefix}.control_held", code)
        game.set_value(trigger, f"{prefix}.control", code)
    none = game.trigger(f"{prefix}.control.none", looping=True)
    game.value(none, f"{prefix}.active", 1)
    game.value(none, f"{prefix}.control_held", 1, Comparison.LARGER_OR_EQUAL)
    for control in CONTROLS:
        condition(
            none,
            "object_selected_multiplayer",
            unit_object=outposts[control.key],
            source_player=player,
            inverted=1,
        )
    game.set_value(none, f"{prefix}.control_held", 0)


def retire_controls(game: Game) -> None:
    """Once the options are fixed the run options go, and so do the practice controls unless
    the run is a Practice run."""
    run = game.trigger("game.controls.run.remove", looping=False)
    game.value(run, "game.locked", 1)
    practice = game.trigger("game.controls.practice.remove", looping=False)
    game.value(practice, "game.locked", 1)
    game.value(practice, "game.mode", MODES.index("practice"), Comparison.LESS)
    retired: tuple[tuple[TriggerHandle, ControlGroup], ...] = ((run, "run"), (practice, "practice"))
    for trigger, group in retired:
        effect(
            trigger,
            "remove_object",
            source_player=0,
            selected_object_ids=[
                game.names.resolve("object", f"control.{c.key}") for c in controls(group)
            ],
        )
