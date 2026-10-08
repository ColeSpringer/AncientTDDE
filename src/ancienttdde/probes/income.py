"""Trade income by route length, and how fast a raider kills a trader."""

from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

HOME_X = 8
# Partner markets and docks stand this far east of the home ones: a short and a long route.
ROUTES = (("short", 28), ("long", 54))
LAND_Y = (12, 22)
WATER_Y = (36, 48)
CART_PAD, COG_PAD = (20, 24), (32, 24)
KINGS = (44, 24)
# Raider and prey positions: the light cavalry on land, the fire galley in the water.
RAIDS = (("cart", "light-cavalry", "cart", 48, 4), ("cog", "fire-galley", "cog", 50, 60))

DEFINITION = ProbeDefinition(
    ProbeId.TRADE_INCOME,
    "Trade income and raider kill times",
    f"P1 has two home markets and two home docks at x={HOME_X} with Gaia partners "
    f"{ROUTES[0][1] - HOME_X} and {ROUTES[1][1] - HOME_X} tiles east of them. One cart and one "
    "cog trade on each route from two seconds in; gold starts at zero, so each return shows "
    "the trip's gold. Caravan is not researched: trips take a fifth longer than in the game. "
    f"A P1 light cavalry waits beside a P8 trade cart in the north-east corner and a P1 fire "
    f"galley beside a P8 trade cog in the south-east; a King on {tile_text(CART_PAD)} or "
    f"{tile_text(COG_PAD)} orders the attack. Kings wait at {tile_text(KINGS)}.",
    (
        ProbeCase(
            "trade-income.cart-short",
            f"Watch the cart on the {ROUTES[0][1] - HOME_X}-tile land route for three returns.",
            "Record the gold each return adds and the seconds per round trip.",
        ),
        ProbeCase(
            "trade-income.cart-long",
            f"Watch the cart on the {ROUTES[1][1] - HOME_X}-tile land route for three returns.",
            "Record the gold each return adds and the seconds per round trip.",
        ),
        ProbeCase(
            "trade-income.cog-short",
            f"Watch the cog on the {ROUTES[0][1] - HOME_X}-tile water route for three returns.",
            "Record the gold each return adds and the seconds per round trip.",
        ),
        ProbeCase(
            "trade-income.cog-long",
            f"Watch the cog on the {ROUTES[1][1] - HOME_X}-tile water route for three returns.",
            "Record the gold each return adds and the seconds per round trip.",
        ),
        ProbeCase(
            "trade-income.raid-cart",
            f"Put a King on {tile_text(CART_PAD)} and time the light cavalry against the cart.",
            "Record the seconds from the first hit to the cart's death.",
        ),
        ProbeCase(
            "trade-income.raid-cog",
            f"Put a King on {tile_text(COG_PAD)} and time the fire galley against the cog.",
            "Record the seconds from the first hit to the cog's death.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    arena.terrain((0, 30, 63, 63), 1)
    endpoints: list[int] = []
    start = arena.trigger("income.start", looping=False)
    condition(start, "timer", timer=2)
    for kind, trader, rows in (("market", "cart", LAND_Y), ("dock", "cog", WATER_Y)):
        for (length, partner_x), y in zip(ROUTES, rows, strict=True):
            caption = f"Gaia partner {kind}, {partner_x - HOME_X} tiles from home"
            endpoints.extend(
                arena.trade_pair(
                    start,
                    f"income.{trader}.{length}",
                    kind,
                    trader,
                    HOME_X,
                    partner_x,
                    y,
                    0,
                    caption,
                )
            )
    # Trade units keep no player in the game, so P8's prey needs a counted, protected King.
    endpoints.append(arena.unit("income.keeper", "king", 8, 61, 16, "P8 marker: stays"))
    arena.protect(init, endpoints)
    arena.kings("income.payment", 1, 6, *KINGS)
    for name, raider, victim, x, y in RAIDS:
        attacker = arena.unit(f"income.raider.{name}", raider, 1, x, y)
        prey = arena.unit(f"income.prey.{name}", victim, 8, x + 6, y, f"P8 {name}: raid target")
        effect(
            init,
            "change_object_stance",
            source_player=8,
            selected_object_ids=[prey],
            attack_stance=AttackStance.NO_ATTACK_STANCE,
        )
        pad = arena.pad(
            f"income.raid.{name}.pad",
            *(CART_PAD if name == "cart" else COG_PAD),
            f"Raid the {name}",
        )
        raid = arena.trigger(f"income.raid.{name}", looping=False)
        arena.on_pad(raid, pad)
        effect(
            raid,
            "task_object",
            source_player=1,
            selected_object_ids=[attacker],
            location_object_reference=prey,
        )
        effect(raid, "send_chat", source_player=1, message=f"Raid on the {name} started.")
