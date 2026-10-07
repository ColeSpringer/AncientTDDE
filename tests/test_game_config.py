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
    assert start.gold < economy.king_gold
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
        (("economy", "king_gold"), 0, "king_gold"),
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
    assert raw["schema_version"] == 3
    raw["schema_version"] = 2
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
