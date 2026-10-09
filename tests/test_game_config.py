"""Reject balance values that could make a run invalid or unbounded."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_balance_has_a_finite_schedule_ending_in_ten_bosses() -> None:
    from ancienttdde.game.config import load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    # About seventy game minutes of spawning and intermissions: roughly fifty real minutes at
    # Fast once the enemies' crossings are added.
    assert 3600 <= balance.scheduled_seconds <= 5400
    assert len(balance.waves) == 56
    assert [w.boss for w in balance.waves] == [False] * 46 + [True] * 10
    assert all(w.enemies <= 400 for w in balance.waves)
    assert balance.max_enemies_per_lane <= 100
    assert (balance.choice_seconds, balance.boss_leak_lives) == (60, 5)


def test_the_schedule_follows_the_originals_roster_and_cadence() -> None:
    """The original's 46 regular waves in its order, and its pacing: pairs every three seconds
    for forty-five seconds, threes from level 7, seventy-five seconds for level 9 and 10-A."""
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    units = [w.unit for w in waves[:46]]
    assert units[:5] == ["VILLAGER_MALE", "MILITIA", "SPEARMAN", "ARCHER", "WAR_ELEPHANT"]
    assert units[5:10] == ["MAN_AT_ARMS", "PIKEMAN", "CHAMPION", "SCOUT_CAVALRY", "MAMELUKE"]
    assert units[15:20] == [
        "CHARLES_MARTEL",
        "GUY_JOSSELYNE",
        "JOAN_OF_ARC",
        "WILLIAM_WALLACE",
        "WILLIAM_THE_CONQUEROR",
    ]
    assert units[35:40] == [
        "PALADIN",
        "ELITE_WAR_ELEPHANT",
        "ELITE_CATAPHRACT",
        "BELISARIUS",
        "SIEGE_RAM",
    ]
    assert units[45] == "SCYTHIAN_SCOUT"
    assert len(set(units)) == 46
    for index, wave in enumerate(waves[:46]):
        level = index // 5 + 1
        assert wave.count == (2 if level <= 6 else 3), wave.key
        assert wave.interval == (5 if index == 4 else 3), wave.key
        assert wave.duration == (75 if level >= 9 else 45), wave.key
        expected = 18 if index == 4 else 30 if level <= 6 else 45 if level <= 8 else 75
        assert wave.enemies == expected, wave.key
    bosses = waves[46:]
    assert all(w.enemies == 1 and w.duration == 1 for w in bosses)
    # The rams keep half their armor, not the 195 that would turn arrows away.
    rams = next(w for w in waves if w.unit == "SIEGE_RAM")
    assert rams.pierce_armor == 100 and all(w.pierce_armor is None for w in waves if w is not rams)
    assert len({w.unit for w in bosses}) == 10 and not {w.unit for w in bosses} & set(units)


def test_villagers_open_the_schedule_as_its_weakest_wave() -> None:
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    assert waves[0].unit == "VILLAGER_MALE" and waves[0].hit_points == 45
    assert waves[0].hit_points < min(w.hit_points for w in waves[1:])


def test_wave_units_may_be_heroes_but_not_the_king() -> None:
    from ancienttdde.game.config import load_balance, wave_unit

    assert wave_unit("CHARLEMAGNE") == 165 and wave_unit("VILLAGER_MALE") == 83
    with pytest.raises(ValueError, match="Unknown wave unit: DRAGON"):
        wave_unit("DRAGON")
    with pytest.raises(ValueError, match="King"):
        wave_unit("KING")
    waves = load_balance(ROOT / "content/balance/game.json").waves
    assert waves[-1].object_id == 1071


def test_lane_paths_hold_the_three_rows_a_batch_fills() -> None:
    from ancienttdde.common.data import object_value, read_object
    from ancienttdde.game.config import load_lanes

    anchors = object_value(read_object(ROOT / "content/maps/foundation.json")["anchors"], "anchors")
    for lane in load_lanes(anchors):
        assert lane.path[1] + 1 <= lane.center_y <= lane.path[3] - 1
    anchors["lane.p1.path"] = {"region": [8, 14, 56, 16]}
    load_lanes(anchors)
    anchors["lane.p1.path"] = {"region": [8, 15, 56, 16]}
    with pytest.raises(ValueError, match="3 rows"):
        load_lanes(anchors)


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


def test_wave_hit_points_fit_the_engine_attribute_except_for_bosses() -> None:
    from ancienttdde.game.config import BOSS_HIT_POINTS, MAX_HIT_POINTS, load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    # DE stores unit hit points in 16 bits; a boss carries more as its current hit points.
    assert all(w.hit_points <= MAX_HIT_POINTS for w in waves if not w.boss)
    assert all(MAX_HIT_POINTS < w.hit_points <= BOSS_HIT_POINTS for w in waves if w.boss)


def test_every_boss_outclasses_every_regular_wave() -> None:
    from ancienttdde.game.config import load_balance

    waves = load_balance(ROOT / "content/balance/game.json").waves
    # Each boss needs more damage per second than the last (test_game_balance.py); its hit
    # points follow its speed.
    bosses = [w.hit_points for w in waves if w.boss]
    assert min(bosses) > 10 * max(w.hit_points for w in waves if not w.boss)


def write_balance(tmp_path: Path, raw: dict[str, object]) -> Path:
    path = tmp_path / "balance.json"
    path.write_text(json.dumps(raw))
    return path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lives", 0),
        ("boss_leak_lives", 0),
        ("choice_seconds", 5),
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
        (("endless", "templates"), ["Villagers", "Villagers"], "twice"),
        (("endless", "hit_point_growth_percent"), 0, "hit_point_growth_percent"),
        (("endless", "armor_step"), -1, "armor_step"),
        (("interaction", "raiders", "land", "unit"), "ARCHER", "ARCHER"),
        (("interaction", "raiders", "naval", "unit"), "GALLEY", "GALLEY"),
        (("interaction", "raiders", "land", "line"), ["HUSSAR"], "LIGHT_CAVALRY"),
        (("interaction", "raiders", "land", "cap"), 0, "cap"),
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
        (("waves", 55, "hit_points"), 6_000_000, "hit_points"),
        (("waves", 0, "count"), 4, "count"),
        (("waves", 55, "count"), 2, "one enemy"),
        (("waves", 39, "pierce_armor"), 600, "pierce_armor"),
        (("waves", 0, "unit"), "KING", "King"),
        (("waves", 0, "unit"), "CHARLEMAGNE", "boss unit"),
        (("endless", "templates"), ["Charlemagne"], "boss"),
        (("economy", "starting_technologies"), ["BALLISTICS", "GILLNETS"], "GILLNETS"),
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
    assert raw["schema_version"] == 6
    raw["schema_version"] = 5
    with pytest.raises(ValueError, match="Unsupported balance schema"):
        load_balance(write_balance(tmp_path, raw))


def test_raider_bonuses_belong_to_the_civilization_profiles(tmp_path: Path) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    assert "bonuses" not in raw["interaction"]["raiders"]
    raw["interaction"]["raiders"]["bonuses"] = [
        {"civilization": "HUNS", "medium": "land", "extra": 1}
    ]
    with pytest.raises(ValueError, match="civilizations.json"):
        load_balance(write_balance(tmp_path, raw))


def test_reject_unknown_wave_type_and_incomplete_schedule(tmp_path: Path) -> None:
    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text())
    raw["waves"][0]["unit"] = "KING"
    path = tmp_path / "balance.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="unit"):
        load_balance(path)
    raw["waves"][0]["unit"] = "VILLAGER_MALE"
    raw["waves"][1]["unit"] = "VILLAGER_MALE"
    raw["endless"]["templates"] = ["Villagers", "Militia"]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="share"):
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
        ("easy", "Easy", 1500, 80),
        ("normal", "Normal", 2000, 100),
        ("hard", "Hard", 3000, 110),
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
        assert scaled == sorted(scaled)
        assert wave.boss or max(scaled) <= MAX_HIT_POINTS
    assert balance.hit_points(0, balance.difficulty.index("easy")) == 36
    last = balance.waves[-1]
    assert balance.hit_points(len(balance.waves) - 1, balance.difficulty.index("hard")) == (
        last.hit_points * 110 // 100
    )


def test_endless_waves_repeat_the_last_tier_and_grow_until_the_limit() -> None:
    from ancienttdde.game.config import MAX_HIT_POINTS, load_balance

    balance = load_balance(ROOT / "content/balance/game.json")
    endless = balance.endless
    assert [balance.waves[t].key for t in endless.templates] == [
        "Elite Conquistadors",
        "Attila the Hun",
        "Master of the Templar",
        "Lancelot",
        "Henry V",
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
    assert not hasattr(raiders, "bonuses")


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


@pytest.mark.parametrize("name", ["YASAMA", "CRENELLATIONS", "FAST_FIRE_SHIP"])
def test_starting_technologies_cannot_be_ones_the_lanes_rule_out(tmp_path: Path, name: str) -> None:
    import json

    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text(encoding="utf-8"))
    raw["economy"]["starting_technologies"].append(name)
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=f"{name} cannot be a starting technology"):
        load_balance(path)


def test_the_king_price_floor_keeps_every_profile_price_above_zero(tmp_path: Path) -> None:
    import json

    from ancienttdde.game.config import load_balance

    raw = json.loads((ROOT / "content/balance/game.json").read_text(encoding="utf-8"))
    raw["difficulty"]["levels"]["easy"]["king_gold"] = 99
    path = tmp_path / "game.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="king_gold must be an integer between 100 and 30000"):
        load_balance(path)
