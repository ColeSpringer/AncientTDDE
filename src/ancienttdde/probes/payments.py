"""Exact King payments: an open shop pad takes only its price; a closed pad takes nothing."""

from AoE2ScenarioParser.datasets.trigger_lists.attribute import Attribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

OPEN_PAD = (10, 10)
CLOSED_PAD = (22, 10)

DEFINITION = ProbeDefinition(
    ProbeId.PAYMENTS,
    "Exact King payments",
    f"Move Kings onto the marked shop pad {tile_text(OPEN_PAD)}. Price: 3 Kings; reward: 100 gold. "
    f"The pad at {tile_text(CLOSED_PAD)} is closed. Spare Kings wait south of the pads. "
    "Restart the scenario for each payment comparison; wait two game-seconds after moving.",
    (
        ProbeCase(
            "payments.exact",
            "Move exactly 3 Kings onto the open pad.",
            "3 Kings disappear and gold increases by exactly 100.",
        ),
        ProbeCase(
            "payments.excess",
            "Move 5 Kings onto the open pad.",
            "Exactly 3 disappear, 2 remain, and gold increases by 100.",
        ),
        ProbeCase(
            "payments.repeat",
            "Move 6 Kings onto the open pad and wait 3 seconds.",
            "Two separate purchases consume 6 Kings and grant 200 gold.",
        ),
        ProbeCase(
            "payments.insufficient",
            "Move only 2 Kings onto the open pad.",
            "Both remain and no gold is awarded.",
        ),
        ProbeCase(
            "payments.rejected",
            "Move 3 Kings onto the closed pad.",
            "All 3 remain, no gold is awarded, and rejection feedback appears.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    pad = arena.pad("shop.open", *OPEN_PAD, "3 Kings = 100 gold")
    closed = arena.pad("shop.closed", *CLOSED_PAD, "Closed: payment is never consumed")
    arena.kings("payment", 1, 18, 8, 20)
    purchase = arena.trigger("shop.purchase", looping=True)
    condition(purchase, "timer", timer=1)
    arena.on_pad(purchase, pad, price=3)
    arena.pay(purchase, pad, 1, 3)
    effect(
        purchase,
        "modify_resource",
        source_player=1,
        tribute_list=Attribute.GOLD_STORAGE,
        quantity=100,
        operation=Operation.ADD,
    )
    effect(purchase, "send_chat", source_player=1, message="Purchase: 3 Kings consumed; +100 gold.")
    rejected = arena.trigger("shop.rejected", looping=True)
    condition(rejected, "timer", timer=5)
    arena.on_pad(rejected, closed)
    effect(rejected, "send_chat", source_player=1, message="Closed shop: no Kings consumed.")
