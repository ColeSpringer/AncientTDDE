"""Messages the engine sends one lane's player, by code, through that lane's native triggers."""

from ancienttdde.game.config import Balance

# In code order; the XS requests a message by setting the lane's message field to its code.
MESSAGES: tuple[tuple[str, str], ...] = (
    ("owned", "That purchase is already yours; move your Kings off its pad."),
    ("requires", "That purchase needs another one first; its sign names it."),
    ("relics", "Monks must collect the last relics before more can be bought."),
    ("civilization", "Your civilization lacks the towers that purchase improves."),
    ("no_room", "No room for the purchase to appear; move units off its arrival spots."),
    ("gold", "Gold converted into Kings; they arrive at your stall."),
    ("kill_king", "Kill reward: every {kills} wave kills earn a King; one arrives at your stall."),
    (
        "pvp_off",
        "Raiders and siege are sold only with PvP on, from the first wave of a competitive game.",
    ),
    ("no_rival", "No rival survives to raid or besiege."),
    ("raider_cap", "You already keep as many raiders of that kind as you may; your Kings stay."),
    ("siege_held", "Another player holds the siege power-up; your Kings stay."),
    (
        "siege_cooldown",
        "The siege power-up is cooling down, longer for its last buyer; your Kings stay.",
    ),
    ("chooser_only", "Only the first human lane chooses the run options."),
    (
        "options_fixed",
        "The run options are fixed once the first wave starts or practice help is used.",
    ),
    ("solo_modes", "Endless and Practice are solo modes; competitive games play Standard."),
    ("needs_rivals", "PvP needs rivals: it applies only to competitive games."),
    ("practice_only", "Practice controls work only in Practice runs."),
    ("practice_wave", "Practice: the next wave can start once the current one ends."),
    ("siege_yours", "You hold the siege power-up already; your Kings stay."),
    (
        "economy_tower",
        "Towers belong in your build rows: one built in your resource area was removed.",
    ),
)


def message_code(key: str) -> int:
    return [name for name, _ in MESSAGES].index(key) + 1


def message_texts(balance: Balance) -> dict[str, str]:
    economy = balance.economy
    values = {"kills": economy.kills_per_reward * economy.rewards_per_king}
    return {key: text.format(**values) for key, text in MESSAGES}
