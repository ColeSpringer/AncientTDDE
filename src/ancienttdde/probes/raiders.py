"""Raider purchases with a living cap, combat against hostile traders, and containment."""

from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

LAND_PAD_X, NAVAL_PAD_X, PAD_Y = 8, 18, 27
SPAWN_X, LAND_SPAWN_Y, NAVAL_SPAWN_Y = 18, 16, 50

DEFINITION = ProbeDefinition(
    ProbeId.RAIDERS,
    "Raider combat and containment",
    f"Move Kings to {tile_text((LAND_PAD_X, PAD_Y))} for a land scout or "
    f"{tile_text((NAVAL_PAD_X, PAD_Y))} for a naval galley. "
    "Each costs 3 Kings and has a living cap of 2. Land raiders appear inside "
    f"the blocker enclosure at {tile_text((SPAWN_X, LAND_SPAWN_Y))}; ships appear at "
    f"{tile_text((SPAWN_X, NAVAL_SPAWN_Y))} in the southern basin. "
    "A blocked spawn keeps your Kings: move the previous raider away to retry. "
    "Hostile traders and raiders belong to player 8. Your market/dock can train "
    "replacement stock traders with the supplied resources.",
    (
        ProbeCase(
            "raiders.control",
            "Buy both raiders and attack hostile traders and raiders.",
            "Units belong to you, accept normal commands, and damage vulnerable units.",
        ),
        ProbeCase(
            "raiders.containment",
            "Order raiders toward shop Kings and across arena boundaries.",
            "Scouts stay inside the land enclosure; galleys stay in the water basin.",
        ),
        ProbeCase(
            "raiders.cap",
            "For each type, buy one and leave it on its spawn. Put 3 more Kings on "
            "its pad, wait, then move the first raider away. After the second appears, "
            "move it away and put 3 more Kings on the pad.",
            "The blocked second purchase keeps all 3 Kings until the spawn clears. "
            "Then exactly 3 are consumed for the second raider. With both alive, "
            "no third raider appears and all 3 payment Kings remain.",
        ),
        ProbeCase(
            "raiders.replacement",
            "Lose a raider, buy another, then replace a killed trader.",
            "A freed living-cap slot permits one purchase; new cart/cog can trade normally.",
        ),
        ProbeCase(
            "raiders.protection",
            "Order attacks on hostile markets and docks.",
            "Protected endpoints survive while traders remain vulnerable.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    arena.resources(init, 10000)
    arena.research(init, "FEUDAL_AGE")
    arena.terrain((0, 34, 63, 60), 1)
    # A closed stock-blocker ring keeps land combat separate from the shop controls.
    perimeter = {(x, y) for x in range(4, 60) for y in (4, 23)} | {
        (x, y) for y in range(5, 23) for x in (4, 59)
    }
    for x, y in sorted(perimeter):
        arena.unit(f"raider.boundary.{x}.{y}", "blocker", 0, x, y)
    endpoints: list[int] = []
    start = arena.trigger("raider.trade.start", looping=False)
    condition(start, "timer", timer=2)
    for kind, trader, y in (("market", "cart", 10), ("dock", "cog", 44)):
        home = arena.unit(f"raider.{trader}.home", kind, 1, 8, y)
        partner = arena.unit(f"raider.{trader}.partner", kind, 8, 54, y)
        endpoints.extend([home, partner])
        for player, x, target in ((1, 14, partner), (8, 48, home)):
            unit = arena.unit(f"raider.{trader}.p{player}", trader, player, x, y)
            effect(
                start,
                "task_object",
                source_player=player,
                selected_object_ids=[unit],
                location_object_reference=target,
            )
    arena.protect(init, endpoints)
    arena.kings("raider.payment", 1, 24, 30, 27)
    for name, kind, pad_x, spawn_y in (
        ("land", "scout", LAND_PAD_X, LAND_SPAWN_Y),
        ("naval", "galley", NAVAL_PAD_X, NAVAL_SPAWN_Y),
    ):
        pad = arena.pad(f"raider.{name}.pad", pad_x, PAD_Y, f"{name}: 3 Kings; living cap 2")
        enemy = arena.unit(f"raider.{name}.enemy", kind, 8, 42, spawn_y)
        effect(
            init,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[enemy],
            attack_stance=AttackStance.STAND_GROUND,
        )
        purchase = arena.trigger(f"raider.{name}.purchase", looping=True)
        condition(purchase, "timer", timer=1)
        arena.on_pad(purchase, pad, price=3)
        x1, y1, x2, y2 = pad
        effect(
            purchase,
            "script_call",
            message=(
                f"void ancientBuy{name.title()}Raider() {{ "
                f"ancientPurchaseRaider(1, {arena.stock(kind)}, {arena.stock('king')}, 2, "
                f'{x1}, {y1}, {x2 + 1}, {y2 + 1}, {SPAWN_X + 0.5}, {spawn_y + 0.5}, "{name}"); }}'
            ),
        )
