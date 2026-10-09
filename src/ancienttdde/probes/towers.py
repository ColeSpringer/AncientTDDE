"""Tower bonus persistence: an attack bonus survives construction, upgrades and saves, and the
script's technology-style effect raises attack past the 255 a native effect stops at."""

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, effect

BONUS_PAD = (8, 8)
CASTLE_PAD = (16, 8)
IMPERIAL_PAD = (24, 8)
BEYOND_PAD = (8, 24)
ENCODING_PAD = (16, 24)
TOWN_CENTER = (24, 28)
# The arrow towers the game's script raises: Watch Tower, Guard Tower and Keep.
SCRIPT_TOWERS = (79, 234, 235)

DEFINITION = ProbeDefinition(
    ProbeId.TOWERS,
    "Tower bonus persistence",
    "Use a standard civilization with Guard Tower and Keep (Britons recommended). "
    "The game starts in Feudal Age. Move the control King to the bonus pad "
    f"{tile_text(BONUS_PAD)}, then build towers with the villagers. The pads at "
    f"{tile_text(CASTLE_PAD)} and {tile_text(IMPERIAL_PAD)} force "
    "Castle/Guard Tower and Imperial/Keep respectively. The script pad at "
    f"{tile_text(BEYOND_PAD)} adds Watch Tower attack the way the game's script does, and "
    f"the encoding pad at {tile_text(ENCODING_PAD)} tests how the script packs the attack "
    "class. Keep the control King alive. "
    f"The Town Center at {tile_text(TOWN_CENTER)}, two builders and scout are deliberate "
    "test fixtures.",
    (
        ProbeCase(
            "towers.existing",
            "Inspect the existing Watch Tower before/after the bonus pad.",
            "Its pierce attack increases by 4, exactly once.",
        ),
        ProbeCase(
            "towers.construction",
            "Build a new Watch Tower after buying the bonus.",
            "It has the same +4 attack adjustment as the existing tower.",
        ),
        ProbeCase(
            "towers.upgrades",
            "Use both age/upgrade pads, then build another tower.",
            "Existing and newly built Guard Towers/Keeps retain exactly +4 attack.",
        ),
        ProbeCase(
            "towers.scope",
            "Inspect the scout and Bombard Tower before/after the bonus.",
            "They receive no arrow-tower bonus; no unrelated class is modified.",
        ),
        ProbeCase(
            "towers.save-load",
            "Save after applying the bonus, reload and build another tower.",
            "The bonus persists without being added a second time.",
        ),
        ProbeCase(
            "towers.beyond-255",
            "After the +4 pad, move the King to the script pad and inspect the Watch Tower.",
            "The chat confirms the script pad ran, and the pierce attack reads 5+304: the script "
            "adds 255 then 45 and the total passes 255. Without the chat line the script did "
            "not run; record that instead of an attack result.",
        ),
        ProbeCase(
            "towers.encoding",
            "Move the King to the encoding pad and inspect the Watch Tower again.",
            "The chat confirms the encoding pad ran, and the attack does not change: DE packs "
            "the class with the amount as class * 256 + "
            "amount, as the game's script does. A rise of exactly 7 would mean the class sits "
            "in the upper 16 bits and the script must use that factor instead.",
        ),
        ProbeCase(
            "towers.beyond-persists",
            "After both script pads use the Castle Age pad, build a tower, save, reload.",
            "Existing and new Guard Towers show the same pierce bonus the Watch Tower showed, "
            "after the upgrade and after the reload.",
        ),
    ),
)


def build(arena: Arena, init: TriggerHandle) -> None:
    arena.resources(init, 10000)
    arena.research(init, "FEUDAL_AGE")
    arena.unit("tower.original", "watch-tower", 1, 32, 18)
    arena.unit("tower.comparison", "bombard-tower", 1, 38, 18)
    arena.unit("tower.scout", "scout", 1, 40, 22)
    arena.unit("tower.builder", "villager", 1, 28, 22)
    arena.unit("tower.builder.2", "villager", 1, 29, 22)
    arena.unit("tower.town", "town-center", 1, *TOWN_CENTER)
    arena.unit("tower.control", "king", 1, 8, 16)
    bonus_pad = arena.pad("tower.bonus.pad", *BONUS_PAD, "+4 arrow tower pierce attack")
    castle_pad = arena.pad("tower.castle.pad", *CASTLE_PAD, "Castle Age + Guard Tower")
    imperial_pad = arena.pad("tower.imperial.pad", *IMPERIAL_PAD, "Imperial Age + Keep")
    beyond_pad = arena.pad("tower.beyond.pad", *BEYOND_PAD, "Script: Watch Tower attack +300")
    encoding_pad = arena.pad("tower.encoding.pad", *ENCODING_PAD, "Script: attack class packing")
    bonus = arena.trigger("tower.bonus", looping=False)
    arena.on_pad(bonus, bonus_pad)
    # Modify type definitions so future construction and upgrades are part of the experiment.
    arena.tower_attack_bonus(bonus, 4)
    effect(
        bonus,
        "send_chat",
        source_player=1,
        message="Arrow tower definitions: +4 attack applied once.",
    )
    castle = arena.trigger("tower.castle", looping=False)
    arena.on_pad(castle, castle_pad)
    arena.research(castle, "CASTLE_AGE")
    arena.research(castle, "GUARD_TOWER")
    imperial = arena.trigger("tower.imperial", looping=False)
    arena.on_pad(imperial, imperial_pad)
    arena.research(imperial, "CASTLE_AGE")
    arena.research(imperial, "GUARD_TOWER")
    arena.research(imperial, "IMPERIAL_AGE")
    arena.research(imperial, "KEEP")
    # The game's script adds tower attack in steps of at most 255, each packed with the pierce
    # class (3) as class * 256 + amount, to every arrow tower definition, so upgrades keep it;
    # the value parameter is a float.
    beyond = arena.trigger("tower.beyond", looping=False)
    arena.on_pad(beyond, beyond_pad)
    steps = "".join(
        f"xsEffectAmount(cAddAttribute, {tower}, cAttack, {value}, 1); "
        for tower in SCRIPT_TOWERS
        for value in ("1023.0", "813.0")
    )
    ran = 'xsChatData("Script pad: +300 pierce attack sent to the arrow towers."); '
    effect(beyond, "script_call", message=f"void probeAttackBeyond() {{ {steps}{ran}}}")
    # The same class in the upper 16 bits: 3 * 65536 + 7.
    encoding = arena.trigger("tower.encoding", looping=False)
    arena.on_pad(encoding, encoding_pad)
    packed = "".join(
        f"xsEffectAmount(cAddAttribute, {tower}, cAttack, 196615.0, 1); " for tower in SCRIPT_TOWERS
    )
    ran = 'xsChatData("Encoding pad: 3 * 65536 + 7 sent to the arrow towers."); '
    effect(encoding, "script_call", message=f"void probeAttackEncoding() {{ {packed}{ran}}}")
