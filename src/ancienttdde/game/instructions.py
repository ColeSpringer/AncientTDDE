"""Hosting and play instructions written into the scenario and its sidecar."""

from ancienttdde.game.catalog import Repair, ResourceGrant, Shop
from ancienttdde.game.config import Balance
from ancienttdde.game.script import STILL_SAMPLES
from ancienttdde.scenario.objects import display_name

CREDIT = "Original Ancient Tower Defense by DRAX6869 / DRAX"

# DE's Fast lobby speed runs game time at twice real time.
FAST_GAME_SPEED = 2
DEPOSITS = {
    "gold": "endless gold mines",
    "food": "an endless berry bush",
    "stone": "endless stone mines",
}
DEPOSIT_PLACES = {
    "gold": "beside your mining camp",
    "food": "at the end of the berry rows",
    "stone": "beside your mining camp",
}


def count(amount: int, single: str, plural: str) -> str:
    return f"{amount} {single if amount == 1 else plural}"


def listed(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def opening_stock(shop: Shop) -> str:
    """The resource purchases that top up the starting grant, each with its price."""
    grants = [
        (purchase, purchase.effect)
        for purchase in shop.purchases
        if isinstance(purchase.effect, ResourceGrant)
    ]
    if not grants:
        return ""
    sold = [
        f"{effect.amount} {effect.resource} for {purchase.price}" for purchase, effect in grants
    ]
    return f"The shop sells {listed(sold)}. "


def starting_research(balance: Balance) -> str:
    names = [display_name(name) for name in balance.economy.starting_technologies]
    return f"Every lane starts with {listed(names)} researched. " if names else ""


def bonus_reward(balance: Balance, resource: str) -> str:
    """What reaching the end of a resource's rows gives; the delivery message quotes it."""
    economy = balance.economy
    amount = {"gold": economy.gold_bonus, "food": economy.food_bonus, "stone": economy.stone_bonus}
    return f"{amount[resource]} {resource} and {DEPOSITS[resource]}"


def bonus_delivered(balance: Balance, resource: str) -> str:
    return (
        f"{resource.title()} bonus delivered: {bonus_reward(balance, resource)} "
        f"{DEPOSIT_PLACES[resource]}."
    )


def instructions(balance: Balance, shop: Shop) -> str:
    economy = balance.economy
    towers = balance.towers
    start = economy.starting_resources
    repair = next((p.effect for p in shop.purchases if isinstance(p.effect, Repair)), None)
    schedule = "\n".join(
        f"{i}. {w.key}: {w.batches * w.count} enemies with {w.hit_points} HP each, "
        f"{w.duration} game seconds" + (" (boss)" if w.boss else "")
        for i, w in enumerate(balance.waves, 1)
    )
    catalog = "\n".join(f"- {p.caption}" for p in shop.purchases)
    repairs = (
        f"The repair crew restores one life every {repair.interval} game seconds for "
        f"{repair.stone} stone, up to the starting total."
        if repair
        else ""
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
        "## Economy\n\n"
        f"Each human lane starts with {start.food} food, {start.wood} wood, {start.stone} "
        f"stone and {start.gold} gold, {balance.lives} lives, three Kings in the shop, two "
        "Watch Towers, villagers in its build and resource areas, eight trade carts and four "
        "trade cogs that start trading, and "
        f"{count(economy.starting_relics, 'relic', 'relics')} in its monasteries. "
        f"{opening_stock(shop)}{starting_research(balance)}Your houses "
        "provide population; Kings, villagers, traders and monks all use it.\n\n"
        f"Every {economy.king_gold} gold you hold becomes a King at your stall above the "
        "shop. Surviving a wave earns every lane "
        f"{count(economy.wave_kings, 'King', 'Kings')}, every "
        f"{economy.kills_per_reward} kills pay {economy.kill_stone} stone and "
        f"{economy.kill_wood} wood, and every "
        f"{economy.kills_per_reward * economy.rewards_per_king} kills earn a King. Gold also "
        "comes from trade, relics, mining and the market. Mining or foraging through to the "
        f"end of the gold, berry or stone rows pays {economy.gold_bonus} gold, "
        f"{economy.food_bonus} food or {economy.stone_bonus} stone once and opens deposits "
        "that never run out. The trees beside your lumber camps never run out either. "
        "Messages about your Kings, rewards and refused purchases are shown only to you.\n\n"
        "Villagers cannot walk between the build and resource areas, or across the enemy "
        "path. Stand one on a flagged transfer pad to move it to the other area.\n\n"
        "## Shop\n\n"
        f"Walk Kings onto a shop pad and let them stand for about {STILL_SAMPLES + 1} seconds; "
        "Kings walking across or pausing briefly on a pad buy nothing. A purchase takes "
        "exactly its price, and Kings left on the pad buy it again if they can. Purchases "
        "marked once can be bought once per player, and some need another purchase first. "
        "Investments pay on every multiple of their period, counted from the start of "
        "preparation.\n\n"
        f"{catalog}\n\n"
        "## Towers and lives\n\n"
        "Tower attack purchases raise Watch Towers, Guard Towers, Keeps and Bombard Towers, "
        "including towers built or upgraded later; Bombard Tower attack raises only Bombard "
        "Towers. The left and right Accursed Towers stand on the reserved pads in the middle "
        f"of your build rows, with {towers.special_attack + towers.special_pierce} pierce "
        f"attack and a range of {towers.special_range}. Castle Age adds Guard Towers and "
        "Imperial Age adds Keeps for civilizations that have them; each civilization keeps "
        "its own technology tree, and the game lists your available towers when preparation "
        "begins.\n\n"
        "Each enemy reaching the exit flags at the right-hand end of a lane costs one life. "
        "Your life Outpost below the shop shows your remaining lives, and the objectives "
        f"list every lane. {repairs}".rstrip()
        + "\n\n"
        "## Waves\n\n"
        f"Preparation lasts {balance.preparation_seconds} game seconds, about "
        f"{balance.preparation_seconds / FAST_GAME_SPEED:.0f} real seconds at Fast. "
        "Enemies spawn in pairs on the same schedule in all surviving lanes. "
        f"There are {balance.intermission_seconds} game seconds between waves after the "
        "remaining enemies are cleared. The schedule lasts about "
        f"{balance.scheduled_seconds / 60:.1f} game minutes plus enemy cleanup.\n\n"
        f"{schedule}\n\n"
        "## Victory\n\n"
        "Solo victory requires clearing the entire finale. In competition the last survivor "
        "wins; multiple survivors after the finale enter sudden death. "
        f"Sudden death removes increasing lives from every survivor every "
        f"{balance.sudden_death_interval} game seconds, up to 10 lives per pulse. "
        "Simultaneous elimination of the entire field is a shared defeat. "
        "Resignation or disconnect eliminates that lane when DE reports it out of the game.\n\n"
        "Save normally during preparation, waves or sudden death. Progress, lives, purchases "
        "and countdowns are stored in the scenario.\n\n"
        f"{CREDIT}.\n"
    )
