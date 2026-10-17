"""The balance model: tower damage, wave demands, King income, investments, profiles, rivals."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.game.catalog import Investment, TowerAttack

ROOT = Path(__file__).resolve().parents[1]
PIERCE = 3


def inputs():
    from ancienttdde.game.balance import load_inputs

    return load_inputs(ROOT)


def test_damage_follows_the_armor_rule_with_a_minimum_of_one() -> None:
    from ancienttdde.game.balance import damage_per_hit, tower_dps

    assert damage_per_hit(5, 1) == 4 and damage_per_hit(2, 3) == 1
    watch = inputs().stock.unit("WATCH_TOWER")
    # 5 pierce attack every 2 seconds against 1 pierce armor.
    assert tower_dps(watch, 0, 1) == 2.0
    assert tower_dps(watch, 750, 3) == (5 + 750 - 3) / 2


def test_the_attack_ladder_prices_each_point_of_tower_attack() -> None:
    from ancienttdde.game.balance import attack_ladder, rates

    ladder = attack_ladder(inputs().shop)
    assert [step.purchase.key for step in ladder][:2] == ["tower_attack_4", "tower_attack_10"]
    amounts = [step.purchase.effect for step in ladder]
    assert ladder[-1].attack == sum(
        effect.amount for effect in amounts if isinstance(effect, TowerAttack)
    )
    assert all(isinstance(effect, TowerAttack) for effect in amounts)
    assert ladder[-1].kings == sum(step.purchase.kings for step in ladder)
    exchange = rates(inputs())
    assert exchange.kings_per_attack == pytest.approx(ladder[-1].kings / ladder[-1].attack)
    assert (exchange.stone_per_king, exchange.wood_per_king) == (1500, 2000)
    assert exchange.gold_per_king == inputs().balance.difficulty.level("normal").king_gold


def test_each_wave_states_the_damage_a_lane_must_deal() -> None:
    from ancienttdde.game.balance import wave_needs

    needs = wave_needs(inputs())
    balance = inputs().balance
    assert len(needs) == len(balance.waves)
    first = needs[0]
    assert (first.key, first.enemies, first.pierce_armor) == ("Villagers", 30, 0)
    assert first.hit_points == balance.hit_points(0, balance.difficulty.index("normal"))
    assert first.total_hit_points == 30 * first.hit_points
    # Enemies spawn for the batch window, then walk the lane at their own speed.
    assert first.spawn_seconds == (balance.waves[0].batches - 1) * balance.waves[0].interval
    assert first.required_dps == pytest.approx(
        first.total_hit_points / (first.spawn_seconds + first.crossing_seconds)
    )
    assert needs[-1].required_dps > needs[0].required_dps * 20
    # The schedule's own armor replaces the unit's in the demand table. The rams keep theirs.
    nobunaga = next(need for need in needs if need.unit == "NOBUNAGA")
    assert nobunaga.pierce_armor == inputs().stock.unit("NOBUNAGA").armor(PIERCE) + 10
    rams = next(need for need in needs if need.unit == "SIEGE_RAM")
    assert rams.pierce_armor == inputs().stock.unit("SIEGE_RAM").armor(PIERCE) == 195
    # Each boss needs more damage per second than the last, whatever its speed, and none
    # more than the reservoir can refill: the script tops a boss up once a second to the
    # 32,767 the attribute holds, so a lane dealing more than that in a second kills it with
    # the reservoir unspent.
    bosses = [need.required_dps for need in needs if need.enemies == 1]
    assert len(bosses) == 10 and bosses == sorted(set(bosses))
    for level in range(len(balance.difficulty.levels)):
        assert max(n.required_dps for n in wave_needs(inputs(), level) if n.enemies == 1) <= 30000


def test_crossing_time_uses_each_enemys_own_speed() -> None:
    from ancienttdde.game.balance import wave_needs

    needs = wave_needs(inputs())
    first = needs[0]
    assert first.unit == "VILLAGER_MALE" and first.speed == 0.8
    assert first.crossing_seconds == pytest.approx(48 / 0.8)
    knights = next(need for need in needs if need.unit == "KNIGHT")
    assert knights.crossing_seconds == pytest.approx(48 / 1.35)


def test_attack_follows_the_ladder_and_its_last_rung_repeats() -> None:
    from ancienttdde.game.balance import attack_ladder, ladder_attack

    ladder = attack_ladder(inputs().shop)
    assert ladder_attack(ladder, 0) == 0
    assert ladder_attack(ladder, ladder[0].kings) == ladder[0].attack
    halfway = (ladder[1].kings + ladder[2].kings) / 2
    middle = (ladder[1].attack + ladder[2].attack) / 2
    assert ladder_attack(ladder, halfway) == pytest.approx(middle)
    # The rungs can be bought again, so past the last one its price per point carries on.
    last = ladder[-1]
    effect = last.purchase.effect
    assert isinstance(effect, TowerAttack)
    assert ladder_attack(ladder, last.kings + last.purchase.kings) == pytest.approx(
        last.attack + effect.amount
    )


def test_lane_pressure_follows_the_schedule_the_income_and_the_ladder() -> None:
    from ancienttdde.game.balance import (
        Assumptions,
        attack_ladder,
        baseline_income,
        ladder_attack,
        lane_pressure,
        tower_dps,
        wave_needs,
    )

    data, assumptions = inputs(), Assumptions()
    balance, economy = data.balance, data.balance.economy
    pressure = lane_pressure(data, assumptions)
    needs = wave_needs(data)
    assert [p.key for p in pressure] == [w.key for w in balance.waves]
    # The first wave starts after the choice window and the preparation. Each next one after
    # the wave before it and an intermission.
    first = pressure[0]
    assert first.minutes == pytest.approx(
        (balance.choice_seconds + balance.preparation_seconds) / 60
    )
    assert pressure[1].minutes - first.minutes == pytest.approx(
        (balance.waves[0].duration + balance.intermission_seconds) / 60
    )
    # Towers grow from the first wave's count to the finale's and stay there.
    assert first.towers == assumptions.towers_at_first_wave
    assert pressure[-1].towers == assumptions.towers_at_finale
    assert all(a.towers <= b.towers for a, b in zip(pressure, pressure[1:], strict=False))
    # Kings: the starting ones and everything earned so far, grown by what investments return.
    gold = baseline_income(data, assumptions).gold_per_minute
    king_gold = balance.difficulty.levels[data.level].king_gold
    for index in (0, 10, 45):
        wave = pressure[index]
        kills = sum(w.enemies for w in balance.waves[:index])
        earned = (
            index * economy.wave_kings
            + gold * wave.minutes / king_gold
            + kills // economy.kills_per_reward // economy.rewards_per_king
        )
        share = min(1.0, wave.minutes / assumptions.investment_minutes)
        growth = 1 + (assumptions.investment_return - 1) * share
        assert wave.kings == pytest.approx(assumptions.starting_kings + growth * earned)
        # The ladder's attack for the lane's share of its Kings, plus what the attack
        # investments have paid since the minutes the lane bought them.
        bonus = 0.0
        for key, minute in assumptions.attack_investments:
            effect = data.shop.get(key).effect
            assert isinstance(effect, Investment)
            if wave.minutes >= minute:
                bonus += effect.amount * 60 / effect.period * (wave.minutes - minute)
        ladder = ladder_attack(attack_ladder(data.shop), assumptions.attack_share * wave.kings)
        assert wave.attack == pytest.approx(ladder + bonus)
    assert pressure[0].attack == pytest.approx(
        ladder_attack(attack_ladder(data.shop), assumptions.attack_share * pressure[0].kings)
    )
    assert pressure[45].attack > ladder_attack(
        attack_ladder(data.shop), assumptions.attack_share * pressure[45].kings
    )
    # What the towers deal against the wave's armor, with both Accursed Towers once bought.
    watch = data.stock.unit("WATCH_TOWER")
    accursed = data.stock.unit(balance.towers.special)
    for wave, need in zip(pressure, needs, strict=True):
        expected = wave.towers * tower_dps(watch, wave.attack, need.pierce_armor)
        if wave.minutes >= assumptions.accursed_from_minute:
            expected += 2 * tower_dps(accursed, balance.towers.special_pierce, need.pierce_armor)
        assert wave.expected_dps == pytest.approx(expected)
        assert wave.required_dps == need.required_dps
        assert wave.ratio == pytest.approx(need.required_dps / expected)


# The original's tiers: five waves each, with 10-A grouped into the last regular tier and
# the ten bosses as the last. Each tier's hit points step up at its first wave, so the curve
# is a staircase.
TIERS = (
    (1, 5),
    (6, 10),
    (11, 15),
    (16, 20),
    (21, 25),
    (26, 30),
    (31, 35),
    (36, 40),
    (41, 46),
    (47, 56),
)
# Target pressure per tier on Normal. The DE run, not this test, calibrates the curve. The
# opening villager wave is tuned by playtest, and the rams sit below their tier's band with
# their full armor. From tier 6 the targets run above 1 on every level: a played lane
# outgrows the lane the assumptions expect by then.
BANDS = (
    (2, 5, 0.45, 0.7),
    (6, 10, 0.8, 1.0),
    (11, 15, 0.85, 1.1),
    (16, 20, 0.9, 1.15),
    (21, 25, 0.95, 1.2),
    (26, 30, 1.35, 1.65),
    (31, 35, 1.35, 1.65),
    (36, 40, 1.2, 1.6),
    (41, 46, 1.1, 1.55),
    (47, 56, 1.15, 1.45),
)
# Ceilings on Hard by tier, from playtests on Hardest: the first two keep a lane with few
# Kings pressed, not smothered.
HARD_CEILINGS = (
    (2, 5, 0.75),
    (6, 10, 1.15),
    (11, 25, 1.4),
    (26, 46, 2.0),
)


def test_each_wave_presses_the_expected_lane_within_its_tiers_band() -> None:
    from ancienttdde.game.balance import Assumptions, lane_pressure

    data = inputs()
    pressure = lane_pressure(data, Assumptions())
    assert 0.2 <= pressure[0].ratio <= 0.4
    rams = {wave.key for wave in data.balance.waves if wave.unit == "SIEGE_RAM"}
    for first, last, low, high in BANDS:
        for wave in pressure[first - 1 : last]:
            if wave.key in rams:
                continue
            assert low <= wave.ratio <= high, (wave.key, wave.ratio)
    bosses = [wave.ratio for wave in pressure[46:]]
    assert all(later >= earlier - 0.05 for earlier, later in zip(bosses, bosses[1:], strict=False))


def test_each_tier_opens_harder_than_the_last_one_ended() -> None:
    """The first wave of a tier presses harder than the last wave of the tier before it by a
    step a player notices, on Normal and on Hard."""
    from ancienttdde.game.balance import Assumptions, lane_pressure

    data = inputs()
    for level in (data.balance.difficulty.index("normal"), data.balance.difficulty.index("hard")):
        pressure = lane_pressure(data, Assumptions(), level)
        for (_, last), (first, _) in zip(TIERS, TIERS[1:], strict=False):
            opener, closer = pressure[first - 1], pressure[last - 1]
            assert opener.ratio >= closer.ratio + 0.05, (level, opener.key, closer.key)


def test_hard_presses_harder_than_normal_on_every_wave() -> None:
    """Hard has dearer Kings and more hit points: every wave presses at least a tenth harder
    than on Normal, the opening stays an opening, every tier stays under its playtested
    ceiling, and the bosses need more than the expected lane has."""
    from ancienttdde.game.balance import Assumptions, lane_pressure

    data = inputs()
    normal = lane_pressure(data, Assumptions())
    hard = lane_pressure(data, Assumptions(), data.balance.difficulty.index("hard"))
    assert all(h.ratio >= 1.1 * n.ratio for h, n in zip(hard, normal, strict=True))
    assert hard[0].ratio <= 0.45
    for first, last, high in HARD_CEILINGS:
        for wave in hard[first - 1 : last]:
            assert wave.ratio <= high, (wave.key, wave.ratio)
    assert all(1.0 < wave.ratio <= 1.6 for wave in hard[46:])


def test_easy_stays_below_normal_and_holds_the_early_tiers() -> None:
    """Easy has cheaper Kings and fewer hit points: every wave presses at most four fifths
    as hard as on Normal, and the expected lane holds the first five tiers."""
    from ancienttdde.game.balance import Assumptions, lane_pressure

    data = inputs()
    normal = lane_pressure(data, Assumptions())
    easy = lane_pressure(data, Assumptions(), data.balance.difficulty.index("easy"))
    assert all(e.ratio <= 0.8 * n.ratio for e, n in zip(easy, normal, strict=True))
    assert all(wave.ratio <= 0.95 for wave in easy[:25])


def test_investment_attack_pays_from_each_purchase_minute() -> None:
    from dataclasses import replace

    from ancienttdde.game.balance import Assumptions, attack_investments, investment_attack
    from ancienttdde.game.catalog import Investment, Shop

    data, assumptions = inputs(), Assumptions()
    bought = attack_investments(data, assumptions)
    assert [minute for _, minute in bought] == [15.0, 24.0, 32.0]
    assert investment_attack(bought, 14.9) == 0.0
    # At minute 40: +1/30 s for 25 minutes, +3/30 s for 16 and +1/5 s for 8.
    assert investment_attack(bought, 40.0) == pytest.approx(50 + 96 + 96)
    with pytest.raises(ValueError, match="attack investment"):
        attack_investments(data, Assumptions(attack_investments=(("gold_1000", 1.0),)))
    # The pressure model adds the attack to the towers' family, so no other family counts.
    purchase = data.shop.get("attack_1_every_30")
    effect = purchase.effect
    assert isinstance(effect, Investment)
    bombard = replace(purchase, key="bombard_1_every_30", effect=replace(effect, family="bombard"))
    other = replace(data, shop=Shop((*data.shop.purchases, bombard)))
    with pytest.raises(ValueError, match="attack investment"):
        attack_investments(other, Assumptions(attack_investments=(("bombard_1_every_30", 1.0),)))


def test_baseline_income_counts_every_source_of_kings() -> None:
    from ancienttdde.game.balance import Assumptions, baseline_income

    income = baseline_income(inputs(), Assumptions())
    balance = inputs().balance
    assert income.wave_kings == len(balance.waves) * balance.economy.wave_kings
    kills = sum(w.count * w.batches for w in balance.waves)
    rewards = kills // balance.economy.kills_per_reward
    assert income.kill_kings == rewards // balance.economy.rewards_per_king
    assert income.kill_stone == rewards * balance.economy.kill_stone
    assert income.trade_gold_per_minute > 0 and income.relic_gold_per_minute == 60
    assert income.gold_kings == pytest.approx(
        income.gold_per_minute
        * income.minutes
        / inputs().balance.difficulty.level("normal").king_gold
    )
    assert income.total_kings == pytest.approx(
        income.wave_kings + income.kill_kings + income.gold_kings
    )


def test_income_report_prices_a_trained_trader() -> None:
    from ancienttdde.game.balance import Assumptions, rates, trader_kings
    from ancienttdde.game.report import income_section

    data = inputs()
    exchange = rates(data)
    text = income_section(data, Assumptions())
    cost = exchange.cost_kings(data.stock.unit("TRADE_CART_EMPTY").cost)
    cart = trader_kings("land", 1, data, Assumptions(), exchange)
    cog = trader_kings("water", 1, data, Assumptions(), exchange)
    assert (
        f"A trade cart trained at the market costs {cost:.2f} Kings and a point of room and "
        f"brings {cart:.1f} Kings over the run on the lane's route, a trade cog {cog:.1f}. The "
        "lane the waves are tuned against trains none." in text
    )


def test_investments_report_their_payback_within_the_run() -> None:
    from ancienttdde.game.balance import investment_returns

    returns = {r.key: r for r in investment_returns(inputs())}
    gold = returns["gold_1000"]
    assert gold.kings == inputs().shop.get("gold_1000").kings
    assert gold.kings_per_minute == pytest.approx(
        1000 / 2 / inputs().balance.difficulty.level("normal").king_gold
    )
    assert gold.payback_minutes == pytest.approx(gold.kings / gold.kings_per_minute)
    minutes = returns["king_every_minute"]
    assert minutes.kings_per_minute == pytest.approx(1.0)
    assert minutes.run_value == pytest.approx(
        minutes.kings_per_minute * returns["king_every_minute"].run_minutes
    )
    attack = returns["attack_1_every_5"]
    assert attack.kings_per_minute > 0


def test_every_investment_pays_for_itself_within_most_of_the_run() -> None:
    from ancienttdde.game.balance import investment_returns

    returns = investment_returns(inputs())
    run = inputs().minutes
    for investment in returns:
        # Bought at the start, every investment returns at least half as much again. Bought
        # halfway, none of them is a plain loss by more than a King.
        assert investment.payback_minutes <= run * 0.6, investment.key
        assert investment.run_value >= investment.kings * 1.5, investment.key
        assert investment.half_run_value >= investment.kings - 1, investment.key


def test_profile_values_score_solo_and_pvp_worth_in_kings() -> None:
    from ancienttdde.game.balance import Assumptions, profile_value, rates
    from ancienttdde.game.civilizations import Profile
    from ancienttdde.game.config import Resources

    exchange = rates(inputs())
    data = inputs()
    neutral = profile_value(Profile(), data, Assumptions())
    assert (neutral.solo, neutral.pvp) == (0.0, 0.0)
    kings = profile_value(Profile(kings=2), data, Assumptions())
    assert kings.solo == 2.0 and kings.pvp == 2.0
    stone = profile_value(Profile(resources=Resources(0, 0, 1500, 0)), data, Assumptions())
    assert stone.solo == pytest.approx(1500 / exchange.stone_per_king)
    attack = profile_value(Profile(attack=(("towers", 10),)), data, Assumptions())
    four = data.shop.get("tower_attack_4")
    assert attack.solo == pytest.approx(10 * four.kings / 4)
    raiders = profile_value(Profile(raiders=(("land", 1),)), data, Assumptions())
    assert raiders.solo == 0.0 and raiders.pvp > 0
    hit_points = profile_value(Profile(tower_hit_points=300), data, Assumptions())
    assert hit_points.solo == 0.0 and hit_points.pvp > 0
    # More hit points on every tower spare that share of the typical siege, one row's
    # trebuchets for the siege against a Keep, at the hit point rate.
    from ancienttdde.game.balance import siege_kings

    keep = data.stock.unit("KEEP").hit_points
    assert siege_kings(data, Assumptions()) == pytest.approx(2 * 6 * (200 + 250 - 9) * 0.0005)
    assert hit_points.pvp == pytest.approx(
        (1 - keep / (keep + 300)) * siege_kings(data, Assumptions())
    )
    discount = profile_value(Profile(king_gold_percent=80), data, Assumptions())
    assert discount.solo > 0 and discount.pvp == discount.solo
    # A granted purchase is worth its price, an investment what it pays over the run, and a
    # castle its population plus the building.
    age = profile_value(Profile(purchases=("castle_age",)), data, Assumptions())
    assert age.solo == data.shop.get("castle_age").kings
    from ancienttdde.game.balance import investment_returns

    paid = {r.key: r for r in investment_returns(data)}
    gold = profile_value(Profile(purchases=("gold_175",)), data, Assumptions())
    assert gold.solo == pytest.approx(paid["gold_175"].run_value)
    castle = profile_value(Profile(purchases=("castle",)), data, Assumptions())
    assert castle.solo == pytest.approx(1.0 + 20 * Assumptions().population_kings)


def test_rivalry_prices_the_siege_flat_and_counts_every_islet_row() -> None:
    from ancienttdde.game.balance import rates, rivalry

    model = rivalry(inputs())
    siege = inputs().shop.get("siege")
    assert model.siege_price == siege.kings == 20
    # Two trebuchets on each of the eight islet rows, whoever plays.
    assert model.trebuchets == 16
    # A lane can take fire from the rows on both sides: four trebuchets for a minute at a
    # ten-second reload, six shots each, 450 against buildings, when all fire at it.
    assert model.flanking == 4
    assert model.siege_damage_per_lane == pytest.approx(model.flanking * 6 * (200 + 250 - 9))
    assert model.watch_towers_per_lane > 0 and model.rebuild_kings_per_lane > 0
    assert model.cart_seconds == pytest.approx(70 / (7 / 2))
    # A lost cart is retrained at the market for its stock cost, cheaper than the shop's third
    # of a King.
    cart = inputs().stock.unit("TRADE_CART_EMPTY")
    market = rates(inputs()).cost_kings(cart.cost)
    assert 0 < market < 1 / 3
    assert model.cog_seconds > 0 and model.trader_replacement_kings == pytest.approx(market)


def test_rivalry_names_a_missing_siege_or_trader_purchase(tmp_path: Path) -> None:
    import json
    import shutil

    from ancienttdde.game.balance import load_inputs, rivalry

    root = tmp_path / "project"
    for relative in ("content/balance", "content/maps"):
        (root / relative).mkdir(parents=True)
    for name in ("game.json", "shop.json", "civilizations.json", "stock.json"):
        shutil.copy(ROOT / "content/balance" / name, root / "content/balance" / name)
    shutil.copy(ROOT / "content/maps/foundation.json", root / "content/maps/foundation.json")
    shop = json.loads((root / "content/balance/shop.json").read_text())
    shop["purchases"] = [p for p in shop["purchases"] if p["effect"]["kind"] != "siege"]
    (root / "content/balance/shop.json").write_text(json.dumps(shop))
    with pytest.raises(ValueError, match="siege"):
        rivalry(load_inputs(root))


def test_the_report_has_every_section_and_the_versioned_copy_is_current() -> None:
    from ancienttdde.game.balance import Assumptions
    from ancienttdde.game.report import render_report

    text = render_report(inputs(), Assumptions())
    for heading in (
        "# Balance tables",
        "## Assumptions",
        "## Towers",
        "## Waves",
        "## Pressure",
        "## Shop",
        "## Investments",
        "## Income",
        "## Civilizations",
        "## Rivals",
    ):
        assert heading in text
    assert "| Koreans |" in text and "| Any other civilization |" in text
    assert "| Civilization | Lacks | Profile | Solo | Native | Total | PvP |" in text
    assert "| Teutons | - | " in text and "| 0.2 +0.9 | " in text
    from ancienttdde.game.balance import siege_kings

    assert f"{siege_kings(inputs(), Assumptions()):.2f} Kings of towers" in text
    assert "stone and wood alone" in text
    assert (
        "| attack investments | +1 attack/30 s at minute 15, +3 attack/30 s at minute 24, "
        "+1 attack/5 s at minute 32 |"
    ) in text
    assert (ROOT / "docs/balance.md").read_text(encoding="utf-8") == text


def test_balance_command_writes_the_report(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["balance", "--root", str(ROOT), "--output", str(tmp_path / "balance")]
    )
    assert result.exit_code == 0, result.output
    assert (
        (tmp_path / "balance/balance.md").read_text(encoding="utf-8").startswith("# Balance tables")
    )
    assert "balance.md" in result.output


def test_balance_command_fails_cleanly_without_content(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["balance", "--root", str(tmp_path)])
    assert result.exit_code == 1
    assert "game.json" in result.output


def copy_content(tmp_path: Path) -> Path:
    import shutil

    root = tmp_path / "project"
    for relative in ("content/balance", "content/maps"):
        (root / relative).mkdir(parents=True)
    for name in ("game.json", "shop.json", "civilizations.json", "stock.json"):
        shutil.copy(ROOT / "content/balance" / name, root / "content/balance" / name)
    shutil.copy(ROOT / "content/maps/foundation.json", root / "content/maps/foundation.json")
    return root


def test_granted_traders_and_relics_are_worth_the_same_as_the_settings() -> None:
    from ancienttdde.game.balance import Assumptions, profile_value
    from ancienttdde.game.civilizations import Profile

    data = inputs()
    sites = data.lanes[0].sites
    cogs = profile_value(Profile(purchases=("trade_cogs",)), data, Assumptions())
    assert cogs.solo == pytest.approx(
        profile_value(Profile(traders=(("water", len(sites.cogs)),)), data, Assumptions()).solo
    )
    carts = profile_value(Profile(purchases=("trade_carts",)), data, Assumptions())
    assert carts.solo == pytest.approx(
        profile_value(Profile(traders=(("land", len(sites.carts)),)), data, Assumptions()).solo
    )
    relics = profile_value(Profile(purchases=("relics",)), data, Assumptions())
    assert relics.solo == pytest.approx(
        profile_value(Profile(relics=len(sites.relics)), data, Assumptions()).solo
    )
    assert cogs.solo > data.shop.get("trade_cogs").kings


def test_flat_attack_is_worth_the_cheapest_rung_of_its_family() -> None:
    from ancienttdde.game.balance import Assumptions, profile_value, rates, technology_kings
    from ancienttdde.game.civilizations import Profile

    data = inputs()
    four = data.shop.get("tower_attack_4")
    assert profile_value(Profile(attack=(("towers", 4),)), data, Assumptions()).solo == four.kings
    assert profile_value(
        Profile(attack=(("towers", 2),)), data, Assumptions()
    ).solo == pytest.approx(2 * four.kings / 4)
    bombard = data.shop.get("bombard_attack_400")
    assert profile_value(
        Profile(attack=(("bombard", 40),)), data, Assumptions()
    ).solo == pytest.approx(40 * bombard.kings / 400)
    exchange = rates(data)
    fletching = data.stock.technology("FLETCHING")
    assert technology_kings("FLETCHING", data, exchange) == pytest.approx(
        exchange.cost_kings(fletching.cost)
        + fletching.towers.attack * four.kings / 4
        + fletching.towers.range * 0.25
    )


def test_a_king_discount_is_worth_the_extra_kings_the_same_gold_makes() -> None:
    from ancienttdde.game.balance import Assumptions, baseline_income, profile_value
    from ancienttdde.game.civilizations import Profile

    data = inputs()
    income = baseline_income(data, Assumptions())
    discount = profile_value(Profile(king_gold_percent=80), data, Assumptions())
    assert discount.solo == pytest.approx(income.gold_kings * (100 / 80 - 1))
    premium = profile_value(Profile(king_gold_percent=125), data, Assumptions())
    assert premium.solo == pytest.approx(-income.gold_kings / 5)


def test_the_report_names_the_default_level_and_copes_with_new_civilizations(
    tmp_path: Path,
) -> None:
    import json

    from ancienttdde.game.balance import Assumptions, load_inputs
    from ancienttdde.game.report import render_report

    root = copy_content(tmp_path)
    game = json.loads((root / "content/balance/game.json").read_text())
    game["difficulty"]["default"] = "hard"
    (root / "content/balance/game.json").write_text(json.dumps(game))
    civilizations = json.loads((root / "content/balance/civilizations.json").read_text())
    civilizations["civilizations"].append(
        {"key": "ATLANTEANS", "id": 70, "identity": "", "profile": {"kings": 1}}
    )
    (root / "content/balance/civilizations.json").write_text(json.dumps(civilizations))
    text = render_report(load_inputs(root), Assumptions())
    assert "Hard hit points." in text and "on Hard without buying anything" in text
    assert (
        "the Hard King price, the default level. On Easy and Normal, a bonus paid in gold is "
        "worth a different number of Kings and a bonus in Kings the same." in text
    )
    # Priced at the default level, apart from the pressure on the other levels.
    pressure = text.split("## Pressure")[1].split("## Shop")[0]
    assert "The last columns are the pressure on Easy and Normal" in pressure
    assert "| Pressure | Easy | Normal |" in pressure
    assert "Normal" not in text.split("## Waves")[1].split("## Pressure")[0]
    assert "Normal" not in text.split("## Shop")[1].split("## Civilizations")[0]
    row = "| Atlanteans | not in the stock snapshot | +1 starting King | 1.0 | 0.0 | 1.0 | 1.0 |"
    assert row in text


def test_balance_command_keeps_its_output_out_of_the_sources(tmp_path: Path) -> None:
    root = copy_content(tmp_path)
    for destination in (root, root / "content", root.parent, root / "docs"):
        result = CliRunner().invoke(
            app, ["balance", "--root", str(root), "--output", str(destination)]
        )
        assert result.exit_code == 1, destination
        assert "outside source directories" in result.output, destination
        assert not (destination / "balance.md").exists()


def test_balance_command_does_not_replace_an_unrelated_file(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "balance.md").write_text("# My own notes\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["balance", "--root", str(ROOT), "--output", str(notes)])
    assert result.exit_code == 1 and "unrelated" in result.output
    assert (notes / "balance.md").read_text(encoding="utf-8") == "# My own notes\n"
    # Its own earlier report is replaced.
    (notes / "balance.md").write_text("# Balance tables\n\nstale\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["balance", "--root", str(ROOT), "--output", str(notes)])
    assert result.exit_code == 0, result.output
    assert "stale" not in (notes / "balance.md").read_text(encoding="utf-8")


def test_a_civilizations_worth_adds_its_native_bonuses_to_its_profile() -> None:
    from ancienttdde.game.balance import Assumptions, civilization_value, profile_table
    from ancienttdde.game.civilizations import Civilization, NativeWorth, Profile

    data = inputs()
    plain = Civilization("PLAIN", 100, "", Profile(kings=1), NativeWorth(solo=0.5, pvp=0.3))
    worth = civilization_value(plain, data, Assumptions())
    assert (worth.profile.solo, worth.profile.pvp) == (1.0, 1.0)
    assert worth.solo == pytest.approx(1.5) and worth.pvp == pytest.approx(1.8)
    table = profile_table(data, Assumptions())
    teutons = table["Teutons"]
    assert teutons.native.solo == 1.0 and teutons.solo == pytest.approx(teutons.profile.solo + 1.0)
    assert table["Any other civilization"].native == NativeWorth()


def test_report_tables_escape_pipes_and_line_breaks() -> None:
    from ancienttdde.game.report import table

    text = table(["A", "B"], [["one | two", "three\nfour"]])
    assert text.splitlines()[2] == "| one \\| two | three four |"
    assert all(line.replace("\\|", "").count("|") == 3 for line in text.splitlines())


def test_balance_command_refuses_a_dangling_report_link(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    target = tmp_path / "elsewhere" / "planted.md"
    target.parent.mkdir()
    (out / "balance.md").symlink_to(target)
    result = CliRunner().invoke(app, ["balance", "--root", str(ROOT), "--output", str(out)])
    assert result.exit_code == 1 and "unrelated" in result.output
    assert not target.exists()


def test_rates_refuse_a_shop_without_its_yardsticks(tmp_path: Path) -> None:
    import json

    from ancienttdde.game.balance import load_inputs, rates

    root = copy_content(tmp_path)
    original = json.loads((root / "content/balance/shop.json").read_text())
    for field, dropped, message in (
        ("key", "stone_1500", "stone"),
        ("kind", "tower_attack", "attack"),
    ):
        shop = dict(original)
        shop["purchases"] = [
            p
            for p in original["purchases"]
            if (p["key"] if field == "key" else p["effect"]["kind"]) != dropped
        ]
        (root / "content/balance/shop.json").write_text(json.dumps(shop))
        with pytest.raises(ValueError, match=message):
            rates(load_inputs(root))


def test_unwatched_profile_technologies_are_not_priced_silently() -> None:
    from ancienttdde.game.balance import rates, technology_kings

    data = inputs()
    with pytest.raises(ValueError, match="SQUIRES"):
        technology_kings("SQUIRES", data, rates(data))


def test_the_rivals_table_prices_the_configured_raiders(tmp_path: Path) -> None:
    import json

    from ancienttdde.game.balance import Assumptions, load_inputs, rivalry
    from ancienttdde.game.report import rivals_section

    root = copy_content(tmp_path)
    game = json.loads((root / "content/balance/game.json").read_text())
    game["interaction"]["raiders"]["land"].update({"unit": "HUSSAR", "line": ["HUSSAR"]})
    (root / "content/balance/game.json").write_text(json.dumps(game))
    data = load_inputs(root)
    stock = data.stock
    model = rivalry(data)
    assert model.land_raider == "HUSSAR" and model.naval_raider == "FIRE_GALLEY"
    expected = stock.unit("TRADE_CART_EMPTY").hit_points / (
        (stock.unit("HUSSAR").attack(4) - stock.unit("TRADE_CART_EMPTY").armor(4))
        / stock.unit("HUSSAR").reload
    )
    assert model.cart_seconds == pytest.approx(expected)
    text = rivals_section(data, Assumptions())
    assert "A hussar raider kills a trade cart" in text
    assert "can deal up to" in text and "splits its fire" in text


def test_a_starting_tower_is_worth_its_cost_and_its_base_damage() -> None:
    from ancienttdde.game.balance import (
        TOWER_DPS_KINGS,
        Assumptions,
        profile_value,
        rates,
        table_armor,
        tower_dps,
        tower_kings,
    )
    from ancienttdde.game.civilizations import Profile

    data = inputs()
    exchange = rates(data)
    watch = data.stock.unit("WATCH_TOWER")
    cost = exchange.cost_kings(watch.cost)
    assert cost == pytest.approx(125 / exchange.stone_per_king + 35 / exchange.wood_per_king)
    assert table_armor(data) == 2
    expected = cost + tower_dps(watch, 0, 2) * TOWER_DPS_KINGS
    assert tower_kings("WATCH_TOWER", data, exchange) == pytest.approx(expected)
    worths = [tower_kings(name, data, exchange) for name in data.balance.towers.members]
    assert worths == sorted(worths) and worths[-1] > 2 * worths[0]
    pair = profile_value(Profile(towers=(("KEEP", 2),)), data, Assumptions())
    assert pair.solo == pytest.approx(2 * tower_kings("KEEP", data, exchange))
    assert pair.pvp == pair.solo
