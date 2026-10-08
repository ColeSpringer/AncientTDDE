"""Reject balance values that could make a run invalid or unbounded."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_balance_has_a_finite_schedule_ending_in_a_boss() -> None:
    from ancienttdde.game.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    assert 2100 <= balance.scheduled_seconds <= 3600
    assert balance.waves[-1].boss
    assert all(w.count == 2 for w in balance.waves)
    assert all(w.count * w.batches <= 400 for w in balance.waves)
    assert balance.max_enemies_per_lane <= 100


def test_short_waves_keep_their_enemy_count_and_tiers_end_in_bosses() -> None:
    from ancienttdde.game.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    assert all(w.duration <= 120 for w in balance.waves)
    assert all(w.count * w.batches >= (8 if w.boss else 60) for w in balance.waves)
    assert [w.boss for w in balance.waves] == [i % 5 == 4 for i in range(len(balance.waves))]


def test_boss_waves_keep_the_pressure_on() -> None:
    from ancienttdde.game.config import load_balance

    for wave in load_balance(ROOT / "content/balance/game.json").waves:
        if wave.boss:
            # Pairs of bosses follow each other within twenty seconds, and the wave cannot
            # outlast its last pair by more than thirty.
            assert wave.interval <= 20, wave.key
            assert wave.duration - (wave.batches - 1) * wave.interval <= 30, wave.key


def test_villagers_open_the_schedule_as_its_weakest_wave() -> None:
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    assert waves[0].unit == "VILLAGER_MALE"
    assert waves[0].hit_points < min(w.hit_points for w in waves[1:])


def test_lanes_start_with_the_originals_technologies_and_a_modest_grant() -> None:
    from ancienttdde.game.config import load_balance

    economy = load_balance(ROOT / "content/balance/game.json").economy
    assert economy.starting_technologies == (
        "BALLISTICS",
        "MURDER_HOLES",
        "CARAVAN",
        "WHEELBARROW",
        "HAND_CART",
        "SPIES_AND_TREASON",
    )
    start = economy.starting_resources
    # Enough stone and wood for an opening line of eight Watch Towers (125 stone, 25 wood each),
    # but no free King: the gold stays below a conversion.
    assert min(start.stone // 125, start.wood // 25) >= 8
    assert (
        start.gold
        < load_balance(ROOT / "content/balance/game.json").difficulty.level("easy").king_gold
    )
    assert (start.food, start.wood, start.stone, start.gold) == (750, 1500, 1500, 400)


def test_tower_families_resolve_to_tower_definitions_only() -> None:
    from ancienttdde.game.config import load_balance

    towers = load_balance(ROOT / "content/balance/game.json").towers
    assert towers.family_ids("towers") == (79, 234, 235, 236)
    assert towers.family_ids("bombard") == (236,)
    assert towers.special_id == 684


def test_special_tower_states_its_stock_attack_and_range() -> None:
    from ancienttdde.game.config import load_balance

    towers = load_balance(ROOT / "content/balance/game.json").towers
    # The stock Accursed Tower: 8 pierce attack, 13 range (DE data).
    assert (towers.special_attack, towers.special_range) == (8, 13)
    assert towers.special_pierce == 232


def test_wave_hit_points_fit_the_engine_attribute() -> None:
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    # DE stores unit hit points in 16 bits; a larger value wraps around.
    assert all(w.hit_points <= 32767 for w in waves)


def test_waves_grow_stronger_and_each_boss_outclasses_the_waves_before_it() -> None:
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    regular = [w.hit_points for w in waves if not w.boss]
    assert regular == sorted(set(regular))
    bosses = [w.hit_points for w in waves if w.boss]
    assert bosses == sorted(set(bosses))
    for index, wave in enumerate(waves):
        if wave.boss:
            before = [w.hit_points for w in waves[:index] if not w.boss]
            assert wave.hit_points > 3 * max(before)


def write_balance(tmp_path: Path, raw: dict[str, object]) -> Path:
    path = tmp_path / "balance.json"
    path.write_text(json.dumps(raw))
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lives", 0),
        ("preparation_seconds", True),
        ("max_enemies_per_lane", 100000),
        ("sudden_death_interval", -1),
    ],
)
def test_reject_invalid_settings(tmp_path: Path, field: str, value: object) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    raw[field] = value
    with pytest.raises(ValueError, match=field):
        load_balance(write_balance(tmp_path, raw))


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("difficulty", "levels", "normal", "king_gold"), 0, "king_gold"),
        (("difficulty", "levels", "hard", "hit_points_percent"), 300, "hit_points_percent"),
        (("difficulty", "lobby", "moderate"), "brutal", "difficulty level"),
        (("difficulty", "competitive"), "brutal", "difficulty level"),
        (("endless", "templates"), ["Knights", "Dragons"], "Dragons"),
        (("endless", "templates"), [], "templates"),
        (("endless", "templates"), ["Elephant Vanguard", "Elephant Finale"], "share"),
        (("endless", "hit_point_growth_percent"), 0, "hit_point_growth_percent"),
        (("endless", "armor_step"), -1, "armor_step"),
        (("interaction", "raiders", "land", "unit"), "ARCHER", "ARCHER"),
        (("interaction", "raiders", "naval", "unit"), "GALLEY", "GALLEY"),
        (("interaction", "raiders", "land", "line"), ["HUSSAR"], "LIGHT_CAVALRY"),
        (("interaction", "raiders", "land", "cap"), 0, "cap"),
        (("interaction", "raiders", "bonuses", 0, "civilization"), "ATLANTEANS", "ATLANTEANS"),
        (("interaction", "raiders", "bonuses", 0, "civilization"), "RANDOM", "RANDOM"),
        (("interaction", "raiders", "bonuses", 0, "medium"), "air", "medium"),
        (("interaction", "siege", "trebuchets_per_rival"), 4, "trebuchets_per_rival"),
        (("interaction", "siege", "warning_seconds"), 0, "warning_seconds"),
        (("interaction", "siege", "buyer_cooldown"), 30, "buyer_cooldown"),
        (("practice", "kings"), 0, "kings"),
        (("economy", "starting_technologies"), ["BALLISTICS", "CATAPULTS"], "technology"),
        (("economy", "starting_technologies"), "BALLISTICS", "starting_technologies"),
        (("economy", "starting_technologies"), ["BALLISTICS", "BALLISTICS"], "twice"),
        (("economy", "starting_technologies"), ["CASTLE_AGE"], "CASTLE_AGE"),
        (("economy", "starting_technologies"), ["GUARD_TOWER"], "GUARD_TOWER"),
        (("economy", "starting_resources", "stone"), -1, "stone"),
        (("economy", "kill_reward", "kills"), 0, "kills"),
        (("towers", "families", "towers"), ["WATCH_TOWER", "HOUSE"], "Not a tower: HOUSE"),
        (("towers", "special", "unit"), "CASTLE", "Not a tower: CASTLE"),
        (("towers", "special", "range"), 0, "range"),
        (("towers", "special", "attack"), -1, "attack"),
        (("waves", 0, "hit_points"), 40000, "hit_points"),
    ],
)
def test_reject_invalid_economy_and_towers(
    tmp_path: Path, path: tuple[str | int, ...], value: object, message: str
) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    target = raw
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    with pytest.raises(ValueError, match=message):
        load_balance(write_balance(tmp_path, raw))


def test_reject_an_outdated_balance_schema(tmp_path: Path) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    assert raw["schema_version"] == 4
    raw["schema_version"] = 3
    with pytest.raises(ValueError, match="Unsupported balance schema"):
        load_balance(write_balance(tmp_path, raw))


def test_reject_unknown_wave_type_and_incomplete_schedule(tmp_path: Path) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["waves"][0]["unit"] = "KING"
    path = tmp_path / "balance.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="unit"):
        load_balance(path)
    raw["waves"] = []
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="waves"):
        load_balance(path)


def test_lobby_difficulty_chooses_gold_per_king_and_wave_strength() -> None:
    from ancienttdde.game.config import LOBBY_DIFFICULTIES, load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    difficulty = balance.difficulty
    assert [(d.key, d.name, d.king_gold, d.hit_points_percent) for d in difficulty.levels] == [
        ("easy", "Easy", 2500, 80),
        ("normal", "Normal", 3500, 100),
        ("hard", "Hard", 5000, 125),
    ]
    # DE's lobby settings, as xsGetDifficulty reports them, from Extreme (-1) to Easiest (4).
    assert LOBBY_DIFFICULTIES == {
        "extreme": -1,
        "hardest": 0,
        "hard": 1,
        "moderate": 2,
        "standard": 3,
        "easiest": 4,
    }
    assert dict(difficulty.lobby) == {-1: 2, 0: 2, 1: 2, 2: 1, 3: 1, 4: 0}
    assert difficulty.levels[difficulty.competitive].key == "normal"


def test_difficulty_scales_wave_hit_points_within_the_engine_limit() -> None:
    from ancienttdde.game.config import MAX_HIT_POINTS, load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    normal = balance.difficulty.index("normal")
    for index, wave in enumerate(balance.waves):
        assert balance.hit_points(index, normal) == wave.hit_points
        scaled = [balance.hit_points(index, level) for level in range(3)]
        assert scaled == sorted(scaled) and max(scaled) <= MAX_HIT_POINTS
    assert balance.hit_points(0, balance.difficulty.index("easy")) == 120
    assert balance.hit_points(len(balance.waves) - 1, balance.difficulty.index("hard")) == (
        MAX_HIT_POINTS
    )


def test_endless_waves_repeat_the_last_tier_and_grow_until_the_limit() -> None:
    from ancienttdde.game.config import MAX_HIT_POINTS, load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    endless = balance.endless
    assert [balance.waves[t].key for t in endless.templates] == [
        "Two-Handed Swords",
        "Cavaliers",
        "Champions",
        "Paladins",
        "Elephant Finale",
    ]
    assert (endless.growth_percent, endless.armor_step) == (50, 25)
    levels = balance.endless_levels
    assert 1 <= levels <= 10
    for difficulty in range(3):
        for position, template in enumerate(endless.templates):
            grown = [
                balance.endless_hit_points(level, position, difficulty)
                for level in range(1, levels + 1)
            ]
            assert grown == sorted(grown) and grown[-1] == MAX_HIT_POINTS
            assert grown[0] > balance.hit_points(template, difficulty) or grown[0] == MAX_HIT_POINTS


def test_raiders_are_melee_or_short_range_and_capped() -> None:
    from AoE2ScenarioParser.datasets.units import UnitInfo

    from ancienttdde.game.config import load_balance

    raiders = load_balance(ROOT / "content/balance/game.json").interaction.raiders
    assert (raiders.land.unit, raiders.land.cap) == ("LIGHT_CAVALRY", 2)
    assert (raiders.naval.unit, raiders.naval.cap) == ("FIRE_GALLEY", 2)
    # A cap counts the whole upgrade line, so upgrading cannot free a slot.
    assert raiders.land.line_ids == tuple(
        UnitInfo[name].ID for name in ("LIGHT_CAVALRY", "HUSSAR", "WINGED_HUSSAR")
    )
    assert raiders.naval.line_ids == tuple(
        UnitInfo[name].ID for name in ("FIRE_GALLEY", "FIRE_SHIP", "FAST_FIRE_SHIP")
    )
    bonuses = {(civ, medium) for civ, medium, _ in raiders.bonuses}
    assert ("MONGOLS", "land") in bonuses and ("VIKINGS", "naval") in bonuses
    assert all(extra == 1 for _, _, extra in raiders.bonuses)


def test_raider_kinds_reject_unknown_media() -> None:
    from typing import cast

    from ancienttdde.game.config import load_balance
    from ancienttdde.game.sites import RAIDER_MEDIA, RaiderMedium

    raiders = load_balance(ROOT / "content/balance/game.json").interaction.raiders
    assert [raiders.kind(medium) for medium in RAIDER_MEDIA] == [raiders.land, raiders.naval]
    for medium in ("Land", "air"):
        with pytest.raises(ValueError, match=medium):
            raiders.kind(cast(RaiderMedium, medium))


def test_endless_levels_are_worked_out_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from ancienttdde.game.config import Balance, load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    calls: list[int] = []
    grow = Balance.endless_hit_points

    def counted(self: Balance, level: int, position: int, difficulty: int) -> int:
        calls.append(level)
        return grow(self, level, position, difficulty)

    monkeypatch.setattr(Balance, "endless_hit_points", counted)
    assert balance.endless_levels >= 1 and not calls


def test_siege_warns_holds_and_cools_down_for_its_configured_times() -> None:
    from ancienttdde.game.config import load_balance

    siege = load_balance(ROOT / "content/balance/game.json").interaction.siege
    assert (siege.trebuchets_per_rival, siege.warning_seconds, siege.active_seconds) == (2, 10, 60)
    assert (siege.shared_cooldown, siege.buyer_cooldown) == (60, 120)


def test_practice_grants_and_sudden_death_pace() -> None:
    from ancienttdde.game.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    assert (balance.practice.kings, balance.practice.resources) == (5, 5000)
    assert balance.sudden_death_interval == 30
