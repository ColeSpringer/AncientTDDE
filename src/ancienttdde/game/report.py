"""The balance tables as Markdown, from the balance model."""

from dataclasses import fields

from ancienttdde.game.balance import (
    FOOD_PER_KING,
    RANGE_KINGS,
    Assumptions,
    Inputs,
    attack_ladder,
    baseline_income,
    investment_returns,
    lane_pressure,
    profile_table,
    rates,
    rivalry,
    tower_dps,
    wave_needs,
)
from ancienttdde.game.catalog import Investment, Purchase, ResourceGrant, SiegePowerUp, TowerAttack
from ancienttdde.game.civilizations import DEFAULT_NAME, adjustments
from ancienttdde.game.stock import PIERCE_CLASS
from ancienttdde.scenario.objects import display_name

# The report's first line, which marks a balance.md as this command's own output.
REPORT_TITLE = "# Balance tables"


def cell(text: str) -> str:
    """One table cell: pipes are escaped and line breaks become spaces."""
    return " ".join(text.replace("|", "\\|").splitlines())


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(cell(h) for h in headers) + " |", "|" + " --- |" * len(headers)]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def kings(value: float) -> str:
    return f"{value:.1f}"


def level_name(inputs: Inputs) -> str:
    """The difficulty level the tables price: the one every competitive game plays."""
    return inputs.balance.difficulty.levels[inputs.level].name


def assumptions_section(inputs: Inputs, assumptions: Assumptions) -> str:
    stock = inputs.stock
    rows = [
        [field.name.replace("_", " "), str(getattr(assumptions, field.name))]
        for field in fields(assumptions)
    ]
    rows += [
        ["food per King", str(FOOD_PER_KING)],
        ["Kings per tile of tower range", str(RANGE_KINGS)],
        ["lane length (tiles)", str(inputs.lane_tiles)],
        ["land trade route (tiles)", f"{inputs.land_route:.0f}"],
        ["water trade route (tiles)", f"{inputs.water_route:.0f}"],
        ["scheduled run (minutes)", f"{inputs.minutes:.1f}"],
        ["stock data", f"{stock.source.version}, {stock.source.file}, {stock.source.sha256[:12]}"],
    ]
    return (
        "The data files give the towers, enemies and technologies; these settings and constants "
        f"fill the gaps. Values in Kings use the shop's prices and the {level_name(inputs)} King "
        "price, the level every competitive game plays. The trade gold per trip is an estimate "
        "until it is timed on the game map.\n\n" + table(["Setting", "Value"], rows)
    )


def towers_section(inputs: Inputs) -> str:
    stock, balance = inputs.stock, inputs.balance
    ladder = attack_ladder(inputs.shop)
    levels = [0] + [step.attack for step in ladder]
    headers = ["Tower", "HP", "Attack", "Reload", "Range", "Cost"] + [
        f"DPS +{level}" for level in levels
    ]
    rows: list[list[str]] = []
    for name in (*balance.towers.members, balance.towers.special):
        unit = stock.unit(name)
        bonus = balance.towers.special_pierce if name == balance.towers.special else 0
        cost = ", ".join(f"{amount} {resource}" for resource, amount in sorted(unit.cost.items()))
        bought = [0 if name == balance.towers.special else level for level in levels]
        rows.append(
            [
                display_name(name),
                str(unit.hit_points),
                f"{unit.attack(PIERCE_CLASS) + bonus:.0f}",
                f"{unit.reload:g}",
                f"{unit.range:g}",
                cost,
            ]
            + [f"{tower_dps(unit, bonus + level, 2):.0f}" for level in bought]
        )
    return (
        "Damage per second against 2 pierce armor (the knight line), at each cumulative tower "
        "attack purchase; the Accursed Towers take no attack purchases.\n\n" + table(headers, rows)
    )


def waves_section(inputs: Inputs) -> str:
    needs = wave_needs(inputs)
    rows = [
        [
            str(index),
            need.key,
            str(need.enemies),
            str(need.hit_points),
            f"{need.pierce_armor:g}",
            str(need.total_hit_points),
            str(need.spawn_seconds),
            f"{need.speed:g}",
            f"{need.crossing_seconds:.0f}",
            f"{need.required_dps:.0f}",
        ]
        for index, need in enumerate(needs, 1)
    ]
    return (
        f"{level_name(inputs)} hit points. Each enemy crosses the lane at its own speed; the "
        "required damage per second kills the whole wave before its last enemy reaches the "
        "exit.\n\n"
        + table(
            [
                "#",
                "Wave",
                "Enemies",
                "HP",
                "Pierce armor",
                "Total HP",
                "Spawn s",
                "Speed",
                "Crossing s",
                "DPS needed",
            ],
            rows,
        )
    )


