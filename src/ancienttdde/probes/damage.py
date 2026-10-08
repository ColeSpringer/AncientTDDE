"""Tower damage against the scheduled enemies, before and after an attack purchase, and
what two trebuchets do to a Keep in a minute."""

from AoE2ScenarioParser.datasets.trigger_lists.attack_stance import AttackStance
from AoE2ScenarioParser.datasets.trigger_lists.object_attribute import ObjectAttribute

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, effect

TOWER_Y, ENEMY_Y = 10, 14
# One tower of each kind, spaced so that each sees only the enemy spot below it.
TOWERS = (
    ("watch-tower", 8),
    ("guard-tower", 20),
    ("keep", 32),
    ("bombard-tower", 44),
    ("accursed-tower", 58),
)
# The game's Accursed Towers carry this much extra pierce attack.
ACCURSED_PIERCE = 232
# Enemies at the scheduled waves' Normal hit points: Militia, Knights and War Elephants.
ENEMIES = (
    ("militia", "militia", 70),
    ("knight", "knight", 440),
    ("elephant", "war-elephant", 230),
)
ATTACK_BONUS = 100
PADS = {
    "militia": (4, 30),
    "knight": (14, 30),
    "elephant": (24, 30),
    "attack": (34, 30),
    "siege": (44, 30),
}
KINGS = (4, 22)
SIEGE_KEEP = (22, 60)
TREBUCHETS = ((20, 50), (26, 50))

DEFINITION = ProbeDefinition(
    ProbeId.TOWER_DAMAGE,
    "Tower damage and siege damage",
    "P1 owns a Watch Tower, Guard Tower, Keep, Bombard Tower and Accursed Tower along "
    f"y={TOWER_Y}, each with its own target spot four tiles south. A King on the militia, knight "
    "or elephant "
    "pad places one standing enemy of that kind, at its scheduled hit points, below every tower; "
    f"each King placed is another set. A King on {tile_text(PADS['attack'])} adds "
    f"+{ATTACK_BONUS} attack to the four stock towers once, and a King on "
    f"{tile_text(PADS['siege'])} places two P8 trebuchets that cannot move within range of the "
    f"Keep at {tile_text(SIEGE_KEEP)}. Kings wait at {tile_text(KINGS)}. Time with the game clock.",
    (
        ProbeCase(
            "tower-damage.militia",
            f"Put one King on {tile_text(PADS['militia'])} and time each tower.",
            "Record the seconds each tower takes to kill its militia (220 HP, 1 pierce armor).",
        ),
        ProbeCase(
            "tower-damage.knight",
            f"Put one King on {tile_text(PADS['knight'])} and time each tower.",
            "Record the seconds each tower takes to kill its knight (1100 HP, 2 pierce armor).",
        ),
        ProbeCase(
            "tower-damage.elephant",
            f"Put one King on {tile_text(PADS['elephant'])} and time each tower.",
            "Record the seconds each tower takes to kill its elephant (2500 HP, 2 pierce armor).",
        ),
        ProbeCase(
            "tower-damage.attack",
            f"Put a King on {tile_text(PADS['attack'])}, then repeat the knight case.",
            "Each stock tower shows +100 attack and kills its knight correspondingly faster; "
            "the Accursed Tower is unchanged.",
        ),
        ProbeCase(
            "tower-damage.siege",
            f"Put a King on {tile_text(PADS['siege'])} and watch the Keep for a minute.",
            "Record the hits landed, the hit points lost per hit and when the Keep falls.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    for kind, x in TOWERS:
        arena.unit(f"damage.tower.{kind}", kind, 1, x, TOWER_Y, f"P1 {kind}")
    arena.attack_bonus(init, 1, (arena.stock("accursed-tower"),), ACCURSED_PIERCE)
    for _, kind, hit_points in ENEMIES:
        arena.set_attribute(init, 8, arena.stock(kind), ObjectAttribute.HIT_POINTS, hit_points)
    for kind in ("trebuchet", "packed-trebuchet"):
        arena.set_attribute(init, 8, arena.stock(kind), ObjectAttribute.MOVEMENT_SPEED, 0)
    arena.unit("damage.siege.keep", "keep", 1, *SIEGE_KEEP, "P1 Keep: the siege target")
    arena.kings("damage.payment", 1, 24, *KINGS)
    for name, kind, hit_points in ENEMIES:
        pad = arena.pad(f"damage.{name}.pad", *PADS[name], f"1 King: a {name} below every tower")
        spawn = arena.trigger(f"damage.{name}", looping=True)
        arena.on_pad(spawn, pad)
        arena.pay(spawn, pad, 1, 1)
        for _, x in TOWERS:
            effect(
                spawn,
                "create_object",
                source_player=8,
                object_list_unit_id=arena.stock(kind),
                location_x=x,
                location_y=ENEMY_Y,
            )
        effect(
            spawn,
            "change_object_stance",
            source_player=8,
            object_list_unit_id=arena.stock(kind),
            attack_stance=AttackStance.STAND_GROUND,
        )
        effect(
            spawn,
            "send_chat",
            source_player=1,
            message=f"One {name} with {hit_points} hit points stands below every tower.",
        )
    attack = arena.trigger("damage.attack", looping=False)
    arena.on_pad(
        attack, arena.pad("damage.attack.pad", *PADS["attack"], f"+{ATTACK_BONUS} tower attack")
    )
    arena.attack_bonus(
        attack,
        1,
        tuple(arena.stock(kind) for kind, _ in TOWERS if kind != "accursed-tower"),
        ATTACK_BONUS,
    )
    effect(
        attack, "send_chat", source_player=1, message=f"+{ATTACK_BONUS} attack on the four towers."
    )
    siege = arena.trigger("damage.siege", looping=False)
    arena.on_pad(siege, arena.pad("damage.siege.pad", *PADS["siege"], "Two trebuchets at the Keep"))
    for x, y in TREBUCHETS:
        effect(
            siege,
            "create_object",
            source_player=8,
            object_list_unit_id=arena.stock("trebuchet"),
            location_x=x,
            location_y=y,
        )
    effect(siege, "send_chat", source_player=1, message="Two trebuchets fire at the Keep.")
