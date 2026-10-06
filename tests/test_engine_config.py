"""Reject balance values that could make a run invalid or unbounded."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_balance_has_a_finite_schedule_ending_in_a_boss():
    from ancienttdde.engine.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    assert 2100 <= balance.scheduled_seconds <= 3600
    assert balance.waves[-1].boss
    assert all(w.count == 2 for w in balance.waves)
    assert all(w.count * w.batches <= 400 for w in balance.waves)
    assert balance.max_enemies_per_lane <= 100


def test_short_waves_keep_their_enemy_count_and_tiers_end_in_bosses():
    from ancienttdde.engine.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    assert all(w.duration <= 120 for w in balance.waves)
    assert all(w.count * w.batches >= (8 if w.boss else 60) for w in balance.waves)
    assert [w.boss for w in balance.waves] == [i % 5 == 4 for i in range(len(balance.waves))]


def test_villagers_open_the_schedule_as_its_weakest_wave():
    from ancienttdde.engine.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    assert waves[0].unit == "VILLAGER_MALE"
    assert waves[0].hit_points < min(w.hit_points for w in waves[1:])


def test_resources_at_the_first_wave_stay_near_the_playtested_amounts():
    from ancienttdde.engine.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    paid = balance.preparation_seconds // balance.income_interval * balance.income_amount
    # DE trials held 1,300-1,490 of each resource when the first wave arrived.
    assert balance.starting_resources + paid <= 1600


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lives", 0),
        ("income_interval", 0),
        ("preparation_seconds", True),
        ("max_enemies_per_lane", 100000),
        ("sudden_death_interval", -1),
    ],
)
def test_reject_invalid_settings(tmp_path, field, value):
    from ancienttdde.engine.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    raw[field] = value
    path = tmp_path / "balance.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=field):
        load_balance(path)


def test_reject_unknown_wave_type_and_incomplete_schedule(tmp_path):
    from ancienttdde.engine.config import load_balance

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
