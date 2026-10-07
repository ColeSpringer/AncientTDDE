"""Messages the engine sends one lane's player, by code, through that lane's native triggers."""

from ancienttdde.game.config import Balance

# In code order; the XS requests a message by setting the lane's message field to its code.
MESSAGES: tuple[tuple[str, str], ...] = (
    ("owned", "That purchase is already yours; move your Kings off its pad."),
    ("requires", "That purchase needs another one first; its sign names it."),
    ("relics", "Monks must collect the last relics before more can be bought."),
    ("civilization", "Your civilization lacks the towers that purchase improves."),
    ("no_room", "No room for the purchase to appear; move units off its arrival spots."),
    ("gold", "Gold converted: a King per {king_gold} gold arrives at your stall."),
    ("kill_king", "Kill reward: every {kills} kills earn a King; one arrives at your stall."),
)


def message_code(key: str) -> int:
    return [name for name, _ in MESSAGES].index(key) + 1


def message_texts(balance: Balance) -> dict[str, str]:
    economy = balance.economy
    values = {
        "king_gold": economy.king_gold,
        "kills": economy.kills_per_reward * economy.rewards_per_king,
    }
    return {key: text.format(**values) for key, text in MESSAGES}
