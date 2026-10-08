"""Hosting and play instructions written into the scenario and its sidecar."""

from ancienttdde.game.catalog import Repair, ResourceGrant, Shop
from ancienttdde.game.civilizations import DEFAULT_NAME, Profiles
from ancienttdde.game.config import LOBBY_DIFFICULTIES, Balance
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


def lobby_levels(balance: Balance) -> str:
    """Which lobby difficulty settings play which level, easiest first."""
    lobby = dict(balance.difficulty.lobby)
    names = sorted(LOBBY_DIFFICULTIES, key=lambda name: -LOBBY_DIFFICULTIES[name])
    parts: list[str] = []
    for index, level in enumerate(balance.difficulty.levels):
        settings = [n.title() for n in names if lobby[LOBBY_DIFFICULTIES[n]] == index]
        if settings:
            verb = "plays" if len(settings) == 1 else "play"
            parts.append(f"{listed(settings)} {verb} {level.name}")
    return "; ".join(parts)


def king_prices(balance: Balance) -> str:
    levels = balance.difficulty.levels
    first, *rest = levels
    prices = [f"{first.king_gold} gold on {first.name}"] + [
        f"{level.king_gold} on {level.name}" for level in rest
    ]
    return ", ".join(prices[:-1]) + " or " + prices[-1]


def hit_point_scales(balance: Balance) -> str:
    normal = balance.difficulty.competitive
    others = [
        f"{level.hit_points_percent}% on {level.name}"
        for index, level in enumerate(balance.difficulty.levels)
        if index != normal
    ]
    return listed(others)


def raider_bonuses(profiles: Profiles) -> str:
    """Civilizations that keep more raiders, one sentence part per medium and amount."""
    groups: dict[tuple[str, int], list[str]] = {}
    for civilization, medium, extra in profiles.raider_bonuses():
        groups.setdefault((medium, extra), []).append(display_name(civilization))
    parts = [
        f"{listed(names)} keep {'one' if extra == 1 else extra} more {medium} raider"
        + ("" if extra == 1 else "s")
        for (medium, extra), names in groups.items()
    ]
    return "; ".join(parts) + ". " if parts else ""


def interaction(balance: Balance, profiles: Profiles) -> str:
    raiders = balance.interaction.raiders
    siege = balance.interaction.siege
    return (
        "With PvP on, raiders and the siege power-up are for sale from the first wave. "
        f"Land raiders ({display_name(raiders.land.unit).lower()}) arrive below your market in "
        f"the land trade field and naval raiders ({display_name(raiders.naval.unit).lower()}) "
        "below your dock in the trade channel; they fight every rival's traders and raiders and "
        f"cannot leave those areas. Each player keeps at most {raiders.land.cap} land and "
        f"{raiders.naval.cap} naval raiders alive; {raider_bonuses(profiles)}"
        f"The siege power-up puts {siege.trebuchets_per_rival} trebuchets beside every "
        f"surviving rival's towers {siege.warning_seconds} game seconds after purchase, for "
        f"{siege.active_seconds} game seconds. One player holds it at a time, and it is for "
        f"sale again after {siege.shared_cooldown} game seconds for everyone and "
        f"{siege.buyer_cooldown} for its buyer. Markets, docks, Kings, life Outposts and yurts "
        "cannot be attacked; traders can. Villagers build towers and economy buildings only: "
        "no houses, walls, gates, outposts, markets, blacksmiths or universities, and no "
        "military buildings, docks, monasteries or town centers. Lanes cannot train ships "
        "other than trade cogs, monks or castle units, or convert units, and a bought castle "
        "never fires."
    )


def civilization_lines(profiles: Profiles) -> str:
    lines = [f"- {c.name}: {profiles.text(c)}." for c in profiles.civilizations]
    lines.append(f"- {DEFAULT_NAME}: {profiles.text(None)}.")
    return "\n".join(lines)


