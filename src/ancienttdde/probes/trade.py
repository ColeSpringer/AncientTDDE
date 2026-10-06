"""Stock trade between a P1 home and an allied or Gaia partner, with protected endpoints."""

from typing import Literal

from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

HOME_X, PARTNER_X = 8, 54
LAND_Y, WATER_Y = 12, 44
ATTACK_PAD = (8, 4)
CONTROL = (8, 22)

DEFINITION = ProbeDefinition(
    ProbeId.TRADE,
    "Allied stock trade and protected endpoints",
    f"P1 has one home market at {tile_text((HOME_X, LAND_Y))} and one home dock at "
    f"{tile_text((HOME_X, WATER_Y))}. Their allied P2 partners are at "
    f"{tile_text((PARTNER_X, LAND_Y))}/{tile_text((PARTNER_X, WATER_Y))}. "
    "One cart and one cog start trading after two seconds; gold starts at zero. "
    "Observe at least two full return trips before moving the control King from "
    f"{tile_text(CONTROL)} to {tile_text(ATTACK_PAD)} to start P8's attacks. "
    "Use trade-gaia.aoe2scenario for the separate Gaia comparison.",
    (
        ProbeCase(
            "trade.ally",
            "Watch both traders at P2; inspect their carried gold and home deposits.",
            "Both repeatedly pick up at P2 and return to their sole P1 home; gold rises.",
        ),
        ProbeCase(
            "trade.protection",
            f"After checking income, move the King to {tile_text(ATTACK_PAD)}; "
            "watch P8 attack the endpoints.",
            "Endpoints survive combat, remain usable, and traders can still be killed.",
        ),
    ),
)


GAIA_DEFINITION = ProbeDefinition(
    ProbeId.TRADE_GAIA,
    "Gaia stock trade compatibility",
    "The layout matches trade.aoe2scenario: one P1 market/dock at "
    f"{tile_text((HOME_X, LAND_Y))}/{tile_text((HOME_X, WATER_Y))} "
    f"and Gaia partners at {tile_text((PARTNER_X, LAND_Y))}/{tile_text((PARTNER_X, WATER_Y))}. "
    "Gaia endpoints have capture disabled. "
    "Inspect their owner before and after traders approach. Observe two full return "
    "trips if possible. A stopped trader with a Gaia-owned endpoint is a compatibility "
    "failure; an endpoint changing owner invalidates the ownership setup. "
    f"Keep the King away from {tile_text(ATTACK_PAD)} until the trade observations are complete.",
    (
        ProbeCase(
            "trade.gaia-land",
            f"Watch the cart at y={LAND_Y} and confirm its partner remains Gaia-owned.",
            "It completes repeat trips and deposits gold while the partner remains Gaia-owned; "
            "record a failure if Gaia stock trade is unsupported.",
        ),
        ProbeCase(
            "trade.gaia-water",
            f"Watch the cog at y={WATER_Y} and confirm its partner remains Gaia-owned.",
            "It completes repeat trips and deposits gold while the partner remains Gaia-owned; "
            "record a failure if Gaia stock trade is unsupported.",
        ),
    ),
)


def trade_routes(arena: Arena, init: TriggerHandle, partner_player: Literal[0, 2]) -> None:
    arena.terrain((0, 30, 63, 63), 1)
    endpoints: list[int] = []
    start = arena.trigger("trade.start", looping=False)
    condition(start, "timer", timer=2)
    partner_name = "Gaia" if partner_player == 0 else "P2"
    for kind, trader, y in (("market", "cart", LAND_Y), ("dock", "cog", WATER_Y)):
        key = f"trade.{trader}"
        endpoints.append(arena.unit(f"{key}.home", kind, 1, HOME_X, y, f"P1 home {kind}"))
        partner = arena.unit(
            f"{key}.partner",
            kind,
            partner_player,
            PARTNER_X,
            y,
            f"{partner_name} partner {kind}",
            capture_flag=CaptureFlag.NEVER,
        )
        endpoints.append(partner)
        unit = arena.unit(f"{key}.trader", trader, 1, 14, y)
        effect(
            start,
            "task_object",
            source_player=1,
            selected_object_ids=[unit],
            location_object_reference=partner,
            action_type=ActionType.DEFAULT,
        )
    arena.protect(init, endpoints)
    pad = arena.pad("trade.attack.pad", *ATTACK_PAD, "Start endpoint attack test")
    arena.unit("trade.control", "king", 1, *CONTROL, "Endpoint attack control")
    attack = arena.trigger("trade.attack.endpoints", looping=False)
    arena.on_pad(attack, pad)
    for kind, y, target in (
        ("scout", LAND_Y, "trade.cart.home"),
        ("galley", WATER_Y, "trade.cog.home"),
    ):
        attacker = arena.unit(f"trade.attack.{kind}", kind, 8, 18, y)
        effect(
            init,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[attacker],
            attack_stance=AttackStance.NO_ATTACK_STANCE,
        )
        effect(
            attack,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[attacker],
            attack_stance=AttackStance.STAND_GROUND,
        )
        effect(
            attack,
            "task_object",
            source_player=8,
            selected_object_ids=[attacker],
            location_object_reference=arena.names.resolve("object", target),
        )
    effect(attack, "send_chat", source_player=1, message="Endpoint attack test started.")


def build(arena: Arena, init: TriggerHandle) -> None:
    trade_routes(arena, init, 2)


def build_gaia(arena: Arena, init: TriggerHandle) -> None:
    trade_routes(arena, init, 0)
