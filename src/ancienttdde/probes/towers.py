"""Tower bonus persistence: an attack bonus survives construction, upgrades and saves."""

from ancienttdde.probes.arena import Arena, tile_text
from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId
from ancienttdde.scenario.triggers import TriggerHandle, effect

BONUS_PAD = (8, 8)
CASTLE_PAD = (16, 8)
IMPERIAL_PAD = (24, 8)
TOWN_CENTER = (24, 28)

DEFINITION = ProbeDefinition(
    ProbeId.TOWERS,
    "Tower bonus persistence",
    "Use a standard civilization with Guard Tower and Keep (Britons recommended). "
    "The game starts in Feudal Age. Move the control King to the bonus pad "
    f"{tile_text(BONUS_PAD)}, then build towers with the villagers. The pads at "
    f"{tile_text(CASTLE_PAD)} and {tile_text(IMPERIAL_PAD)} force "
    "Castle/Guard Tower and Imperial/Keep respectively. Keep the control King alive. "
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