def pressure_section(inputs: Inputs, assumptions: Assumptions) -> str:
    levels = inputs.balance.difficulty.levels
    others = [index for index in range(len(levels)) if index != inputs.level]
    elsewhere = [lane_pressure(inputs, assumptions, index) for index in others]
    rows = [
        [
            str(number),
            wave.key,
            f"{wave.minutes:.1f}",
            kings(wave.kings),
            f"{wave.attack:.0f}",
            f"{wave.towers:.0f}",
            f"{wave.expected_dps:.0f}",
            f"{wave.required_dps:.0f}",
            f"{wave.ratio:.2f}",
        ]
        + [f"{pressure[number - 1].ratio:.2f}" for pressure in elsewhere]
        for number, wave in enumerate(lane_pressure(inputs, assumptions), 1)
    ]
    names = " and ".join(levels[index].name for index in others)
    return (
        "Each wave against the lane the assumptions expect at the minute it starts: the Kings "
        f"it has, the tower attack {assumptions.attack_share * 100:.0f} percent of them buy, its "
        "Watch Towers and, from minute "
        f"{assumptions.accursed_from_minute:g}, both Accursed Towers. Pressure is the damage per "
        "second the wave needs over what those towers deal; above 1 the wave leaks. The last "
        f"columns are the pressure on {names}, with their own King price and hit points.\n\n"
        + table(
            [
                "#",
                "Wave",
                "Minute",
                "Kings",
                "Attack",
                "Towers",
                "Expected DPS",
                "DPS needed",
                "Pressure",
                *(levels[index].name for index in others),
            ],
            rows,
        )
    )


def purchase_worth(purchase: Purchase) -> str:
    effect = purchase.effect
    if isinstance(effect, TowerAttack):
        return f"{effect.amount / purchase.kings:.1f} attack per King"
    if isinstance(effect, ResourceGrant):
        return f"{effect.amount / purchase.kings:.0f} {effect.resource} per King"
    if isinstance(effect, SiegePowerUp):
        return f"plus {effect.kings_per_rival} per rival"
    if isinstance(effect, Investment):
        return f"{effect.amount} {effect.pays} every {effect.period} s"
    return "-"


def shop_section(inputs: Inputs) -> str:
    exchange = rates(inputs)
    rows = [
        [purchase.name, str(purchase.kings), purchase_worth(purchase)]
        for purchase in inputs.shop.purchases
    ]
    return (
        f"A King buys {exchange.stone_per_king:.0f} stone or {exchange.wood_per_king:.0f} wood, "
        f"and {exchange.gold_per_king:.0f} gold makes one; the attack ladder sells a point of "
        f"tower attack for {exchange.kings_per_attack:.3f} Kings on average.\n\n"
        + table(["Purchase", "Kings", "Worth"], rows)
    )


def investments_section(inputs: Inputs) -> str:
    rows = [
        [
            r.name,
            str(r.kings),
            kings(r.kings_per_minute),
            f"{r.payback_minutes:.0f}",
            kings(r.run_value),
            kings(r.half_run_value),
            kings(r.run_value - r.kings),
        ]
        for r in investment_returns(inputs)
    ]
    return (
        "What each investment pays in Kings per minute, how long it takes to pay for itself, "
        "and what it returns over the scheduled run when bought at the start or halfway.\n\n"
        + table(
            ["Investment", "Kings", "Kings/min", "Payback min", "Run", "Half run", "Net at start"],
            rows,
        )
    )


def income_section(inputs: Inputs, assumptions: Assumptions) -> str:
    income = baseline_income(inputs, assumptions)
    rows = [
        ["Waves cleared", kings(income.wave_kings), ""],
        [
            "Kill rewards",
            kings(income.kill_kings),
            f"{income.rewards} rewards: {income.kill_stone} stone, {income.kill_wood} wood",
        ],
        ["Trade", "", f"{income.trade_gold_per_minute:.0f} gold/min"],
        ["Relics", "", f"{income.relic_gold_per_minute:.0f} gold/min"],
        [
            "Mining",
            "",
            f"{income.mining_gold_per_minute:.0f} gold/min, "
            f"{income.mining_stone_per_minute:.0f} stone/min",
        ],
        [
            "Gold converted",
            kings(income.gold_kings),
            f"{income.gold_per_minute:.0f} gold/min in all",
        ],
        ["Total", kings(income.total_kings), f"over {income.minutes:.1f} minutes"],
    ]
    return (
        f"Kings one lane earns over the scheduled run on {level_name(inputs)} without buying "
        "anything.\n\n" + table(["Source", "Kings", "Detail"], rows)
    )


