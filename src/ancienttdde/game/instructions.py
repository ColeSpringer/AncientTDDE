"""The objectives panel's Instructions, Hints and Scouts tabs, and the sidecar collecting them."""

from dataclasses import dataclass

from ancienttdde.common.credits import CREDIT, NAME
from ancienttdde.game.catalog import Repair, Shop, population_name
from ancienttdde.game.civilizations import DEFAULT_NAME, Profiles
from ancienttdde.game.config import LOBBY_DIFFICULTIES, MAX_HIT_POINTS, Balance
from ancienttdde.game.script import STILL_SAMPLES
from ancienttdde.game.sites import SIEGE_ROWS
from ancienttdde.scenario.objects import display_name

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


@dataclass(frozen=True)
class Section:
    """A titled part of a tab. Blank lines separate the body's paragraphs and lists."""

    title: str
    body: str


def tab(sections: list[Section]) -> str:
    """A tab as the objectives panel shows it: each title on the line above its body."""
    return "\n\n".join(f"{section.title}\n{section.body}" for section in sections) + "\n"


def count(amount: int, single: str, plural: str) -> str:
    return f"{amount} {single if amount == 1 else plural}"


def listed(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def starting_research(balance: Balance) -> str:
    """The clause naming the technologies every lane starts with, or nothing."""
    names = [display_name(name) for name in balance.economy.starting_technologies]
    return f", with {listed(names)} researched" if names else ""


def bonus_reward(balance: Balance, resource: str) -> str:
    """What reaching the end of a resource's rows gives. The delivery message quotes it."""
    economy = balance.economy
    amount = {"gold": economy.gold_bonus, "food": economy.food_bonus, "stone": economy.stone_bonus}
    return f"{amount[resource]} {resource} and {DEPOSITS[resource]}"


def bonus_delivered(balance: Balance, resource: str) -> str:
    return (
        f"{resource.title()} bonus delivered: {bonus_reward(balance, resource)} "
        f"{DEPOSIT_PLACES[resource]}."
    )


def lobby_levels(balance: Balance) -> str:
    """A sentence per level naming the lobby difficulty settings that play it, easiest first."""
    lobby = dict(balance.difficulty.lobby)
    names = sorted(LOBBY_DIFFICULTIES, key=lambda name: -LOBBY_DIFFICULTIES[name])
    parts: list[str] = []
    for index, level in enumerate(balance.difficulty.levels):
        settings = [n.title() for n in names if lobby[LOBBY_DIFFICULTIES[n]] == index]
        if settings:
            verb = "plays" if len(settings) == 1 else "play"
            parts.append(f"{listed(settings)} {verb} {level.name}")
    return ". ".join(parts)


def king_prices(balance: Balance) -> str:
    levels = balance.difficulty.levels
    first, *rest = levels
    prices = [f"{first.king_gold} gold on {first.name}"] + [
        f"{level.king_gold} on {level.name}" for level in rest
    ]
    return ", ".join(prices[:-1]) + " or " + prices[-1]


def hit_point_scales(balance: Balance) -> str:
    priced = balance.difficulty.default
    others = [
        f"{level.hit_points_percent}% on {level.name}"
        for index, level in enumerate(balance.difficulty.levels)
        if index != priced
    ]
    return listed(others)


def raider_bonuses(profiles: Profiles) -> str:
    """A sentence per medium and amount naming the civilizations that keep more raiders, each
    with a leading space, or nothing."""
    groups: dict[tuple[str, int], list[str]] = {}
    for civilization, medium, extra in profiles.raider_bonuses():
        groups.setdefault((medium, extra), []).append(display_name(civilization))
    parts = [
        f"{listed(names)} keep {'one' if extra == 1 else extra} more {medium} raider"
        + ("" if extra == 1 else "s")
        for (medium, extra), names in groups.items()
    ]
    return "".join(f" {part}." for part in parts)


def civilization_lines(profiles: Profiles) -> str:
    """One line per civilization, sorted by name, the default last."""
    listed = sorted(profiles.civilizations, key=lambda c: c.name)
    lines = [f"- {c.name}: {profiles.text(c)}." for c in listed]
    lines.append(f"- {DEFAULT_NAME}: {profiles.text(None)}.")
    return "\n".join(lines)


def instruction_sections(balance: Balance, shop: Shop) -> list[Section]:
    """How to host and play: the lobby, the goal, the run options, Kings and building."""
    economy = balance.economy
    practice = balance.practice
    kills = economy.kills_per_reward
    return [
        Section(
            "Hosting",
            "Standard data set, fixed positions, locked teams, Fast game speed, Reveal Map All "
            f"Visible and Population {balance.population_cap}. Put humans in slots 1 to 7 and "
            "a computer in at least one other: the highest-numbered computer is the enemy, "
            "whichever slot it sits in, and other computer lanes sit out. Choose any "
            f"civilization. The lobby's Difficulty sets the level. {lobby_levels(balance)}.",
        ),
        Section(
            "Goal",
            "Hold your lane: each enemy reaching the exit flags costs a life, a boss "
            f"{balance.boss_leak_lives}, and at 0 lives the lane falls. Solo, clearing all "
            f"{len(balance.waves)} waves wins, and an Endless run goes on until the lane falls "
            "and counts the waves cleared. In competition the last lane standing wins. If "
            "several clear the finale, sudden death drains every survivor's lives every "
            f"{balance.sudden_death_interval} game seconds, more each time and up to 10 at "
            "once, until one remains. If the last lanes fall together, nobody wins. Resigning "
            "or disconnecting forfeits a lane.",
        ),
        Section(
            "Run options",
            f"The first human lane has {balance.choice_seconds} game seconds to select one "
            "Outpost in the row below the shop. Its first selection is final, and preparation "
            "starts at once. With no selection in time, the run is Standard with PvP off. "
            "Solo runs choose Standard, Endless (the waves go on after the finale) or "
            "Practice (assisted, with controls beside the options that start the next wave, "
            f"add {practice.kings} Kings, add {practice.resources} of each resource and "
            "restore all lives, each once per selection). Competitive games choose PvP on, "
            "which sells raiders and the siege power-up from the first wave.",
        ),
        Section(
            "Kings and the shop",
            f"Every {king_prices(balance)} becomes a King at your stall above the shop. "
            f"Surviving a wave earns {count(economy.wave_kings, 'King', 'Kings')}, every "
            f"{kills} wave kills pay {economy.kill_stone} stone and {economy.kill_wood} wood, "
            f"and every {kills * economy.rewards_per_king} earn a King. To buy, walk Kings onto "
            f"a pad and let them stand about {STILL_SAMPLES + 1} seconds: a purchase takes "
            "exactly its price, a refusal nothing, and Kings left standing buy again.",
        ),
        Section(
            "Building",
            "Villagers build towers, mills, camps and farms or pastures only. Towers stand in "
            "the build rows, and one built elsewhere is removed. Markets train trade carts and "
            "docks trade cogs, and nothing else trains or converts. Bought villagers, traders "
            "and raiders, and the traders markets and docks train, need population room. A "
            f"lane starts with room for {economy.starting_population} more, and only the "
            f"shop's {population_name(shop)} (again and again, up to "
            f"{balance.population_cap}), the castle and some profiles add more. Kings, monks "
            "and trebuchets take none.",
        ),
    ]


def hint_sections(balance: Balance, shop: Shop, profiles: Profiles) -> list[Section]:
    """What helps: resources, the catalog and its rules, towers, PvP and the profiles."""
    economy = balance.economy
    towers = balance.towers
    raiders = balance.interaction.raiders
    siege = balance.interaction.siege
    repair = next((p.effect for p in shop.purchases if isinstance(p.effect, Repair)), None)
    repairs = (
        f" The repair crew restores one life every {repair.interval} game seconds for "
        f"{repair.stone} stone, up to the starting total."
        if repair
        else ""
    )
    catalog = "\n".join(f"- {p.caption}" for p in shop.purchases)
    return [
        Section(
            "Resources",
            "Gold comes from trade, relics, mining and the market. Mining or foraging to the "
            f"end of the gold, berry or stone rows pays {economy.gold_bonus} gold, "
            f"{economy.food_bonus} food or {economy.stone_bonus} stone once and opens deposits "
            "that never run out. The trees beside your lumber camps never run out either. "
            "Messages about your Kings, rewards and refused purchases reach only you. Saving "
            "works at any point.",
        ),
        Section(
            "Purchases",
            "Purchases marked once are once per player, and some need another purchase first. "
            "Investments pay on every multiple of their period, counted from the start of "
            f"preparation.{repairs} The castle brings population and its research but never "
            f"fires.\n\n{catalog}",
        ),
        Section(
            "Towers",
            "Tower attack raises Watch Towers, Guard Towers, Keeps and Bombard Towers, built "
            "now or later. Bombard Tower attack raises Bombard Towers alone. The left and right "
            "Accursed Towers stand on the reserved pads in the middle of your build rows, with "
            f"{towers.special_attack + towers.special_pierce} pierce attack and a range of "
            f"{towers.special_range}. Castle Age adds Guard Towers and Imperial Age Keeps, each "
            "for civilizations that have the tower. With Imperial Age and Chemistry, the "
            "Bombard Tower research completes on its own at no cost. Every game rules out "
            "Yasama, Stronghold and Siege Engineers, and competitive games Eupseong and "
            "Artillery. Towers fire one arrow of their own whatever the civilization.",
        ),
        Section(
            "PvP",
            f"Each player keeps at most {raiders.land.cap} land and {raiders.naval.cap} naval "
            f"raiders alive.{raider_bonuses(profiles)} The siege power-up puts "
            f"{siege.trebuchets_per_row} trebuchets on each of the {SIEGE_ROWS} islet rows "
            f"flanking the lanes {siege.warning_seconds} game seconds after purchase, for "
            f"{siege.active_seconds} game seconds, and they fire at every enemy tower and unit "
            "in reach. One player holds it at a time, and it is for sale again after "
            f"{siege.shared_cooldown} game seconds for everyone and {siege.buyer_cooldown} for "
            "its buyer.",
        ),
        Section(
            "Civilizations",
            "Each civilization keeps its technology tree and bonuses. Its profile adds the "
            "adjustments listed here, announced with your towers when preparation begins. "
            "Starting towers stand in mirrored pairs on the build rows beside the path.\n\n"
            f"{civilization_lines(profiles)}",
        ),
    ]


def scout_sections(balance: Balance) -> list[Section]:
    """What scouts report: the enemy, your lane, the wave schedule and the rivals' reach."""
    economy = balance.economy
    start = economy.starting_resources
    raiders = balance.interaction.raiders
    level = balance.difficulty.default
    lines: list[str] = []
    for i, w in enumerate(balance.waves, 1):
        armor = f", {w.pierce_armor} pierce armor" if w.pierce_armor is not None else ""
        if w.boss:
            lines.append(f"{i}. {w.key}: boss, {balance.hit_points(i - 1, level)} HP{armor}")
        else:
            lines.append(
                f"{i}. {w.key}: {w.enemies} enemies, {balance.hit_points(i - 1, level)} HP "
                f"each{armor}, {w.duration} s"
            )
    schedule = "\n".join(lines)
    threes = next((i for i, w in enumerate(balance.waves, 1) if w.count == 3), None)
    batches = "Enemies spawn in pairs on the same schedule in every surviving lane"
    if threes is not None:
        batches += f", in threes from wave {threes}"
    batches += ", and each boss alone"
    endless = listed([balance.waves[t].key for t in balance.endless.templates])
    return [
        Section(
            "Enemy",
            "The highest-numbered computer player, named in the chat at the start. Its units "
            "walk each lane's path at their native speed, never attack, and leave by the exit "
            "flags at the right-hand end.",
        ),
        Section(
            "Your lane",
            f"You start with {start.food} food, {start.wood} wood, {start.stone} stone and "
            f"{start.gold} gold, {balance.lives} lives, three Kings in the shop, villagers in "
            "the build and resource areas, eight trade carts and four trade cogs already "
            f"trading, and {count(economy.starting_relics, 'relic', 'relics')} in the "
            f"monasteries{starting_research(balance)}. Villagers cannot cross the enemy path or "
            "walk between the build rows and the resource area: one standing on the flag at "
            "the end of a walkway crosses (its relic names where it goes) and arrives on a "
            "flag. The life Outpost below the shop shows your lives.",
        ),
        Section(
            "Waves",
            f"The first wave comes after {balance.preparation_seconds} game seconds of "
            f"preparation, about {balance.preparation_seconds / FAST_GAME_SPEED:.0f} real "
            f"seconds at Fast. {batches}. The next wave follows {balance.intermission_seconds} "
            "game seconds after the last enemy is cleared, and the schedule lasts about "
            f"{balance.scheduled_seconds / 60:.1f} game minutes plus cleanup. Hit points below "
            f"are for {balance.difficulty.levels[level].name}: {hit_point_scales(balance)}, up "
            f"to {MAX_HIT_POINTS} for regular enemies. The time is each wave's spawning span in "
            "game seconds, and pierce armor is listed where the schedule sets it. A boss shows "
            f"at most {MAX_HIT_POINTS} and is refilled from its "
            "whole amount as it takes damage, so it falls only once that amount is spent. The "
            f"chat tells its lane at each quarter.\n\n{schedule}\n\nAfter the finale, Endless "
            f"runs and sudden death repeat {endless} in turn at {MAX_HIT_POINTS} hit points, "
            f"each wave with +{balance.endless.armor_step} pierce armor more.",
        ),
        Section(
            "Rivals",
            f"With PvP on, land raiders ({display_name(raiders.land.unit).lower()}) fight in "
            "the land trade field below the markets and naval raiders "
            f"({display_name(raiders.naval.unit).lower()}) in the trade channel below the "
            "docks. They attack every rival's traders and raiders there and cannot leave. "
            "Markets, docks, Kings, life Outposts, yurts and trebuchets cannot be attacked, "
            "but traders can.",
        ),
    ]


def instructions(balance: Balance, shop: Shop) -> str:
    """The Instructions tab, ending with the credit."""
    return f"{tab(instruction_sections(balance, shop))}\n{CREDIT}.\n"


def hints(balance: Balance, shop: Shop, profiles: Profiles) -> str:
    return tab(hint_sections(balance, shop, profiles))


def scouts(balance: Balance) -> str:
    return tab(scout_sections(balance))


def document(balance: Balance, shop: Shop, profiles: Profiles) -> str:
    """The three tabs as one markdown file, the credit last."""
    tabs = (
        ("Instructions", instruction_sections(balance, shop)),
        ("Hints", hint_sections(balance, shop, profiles)),
        ("Scouts", scout_sections(balance)),
    )
    parts = [f"# {NAME}"]
    for name, sections in tabs:
        parts.append(f"## {name}")
        parts += [f"### {section.title}\n\n{section.body}" for section in sections]
    parts.append(f"{CREDIT}.")
    return "\n\n".join(parts) + "\n"
