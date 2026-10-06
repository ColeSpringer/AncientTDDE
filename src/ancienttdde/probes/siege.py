"""Exclusive temporary siege: one owner at a time, warnings, expiry and cooldowns."""

from AoE2ScenarioParser.datasets.trigger_lists.comparison import Comparison
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute
from AoE2ScenarioParser.datasets.trigger_lists.operation import Operation
from AoE2ScenarioParser.datasets.trigger_lists.time_unit import TimeUnit

from ancienttdde.models import Rect
from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, condition, effect

P1_BASE_X, P8_BASE_X, PAD_Y = 8, 48, 8
RESERVE = (28, 1)
P1_ELIMINATE, P8_ELIMINATE = (8, 14), (16, 14)
SIEGE_WARNING, SIEGE_ACTIVE = 1, 2
SIEGE_WARNING_SECONDS, SIEGE_ACTIVE_SECONDS = 10, 60
SIEGE_SHARED_COOLDOWN, SIEGE_BUYER_COOLDOWN = 60, 120

DEFINITION = ProbeDefinition(
    ProbeId.SIEGE,
    "Exclusive temporary siege",
    "P1 and P8 each start with Kings on their purchase pads "
    f"{tile_text((P1_BASE_X, PAD_Y))}/{tile_text((P8_BASE_X, PAD_Y))}. "
    "One surviving rival makes the price 25 Kings. P1 claims first; P8 retries "
    "automatically, and P8's Kings are held in place because the engine would "
    "otherwise walk computer-owned Kings into the Keep. Warning: 10 seconds, "
    "activity: 60 seconds, shared cooldown: 60 seconds, buyer cooldown: 120 "
    "seconds after cleanup; both cooldowns are displayed, and a purchase needs "
    "both at zero. Two deployed trebuchets appear on islets within range of the "
    "rival's Keep and can fire at once; they cannot move, so packing one leaves "
    "it packed in place. "
    f"Spare P1 Kings wait at {tile_text(RESERVE)}; move at least 25 onto your purchase pad to "
    "exercise buyer cooldown and no-rival rejection with sufficient payment. "
    f"Move the separate control King to {tile_text(P1_ELIMINATE)} to remove P1's life marker and "
    f"simulate owner elimination, or {tile_text(P8_ELIMINATE)} to remove P8's life marker. "
    "Restart for expiry and elimination comparisons.",
    (
        ProbeCase(
            "siege.exclusive",
            "Observe both requests immediately after start.",
            "Only P1 pays 25 Kings; P8's 25 Kings remain during ownership/cooldown.",
        ),
        ProbeCase(
            "siege.targeting",
            "After the warning, target the rival towers with both trebuchets.",
            "Exactly two deployed trebuchets appear on rival islets, hit chosen towers "
            "and cannot leave.",
        ),
        ProbeCase(
            "siege.expiry",
            "Pack one trebuchet and leave the other unpacked until expiry.",
            "Both forms disappear 60 game-seconds after activation.",
        ),
        ProbeCase(
            "siege.cooldown",
            "Wait through expiry and the shared cooldown.",
            "P8 can claim after shared cooldown; P1 cannot bypass its longer buyer cooldown.",
        ),
        ProbeCase(
            "siege.repeat",
            "Once both displayed cooldowns read zero, move 25 spare Kings onto P1's pad.",
            "A second purchase consumes 25 Kings, runs a full 10-second warning and "
            "two trebuchets stay for 60 seconds.",
        ),
        ProbeCase(
            "siege.elimination",
            "During warning/activity, remove the current owner's life marker.",
            "All owner siege disappears, pending spawn is canceled and cooldown starts.",
        ),
        ProbeCase(
            "siege.no-rival",
            "Remove P8's life marker before requesting another P1 purchase.",
            "A purchase without a surviving rival does not consume Kings.",
        ),
        ProbeCase(
            "siege.save-load",
            "Save during warning and activity, reload and wait for expiry.",
            "Ownership, timers and payment persist without duplicate siege or reset duration.",
        ),
    ),
)


def countdown(trigger: TriggerHandle, seconds: int, message: str, slot: int) -> None:
    effect(
        trigger,
        "display_timer",
        display_time=seconds,
        time_unit=TimeUnit.SECONDS,
        message=message,
        reset_timer=1,
        timer=slot,
    )