def civilizations_section(inputs: Inputs, assumptions: Assumptions) -> str:
    values = profile_table(inputs, assumptions)
    rows: list[list[str]] = []
    for civilization in inputs.profiles.civilizations:
        found = inputs.stock.find(civilization.id)
        if found is None:
            lacks = "not in the stock snapshot"
        else:
            lacks = ", ".join(
                sorted(
                    display_name(name)
                    for name in found.lacks
                    if name in ("GUARD_TOWER", "KEEP", "BOMBARD_TOWER")
                )
            )
        worth = values[civilization.name]
        native = kings(worth.native.solo)
        if worth.native.pvp:
            native += f" +{kings(worth.native.pvp)}"
        rows.append(
            [
                civilization.name,
                lacks or "-",
                ", ".join(adjustments(civilization.profile, inputs.profiles.purchase_names)) or "-",
                kings(worth.profile.solo),
                native,
                kings(worth.solo),
                kings(worth.pvp),
            ]
        )
    default = values[DEFAULT_NAME]
    rows.append(
        [
            DEFAULT_NAME,
            "-",
            ", ".join(adjustments(inputs.profiles.default, inputs.profiles.purchase_names)) or "-",
            kings(default.profile.solo),
            kings(0),
            kings(default.solo),
            kings(default.pvp),
        ]
    )
    return (
        "Each profile's adjustments and their worth in Kings over a run (Solo), the content's "
        "estimate of what the civilization's own bonuses are worth here (Native, with the "
        "extra with PvP on after a plus), and the two together solo and with PvP on. The "
        "towers column lists the towers the civilization's own technology tree lacks; a flat "
        "attack bonus is priced at the smallest rung of its family's attack ladder.\n\n"
        + table(["Civilization", "Lacks", "Profile", "Solo", "Native", "Total", "PvP"], rows)
    )


def rivals_section(inputs: Inputs) -> str:
    rivals = rivalry(inputs)
    rows = [[str(row.players), str(row.siege_price), str(row.trebuchets)] for row in rivals]
    first = rivals[0]
    land, naval = display_name(first.land_raider).lower(), display_name(first.naval_raider).lower()
    return (
        f"A {land} raider kills a trade cart in {first.cart_seconds:.0f} seconds and a "
        f"{naval} a trade cog in {first.cog_seconds:.0f}; a lost trader costs "
        f"{first.trader_replacement_kings:.2f} Kings to replace. Each rival's trebuchets deal "
        f"{first.siege_damage_per_rival:.0f} damage in the siege's "
        f"{inputs.balance.interaction.siege.active_seconds} seconds if every shot lands: "
        f"{first.watch_towers_per_rival:.1f} Watch Towers or {first.keeps_per_rival:.1f} Keeps, "
        f"{kings(first.rebuild_kings_per_rival)} Kings of stone and wood to rebuild.\n\n"
        + table(["Players", "Siege price", "Trebuchets"], rows)
    )


def render_report(inputs: Inputs, assumptions: Assumptions) -> str:
    sections = [
        ("Assumptions", assumptions_section(inputs, assumptions)),
        ("Towers", towers_section(inputs)),
        ("Waves", waves_section(inputs)),
        ("Pressure", pressure_section(inputs, assumptions)),
        ("Shop", shop_section(inputs)),
        ("Investments", investments_section(inputs)),
        ("Income", income_section(inputs, assumptions)),
        ("Civilizations", civilizations_section(inputs, assumptions)),
        ("Rivals", rivals_section(inputs)),
    ]
    body = "\n\n".join(f"## {title}\n\n{text}" for title, text in sections)
    return (
        f"{REPORT_TITLE}\n\n"
        "Generated by `uv run ancienttdde balance` from the content and the stock data "
        "snapshot; `tests/test_game_balance.py` keeps this copy current.\n\n" + body + "\n"
    )