def instructions(balance: Balance, shop: Shop, profiles: Profiles) -> str:
    economy = balance.economy
    towers = balance.towers
    start = economy.starting_resources
    repair = next((p.effect for p in shop.purchases if isinstance(p.effect, Repair)), None)
    schedule = "\n".join(
        f"{i}. {w.key}: {w.batches * w.count} enemies with "
        f"{balance.hit_points(i - 1, balance.difficulty.competitive)} HP each, "
        f"{w.duration} game seconds" + (" (boss)" if w.boss else "")
        for i, w in enumerate(balance.waves, 1)
    )
    catalog = "\n".join(f"- {p.caption}" for p in shop.purchases)
    endless = listed([balance.waves[t].key for t in balance.endless.templates])
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
        "Civilizations remain selectable. Set Reveal Map to All Visible. For solo runs, the "
        f"lobby's Difficulty sets the level: {lobby_levels(balance)}. Competitive games always "
        f"play {balance.difficulty.levels[balance.difficulty.competitive].name}.\n\n"
        "## Run options\n\n"
        "Before the first wave, the first human lane chooses the run options by selecting them "
        "in the row of Outposts below the shop. A solo run chooses Standard, Endless or "
        "Practice: Standard ends in victory after the finale, Endless keeps the waves coming, "
        f"and Practice adds controls beside the options: start the next wave now, "
        f"{balance.practice.kings} more Kings, {balance.practice.resources} more of each "
        "resource and all lives back. A Practice run is shown as assisted. Competitive games "
        "start with PvP off; selecting PvP on puts raiders and the siege power-up on sale. Each "
        "new selection of an Outpost acts once. The options are fixed once the first wave "
        "starts or practice help is first used; then the run options leave the row, as do the "
        "practice controls unless the run is Practice.\n\n"
        "## Economy\n\n"
        f"Each human lane starts with {start.food} food, {start.wood} wood, {start.stone} "
        f"stone and {start.gold} gold, {balance.lives} lives, three Kings in the shop, two "
        "Watch Towers, villagers in its build and resource areas, eight trade carts and four "
        "trade cogs that start trading, and "
        f"{count(economy.starting_relics, 'relic', 'relics')} in its monasteries. "
        f"{opening_stock(shop)}{starting_research(balance)}Population comes only "
        "from the shop's +80 population and castle, and from the civilization profiles that "
        "add some below: houses cannot be built, and Kings, villagers, traders and monks all "
        "use it.\n\n"
        f"Every {king_prices(balance)} becomes a King at your stall above the "
        "shop. Surviving a wave earns every lane "
        f"{count(economy.wave_kings, 'King', 'Kings')}, every "
        f"{economy.kills_per_reward} wave kills pay {economy.kill_stone} stone and "
        f"{economy.kill_wood} wood, and every "
        f"{economy.kills_per_reward * economy.rewards_per_king} wave kills earn a King. Gold also "
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
        f"{interaction(balance, profiles)}\n\n"
        "## Civilizations\n\n"
        "Each civilization keeps its own technology tree and bonuses. On top of them, its "
        "profile adjusts the lane as listed here; the game announces every lane's towers and "
        "civilization line when preparation begins.\n\n"
        f"{civilization_lines(profiles)}\n\n"
        "## Towers and lives\n\n"
        "Tower attack purchases raise Watch Towers, Guard Towers, Keeps and Bombard Towers, "
        "including towers built or upgraded later; Bombard Tower attack raises only Bombard "
        "Towers. The left and right Accursed Towers stand on the reserved pads in the middle "
        f"of your build rows, with {towers.special_attack + towers.special_pierce} pierce "
        f"attack and a range of {towers.special_range}. Castle Age adds Guard Towers and "
        "Imperial Age adds Keeps for civilizations that have them; each civilization keeps "
        "its own technology tree, and the game lists your available towers when preparation "
        "begins. Towers stand only in your build rows: one built in the resource area is "
        "removed. Every game rules out Yasama and Stronghold, which would multiply every "
        "tower's volley, and towers fire one arrow of their own whatever the civilization. "
        "Competitive games rule out Eupseong and Artillery, whose range would reach the next "
        "lane.\n\n"
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
        f"{balance.scheduled_seconds / 60:.1f} game minutes plus enemy cleanup. Hit points "
        f"below are for {balance.difficulty.levels[balance.difficulty.competitive].name}: "
        f"{hit_point_scales(balance)}, up to 32767.\n\n"
        f"{schedule}\n\n"
        f"After the finale, Endless runs and sudden death keep the waves coming: {endless} "
        f"repeat in turn with {balance.endless.growth_percent}% more hit points each round, up "
        f"to 32767, and every such wave gives their enemies +{balance.endless.armor_step} "
        "pierce armor more.\n\n"
        "## Victory\n\n"
        "Solo Standard and Practice runs are won by clearing the entire finale; an Endless run "
        "goes on until its lane falls, and the result counts the waves cleared. In competition "
        "the last survivor wins; if several survive the finale, sudden death begins: the waves "
        "keep growing and every survivor loses lives every "
        f"{balance.sudden_death_interval} game seconds, more each time, up to 10 at once. "
        "Simultaneous elimination of the entire field is a shared defeat. "
        "Resignation or disconnect eliminates that lane when DE reports it out of the game.\n\n"
        "Save normally during preparation, waves or sudden death. Progress, lives, purchases "
        "and countdowns are stored in the scenario.\n\n"
        f"{CREDIT}.\n"
    )
