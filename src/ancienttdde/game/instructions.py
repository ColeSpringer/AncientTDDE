"""Hosting and play instructions written into the scenario and its sidecar."""

from ancienttdde.game.config import Balance

# DE's Fast lobby speed runs game time at twice real time.
FAST_GAME_SPEED = 2


def instructions(balance: Balance) -> str:
    schedule = "\n".join(
        f"{i}. {w.key}: {w.batches * w.count} enemies, {w.duration} game seconds"
        + (" (boss)" if w.boss else "")
        for i, w in enumerate(balance.waves, 1)
    )
    return (
        "# Ancient TD DE\n\n"
        "Host with the standard DE data set and all eight player slots. Put humans in "
        "any of slots 1–7 and fill the remaining slots with computers. Keep player 8 as "
        "the computer enemy. The embedded passive AI handles every computer slot. "
        "Only human-controlled defense lanes participate; computer-filled defense lanes "
        "are cleared automatically, and do not affect victory. "
        "Use fixed start positions, locked teams and Fast (the highest lobby game speed). "
        "The host must select game speed in the lobby; the scenario cannot set that control. "
        "Civilizations remain selectable. Set Reveal Map to All Visible.\n\n"
        "All seven defense players have a mill beside their berries, owned by that player. "
        f"Each human lane starts with {balance.lives} lives, two Watch Towers, its original "
        f"builders/economy, and {balance.starting_resources} of each resource. "
        f"Build more Watch Towers with the villagers beside your lane. Arrow towers receive "
        f"+{balance.tower_attack_bonus} pierce attack once, including future towers. "
        f"You receive {balance.income_amount} of each resource every {balance.income_interval} "
        "game seconds while your lane survives. Your eight carts and four cogs start trading "
        "automatically with their assigned partners. Gathering is also available, and the "
        "trees beside your lumber camps never run out.\n\n"
        f"Preparation lasts {balance.preparation_seconds} game seconds, about "
        f"{balance.preparation_seconds / FAST_GAME_SPEED:.0f} real seconds at Fast. "
        "Each enemy reaching the exit flags at the right-hand end of a lane costs one life. "
        "Computer-filled and eliminated lanes receive no waves or income. "
        "Enemies spawn in pairs on the same schedule in all surviving lanes. "
        f"There are {balance.intermission_seconds} game seconds between waves after the "
        "remaining enemies are cleared. The schedule lasts about "
        f"{balance.scheduled_seconds / 60:.1f} game minutes plus enemy cleanup.\n\n"
        "Solo victory requires clearing the entire finale. In competition the last survivor "
        "wins; multiple survivors after the finale enter sudden death. "
        f"Sudden death removes increasing lives from every survivor every "
        f"{balance.sudden_death_interval} game seconds, up to 10 lives per pulse. "
        "Simultaneous elimination of the entire field is a shared defeat. "
        "Resignation or disconnect eliminates that lane when DE reports it out of the game.\n\n"
        "The original King shop displays are closed. King purchases and generation, special "
        "tower purchases, trade raiders, siege purchases, Practice and Endless controls are "
        "unavailable in this ruleset. The two central Hay Stack pads in each lane remain "
        "reserved for special towers; ordinary towers cannot be built there. "
        "Do not use the gallery displays as purchase instructions.\n\n"
        "Save normally during preparation, waves or sudden death. Progress, life totals and "
        "countdowns are stored in the scenario.\n\n"
        "## Waves\n\n" + schedule + "\n\n"
        "Original Ancient Tower Defense map by DRAX6869 / DRAX.\n"
    )
