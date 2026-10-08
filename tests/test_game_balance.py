"""The balance model: tower damage, wave demands, King income, investments, profiles, rivals."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ancienttdde.cli import app
from ancienttdde.game.catalog import TowerAttack

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
    # Enemies spawn for the batch window and walk the lane at the configured speed.
    assert first.spawn_seconds == (balance.waves[0].batches - 1) * balance.waves[0].interval
    assert first.crossing_seconds == pytest.approx(48 / 0.65, abs=0.1)
    assert first.required_dps == pytest.approx(
        first.total_hit_points / (first.spawn_seconds + first.crossing_seconds)
    )
    assert needs[-1].required_dps > needs[0].required_dps * 20
    # The schedule's own armor replaces the unit's in the demand table.
    rams = next(need for need in needs if need.unit == "SIEGE_RAM")
    assert rams.pierce_armor == 40 and inputs().stock.unit("SIEGE_RAM").armor(PIERCE) == 195


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
        # Bought at the start, every investment returns at least half as much again; bought
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


def test_rivalry_tables_scale_siege_and_raids_with_the_player_count() -> None:
    from ancienttdde.game.balance import rivalry

    rows = rivalry(inputs())
    assert [row.players for row in rows] == list(range(2, 8))
    siege = inputs().shop.get("siege")
    two, seven = rows[0], rows[-1]
    assert two.siege_price == siege.kings + 5 and seven.siege_price == siege.kings + 30
    assert two.trebuchets == 2 and seven.trebuchets == 12
    # Two trebuchets for a minute at a ten-second reload, 450 against buildings.
    assert two.siege_damage_per_rival == pytest.approx(2 * 6 * (200 + 250 - 9))
    assert two.watch_towers_per_rival > 0 and two.rebuild_kings_per_rival > 0
    assert two.cart_seconds == pytest.approx(70 / (7 / 2))
    assert two.cog_seconds > 0 and two.trader_replacement_kings == pytest.approx(1 / 3)


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
        "## Shop",
        "## Investments",
        "## Income",
        "## Civilizations",
        "## Rivals",
    ):
        assert heading in text
    assert "| Koreans |" in text and "| Any other civilization |" in text
    assert "| Civilization | Lacks | Profile | Solo | Native | Total | PvP |" in text
    assert "| Teutons | - | " in text and "| 1.0 +0.1 | " in text
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
        exchange.kings(**{r: float(a) for r, a in fletching.cost.items()})
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


def test_the_report_names_the_competitive_level_and_copes_with_new_civilizations(
    tmp_path: Path,
) -> None:
    import json

    from ancienttdde.game.balance import Assumptions, load_inputs
    from ancienttdde.game.report import render_report

    root = copy_content(tmp_path)
    game = json.loads((root / "content/balance/game.json").read_text())
    game["difficulty"]["competitive"] = "hard"
    (root / "content/balance/game.json").write_text(json.dumps(game))
    civilizations = json.loads((root / "content/balance/civilizations.json").read_text())
    civilizations["civilizations"].append(
        {"key": "ATLANTEANS", "id": 70, "identity": "", "profile": {"kings": 1}}
    )
    (root / "content/balance/civilizations.json").write_text(json.dumps(civilizations))
    text = render_report(load_inputs(root), Assumptions())
    assert "Hard hit points." in text and "on Hard without buying anything" in text
    assert "Normal" not in text.split("## Waves")[1].split("## Civilizations")[0]
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

    from ancienttdde.game.balance import load_inputs, rivalry
    from ancienttdde.game.report import rivals_section

    root = copy_content(tmp_path)
    game = json.loads((root / "content/balance/game.json").read_text())
    game["interaction"]["raiders"]["land"].update({"unit": "HUSSAR", "line": ["HUSSAR"]})
    (root / "content/balance/game.json").write_text(json.dumps(game))
    data = load_inputs(root)
    stock = data.stock
    first = rivalry(data)[0]
    assert first.land_raider == "HUSSAR" and first.naval_raider == "FIRE_GALLEY"
    expected = stock.unit("TRADE_CART_EMPTY").hit_points / (
        (stock.unit("HUSSAR").attack(4) - stock.unit("TRADE_CART_EMPTY").armor(4))
        / stock.unit("HUSSAR").reload
    )
    assert first.cart_seconds == pytest.approx(expected)
    assert "A hussar raider kills a trade cart" in rivals_section(data)