def build(arena: Arena, init: TriggerHandle) -> None:
    arena.terrain((0, 19, 63, 25), 1)
    # Every stage trigger stays enabled and looping and is gated by these variables. The
    # phase and elapsed seconds describe the current owner's stage; the cooldowns hold the
    # remaining seconds and are counted down by one-second clocks.
    for key in (
        "siege.owner",
        "siege.phase",
        "siege.elapsed",
        "siege.shared.cooldown",
        "siege.p1.cooldown",
        "siege.p8.cooldown",
    ):
        arena.variable(key)
        arena.set_value(init, key, 0)
    arena.clock("siege.clock", "siege.elapsed", Operation.ADD, while_positive="siege.phase")
    for key in ("siege.shared", "siege.p1", "siege.p8"):
        arena.clock(
            f"{key}.clock", f"{key}.cooldown", Operation.SUBTRACT, while_positive=f"{key}.cooldown"
        )
    pads: dict[int, Rect] = {}
    positions = {1: (42, 46), 8: (18, 22)}
    lives: list[int] = []
    for player, x in ((1, P1_BASE_X), (8, P8_BASE_X)):
        lives.append(arena.unit(f"siege.p{player}.life", "life", player, x, 28))
        arena.unit(f"siege.p{player}.tower", "keep", player, x + 6, 29)
        pads[player] = arena.pad(f"siege.p{player}.pad", x, PAD_Y, f"P{player}: 25 Kings per siege")
        arena.kings(f"siege.p{player}.payment", player, 30 if player == 1 else 25, x, PAD_Y)
        for islet_x in positions[player]:
            arena.terrain((islet_x - 1, 22, islet_x + 1, 24), 0)
        for kind in ("trebuchet", "packed-trebuchet"):
            effect(
                init,
                "modify_attribute",
                source_player=player,
                object_list_unit_id=arena.stock(kind),
                object_attributes=ObjectAttribute.MOVEMENT_SPEED,
                quantity=0,
                operation=Operation.SET,
            )
    # The engine walks a computer player's Kings into any garrisonable building it owns (here
    # the Keep) regardless of the AI script, which would carry P8's payment off its pad.
    effect(
        init,
        "modify_attribute",
        source_player=8,
        object_list_unit_id=arena.stock("king"),
        object_attributes=ObjectAttribute.MOVEMENT_SPEED,
        quantity=0,
        operation=Operation.SET,
    )
    arena.protect(init, lives)
    arena.unit("siege.control", "king", 1, 28, 8)
    arena.kings("siege.p1.reserve", 1, 30, *RESERVE)
    for player, position in ((1, P1_ELIMINATE), (8, P8_ELIMINATE)):
        pad = arena.pad(
            f"siege.p{player}.eliminate.pad", *position, f"Remove P{player} life marker"
        )
        control = arena.trigger(f"siege.p{player}.eliminate.control", looping=False)
        arena.on_pad(control, pad)
        effect(
            control,
            "remove_object",
            source_player=player,
            selected_object_ids=[arena.names.resolve("object", f"siege.p{player}.life")],
        )
    for player in (1, 8):
        key = f"siege.p{player}"
        rival = 8 if player == 1 else 1
        purchase = arena.trigger(f"{key}.purchase", looping=True)
        condition(purchase, "timer", timer=1)
        arena.on_pad(purchase, pads[player], player=player, price=25)
        arena.value(purchase, "siege.owner", 0)
        arena.value(purchase, "siege.shared.cooldown", 0)
        arena.value(purchase, f"{key}.cooldown", 0)
        for alive in (player, rival):
            condition(
                purchase,
                "own_objects",
                source_player=alive,
                object_list=arena.stock("life"),
                quantity=1,
            )
        # Claim the shared lock before payment so a later request sees an occupied transaction.
        arena.set_value(purchase, "siege.owner", player)
        arena.set_value(purchase, "siege.phase", SIEGE_WARNING)
        arena.set_value(purchase, "siege.elapsed", 0)
        arena.pay(purchase, pads[player], player, 25)
        effect(
            purchase,
            "send_chat",
            source_player=1,
            message=f"P{player} owns siege. 10-second warning; other requests retain Kings.",
        )
        countdown(purchase, SIEGE_WARNING_SECONDS, f"P{player} siege warning: %d", 0)
        warning = arena.trigger(f"{key}.warning", looping=True)
        arena.value(warning, "siege.owner", player)
        arena.value(warning, "siege.phase", SIEGE_WARNING)
        arena.value(warning, "siege.elapsed", SIEGE_WARNING_SECONDS, Comparison.LARGER_OR_EQUAL)
        for x in positions[player]:
            # Unit 42 is the deployed Trebuchet, ready to fire; 331 is the packed form.
            effect(
                warning,
                "create_object",
                source_player=player,
                object_list_unit_id=arena.stock("trebuchet"),
                location_x=x,
                location_y=23,
            )
        arena.set_value(warning, "siege.phase", SIEGE_ACTIVE)
        arena.set_value(warning, "siege.elapsed", 0)
        countdown(warning, SIEGE_ACTIVE_SECONDS, f"P{player} siege active: %d", 0)
        for ending in ("expiry", "eliminated", "defeated"):
            cleanup = arena.trigger(f"{key}.{ending}", looping=True)
            arena.value(cleanup, "siege.owner", player)
            if ending == "expiry":
                arena.value(cleanup, "siege.phase", SIEGE_ACTIVE)
                arena.value(
                    cleanup, "siege.elapsed", SIEGE_ACTIVE_SECONDS, Comparison.LARGER_OR_EQUAL
                )
            elif ending == "eliminated":
                arena.at_most(cleanup, player, "life", 0)
            else:
                condition(cleanup, "player_defeated", source_player=player)
            for kind in ("trebuchet", "packed-trebuchet"):
                effect(
                    cleanup,
                    "remove_object",
                    source_player=player,
                    object_list_unit_id=arena.stock(kind),
                )
            arena.set_value(cleanup, "siege.owner", 0)
            arena.set_value(cleanup, "siege.phase", 0)
            arena.set_value(cleanup, "siege.shared.cooldown", SIEGE_SHARED_COOLDOWN)
            arena.set_value(cleanup, f"{key}.cooldown", SIEGE_BUYER_COOLDOWN)
            effect(
                cleanup,
                "send_chat",
                source_player=1,
                message=f"P{player} siege removed; shared cooldown 60s, buyer cooldown 120s.",
            )
            countdown(cleanup, SIEGE_SHARED_COOLDOWN, "Shared siege cooldown: %d", 0)
            countdown(cleanup, SIEGE_BUYER_COOLDOWN, f"P{player} buyer cooldown: %d", 1)
