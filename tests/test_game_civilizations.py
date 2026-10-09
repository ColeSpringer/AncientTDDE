"""Civilization profiles: coverage of every civilization, validation and the default fallback."""

import json
from pathlib import Path
from typing import Any

import pytest
from AoE2ScenarioParser.datasets.object_support import CivilizationOld

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/balance/civilizations.json"


def balance():
    from ancienttdde.game.config import load_balance

    return load_balance(ROOT / "content/balance/game.json")


def shop():
    from ancienttdde.game.catalog import load_shop

    anchors = json.loads((ROOT / "content/maps/foundation.json").read_text(encoding="utf-8"))
    families = [name for name, _ in balance().towers.families]
    return load_shop(ROOT / "content/balance/shop.json", anchors["anchors"], families)


def stock():
    from ancienttdde.game.stock import load_stock

    return load_stock(ROOT / "content/balance/stock.json")


def load(path: Path = CONTENT):
    from ancienttdde.game.civilizations import load_profiles

    return load_profiles(path, balance(), shop(), stock())


def raw() -> dict[str, Any]:
    return json.loads(CONTENT.read_text(encoding="utf-8"))


def write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "civilizations.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_every_civilization_the_dataset_knows_has_an_explicit_profile() -> None:
    profiles = load()
    known = {member.name: member.value for member in CivilizationOld if 0 < member.value <= 255}
    assert len(known) == 59
    listed = {c.key: c.id for c in profiles.civilizations}
    assert listed.items() >= known.items()
    # DE's newest civilizations come after the pinned dataset, at their DAT indexes.
    assert {key: id for key, id in listed.items() if key not in known} == {
        "SAXONS": 60,
        "VARANGIANS": 61,
        "DANES": 62,
    }
    assert [c.id for c in profiles.civilizations] == list(range(1, 63))
    britons, hindustanis = profiles.by_id(1), profiles.by_id(20)
    assert britons is not None and britons.name == "Britons"
    assert hindustanis is not None and hindustanis.name == "Hindustanis"


def test_unknown_civilizations_are_not_listed() -> None:
    profiles = load()
    assert profiles.by_id(200) is None and profiles.by_id(0) is None
    huns = profiles.by_id(17)
    assert huns is not None and huns.key == "HUNS"


def test_profiles_default_to_neutral_values() -> None:
    from ancienttdde.game.civilizations import Profile
    from ancienttdde.game.config import Resources

    profile = Profile()
    assert (profile.kings, profile.king_gold_percent, profile.kill_reward_percent) == (0, 100, 100)
    assert profile.resources == Resources(0, 0, 0, 0)
    assert profile.neutral and profile.native is None
    assert profile.raider_extra("land") == 0 and profile.raider_extra("naval") == 0


def test_raider_bonuses_live_in_the_profiles() -> None:
    profiles = load()
    huns, vikings, britons = (profiles.by_id(i) for i in (17, 11, 1))
    assert huns is not None and huns.profile.raider_extra("land") == 1
    assert vikings is not None and vikings.profile.raider_extra("naval") == 1
    assert britons is not None and britons.profile.raider_extra("land") == 0
    extras = {
        (c.key, medium): extra
        for c in profiles.civilizations
        for medium, extra in c.profile.raiders
    }
    # Steppe civilizations raid by land and seafaring ones by sea.
    assert extras.keys() >= {
        ("HUNS", "land"),
        ("MONGOLS", "land"),
        ("MAGYARS", "land"),
        ("CUMANS", "land"),
        ("TATARS", "land"),
        ("VIKINGS", "naval"),
        ("ITALIANS", "naval"),
        ("PORTUGUESE", "naval"),
        ("MALAY", "naval"),
        ("SARACENS", "naval"),
    }
    assert all(extra == 1 for extra in extras.values())
    for medium in ("land", "naval"):
        assert sum(1 for _, found in extras if found == medium) <= 15
    assert profiles.raider_bonuses() == tuple(
        sorted((key, medium, extra) for (key, medium), extra in extras.items())
    )


def test_native_effects_are_the_part_native_triggers_apply() -> None:
    from ancienttdde.game.civilizations import NativeEffects, Profile
    from ancienttdde.game.config import Resources

    profile = Profile(
        kings=1,
        resources=Resources(0, 0, 500, 0),
        attack=(("towers", 2),),
        technologies=("MASONRY",),
        raiders=(("land", 1),),
    )
    assert profile.native == NativeEffects(
        resources=Resources(0, 0, 500, 0), technologies=("MASONRY",)
    )
    assert not profile.neutral
    # Kings, raiders and tower attack are applied by the XS, so profiles differing only there
    # share triggers.
    assert Profile(kings=2).native is None and Profile(raiders=(("naval", 1),)).native is None
    assert Profile(attack=(("towers", 2),)).native is None


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("duplicate_key", "Duplicate civilization key: BRITONS"),
        ("lowercase_key", "Civilization keys are uppercase identifiers: britons"),
        ("wrong_id", "BRITONS must carry its dataset id 1"),
        ("unknown_low_id", "ATLANTEANS is not in the dataset: its id must be 60 or more"),
        ("duplicate_id", "Duplicate civilization id: 60"),
        ("id_too_large", "id must be an integer between 1 and 255"),
        ("kings", "kings must be an integer between 0 and 5"),
        ("gold_percent", "king_gold_percent must be an integer between 50 and 150"),
        ("kill_percent", "kill_reward_percent must be an integer between 50 and 300"),
        ("resources", "stone must be an integer between 0 and 10000"),
        ("attack_family", "Unknown tower family: walls"),
        ("attack_amount", "towers must be an integer between 0 and 200"),
        ("reserved_technology", "CASTLE_AGE cannot be a profile technology"),
        ("restricted_technology", "CRENELLATIONS cannot be a profile technology"),
        ("starting_technology", "BALLISTICS is a starting technology"),
        ("unknown_technology", "Unknown technology: CATAPULTS"),
        ("repeated_technology", "Technology listed twice: MASONRY"),
        ("identity_quote", "Civilization text cannot hold quotes, backslashes or percent signs"),
        ("identity_percent", "Civilization text cannot hold quotes, backslashes or percent signs"),
        ("default_identity", "Civilization text cannot hold quotes, backslashes or percent signs"),
        ("raider_medium", "raiders must name land or naval"),
        ("trader_medium", "traders must name land or water"),
        ("relics", "relics must be an integer between 0 and 3"),
        ("schema", "Unsupported civilizations schema"),
        ("no_default", "default must be an object"),
        ("profile_type", "profile must be an object"),
        ("unknown_key", "Unknown profile setting: tower_hitpoints"),
        ("unknown_resource", "resources must name food, wood, stone or gold: golds"),
        ("unknown_purchase", "Unknown purchase: teleport"),
        ("raider_purchase", "land_raider cannot be granted: raiders and the siege act on rivals"),
        ("siege_purchase", "siege cannot be granted: raiders and the siege act on rivals"),
        ("repeated_purchase", "Purchase listed twice: castle_age"),
        ("missing_requirement", "imperial_age needs castle_age granted as well"),
        ("disabled_technology", "FAST_FIRE_SHIP cannot be a profile technology: the game rules"),
        ("multiplier_technology", "YASAMA cannot be a profile technology: the game rules it out"),
        ("trader_clash", "trade_carts cannot be granted beside starting land traders"),
        ("random_key", "RANDOM is not a playable civilization"),
        ("gaia_key", "GAIA is not a playable civilization"),
        ("native_range", "solo must be a number between 0 and 5"),
        ("native_key", "Unknown native setting: total"),
        ("row_key", "Unknown civilization setting: natve"),
        ("default_key", "Unknown default setting: natives"),
        ("tree_technology", "BRITONS cannot research STONE_SHAFT_MINING"),
        ("tree_purchase", "BRITONS cannot be granted bombard_attack_400: it needs Bombard Towers"),
        ("tree_bombard", "BRITONS cannot raise bombard attack: it lacks Bombard Towers"),
        ("unwatched_technology", "SQUIRES is not in the stock snapshot"),
    ],
)
def test_invalid_profiles_are_rejected(defect: str, message: str, tmp_path: Path) -> None:
    data = raw()
    civilizations: list[dict[str, Any]] = data["civilizations"]
    first = civilizations[0]
    assert first["key"] == "BRITONS"
    extra: dict[str, Any] = {"key": "ATLANTEANS", "id": 70, "identity": "", "profile": {}}
    match defect:
        case "duplicate_key":
            civilizations.append(dict(first))
        case "lowercase_key":
            first["key"] = "britons"
        case "wrong_id":
            first["id"] = 2
        case "unknown_low_id":
            civilizations.append(extra | {"id": 5})
        case "duplicate_id":
            civilizations.append(extra | {"id": 60})
        case "id_too_large":
            civilizations.append(extra | {"id": 300})
        case "kings":
            first["profile"]["kings"] = 9
        case "gold_percent":
            first["profile"]["king_gold_percent"] = 10
        case "kill_percent":
            first["profile"]["kill_reward_percent"] = 400
        case "resources":
            first["profile"]["resources"] = {"stone": -5}
        case "attack_family":
            first["profile"]["attack"] = {"walls": 5}
        case "attack_amount":
            first["profile"]["attack"] = {"towers": 999}
        case "reserved_technology":
            first["profile"]["technologies"] = ["CASTLE_AGE"]
        case "restricted_technology":
            first["profile"]["technologies"] = ["CRENELLATIONS"]
        case "starting_technology":
            first["profile"]["technologies"] = ["BALLISTICS"]
        case "unknown_technology":
            first["profile"]["technologies"] = ["CATAPULTS"]
        case "repeated_technology":
            first["profile"]["technologies"] = ["MASONRY", "MASONRY"]
        case "identity_quote":
            first["identity"] = 'towers "shoot" faster'
        case "identity_percent":
            first["identity"] = "stone miners work 20% faster"
        case "default_identity":
            data["default"]["identity"] = "no profile \\ default"
        case "raider_medium":
            first["profile"]["raiders"] = {"air": 1}
        case "trader_medium":
            first["profile"]["traders"] = {"naval": 1}
        case "relics":
            first["profile"]["relics"] = 4
        case "schema":
            data["schema_version"] = 0
        case "no_default":
            del data["default"]
        case "profile_type":
            first["profile"] = []
        case "unknown_key":
            first["profile"]["tower_hitpoints"] = 300
        case "unknown_resource":
            first["profile"]["resources"] = {"golds": 300}
        case "unknown_purchase":
            first["profile"]["purchases"] = ["teleport"]
        case "raider_purchase":
            first["profile"]["purchases"] = ["land_raider"]
        case "siege_purchase":
            first["profile"]["purchases"] = ["siege"]
        case "repeated_purchase":
            first["profile"]["purchases"] = ["castle_age", "castle_age"]
        case "missing_requirement":
            first["profile"]["purchases"] = ["imperial_age"]
        case "disabled_technology":
            first["profile"]["technologies"] = ["FAST_FIRE_SHIP"]
        case "multiplier_technology":
            first["profile"]["technologies"] = ["YASAMA"]
        case "trader_clash":
            first["profile"]["traders"] = {"land": 1}
            first["profile"]["purchases"] = ["trade_carts"]
        case "random_key":
            civilizations.append(extra | {"key": "RANDOM", "id": 63})
        case "gaia_key":
            civilizations.append(extra | {"key": "GAIA", "id": 64})
        case "native_range":
            first["native"] = {"solo": 9}
        case "native_key":
            first["native"] = {"total": 1}
        case "row_key":
            first["natve"] = {"solo": 1}
        case "default_key":
            data["default"]["natives"] = {"solo": 1}
        case "tree_technology":
            first["profile"]["technologies"] = ["STONE_SHAFT_MINING"]
        case "tree_purchase":
            first["profile"]["purchases"] = ["bombard_attack_400"]
        case "tree_bombard":
            first["profile"]["attack"] = {"bombard": 5}
        case "unwatched_technology":
            first["profile"]["technologies"] = ["SQUIRES"]
        case _:
            raise AssertionError(defect)
    with pytest.raises(ValueError, match=message):
        load(write(tmp_path, data))


def test_a_granted_attack_purchase_may_join_the_profiles_own_attack(tmp_path: Path) -> None:
    """The XS adds both, so they may raise the same towers past 255 together."""
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    turks = next(row for row in data["civilizations"] if row["key"] == "TURKS")
    assert turks["profile"]["attack"] == {"bombard": 25}
    turks["profile"]["purchases"] = ["bombard_attack_400"]
    loaded = next(c for c in load(write(tmp_path, data)).civilizations if c.key == "TURKS")
    assert loaded.profile.purchases == ("bombard_attack_400",)
    assert loaded.profile.attack == (("bombard", 25),)


def test_the_default_profile_is_light_and_needs_no_native_triggers() -> None:
    from ancienttdde.game.balance import Assumptions, load_inputs, profile_value

    profiles = load()
    assert profiles.default_identity
    assert profiles.default.native is None
    worth = profile_value(profiles.default, load_inputs(ROOT), Assumptions())
    assert worth.solo == profiles.default.kings == 3 and worth.pvp == worth.solo


def test_every_civilization_has_an_identity_line_and_some_adjustment() -> None:
    for civilization in load().civilizations:
        assert civilization.identity, civilization.key
        assert ";" not in civilization.identity, civilization.key
        assert not civilization.profile.neutral, civilization.key


def test_profile_worth_stays_within_the_agreed_bands() -> None:
    from ancienttdde.game.balance import (
        Assumptions,
        baseline_income,
        civilization_value,
        load_inputs,
        profile_value,
    )

    inputs = load_inputs(ROOT)
    # Slight uniqueness, measured against what a lane earns over the run without buying
    # anything: every profile is worth about 2.6 to 7.1 percent of that income (one to two
    # Kings of the thirty-one a shorter schedule once paid); with the civilization's own
    # bonuses counted, no one holds more than 9.7 percent, and PvP adds at most 3.2 percent.
    income = baseline_income(inputs, Assumptions()).total_kings
    floor, ceiling = 0.026 * income, 0.071 * income
    for civilization in inputs.profiles.civilizations:
        worth = civilization_value(civilization, inputs, Assumptions())
        assert floor <= worth.profile.solo <= ceiling, (civilization.key, worth)
        assert worth.solo <= 0.097 * income, (civilization.key, worth)
        assert worth.pvp <= worth.solo + 0.032 * income, (civilization.key, worth)
    default = profile_value(inputs.profiles.default, inputs, Assumptions())
    assert floor <= default.solo <= ceiling


def test_native_worth_is_read_from_the_content_and_defaults_to_nothing(tmp_path: Path) -> None:
    from ancienttdde.game.civilizations import NativeWorth

    profiles = load()
    teutons, thracians = profiles.by_id(4), profiles.by_id(55)
    assert teutons is not None and thracians is not None
    assert teutons.native == NativeWorth(solo=1.0, pvp=0.1)
    assert thracians.native == NativeWorth() and NativeWorth().solo == 0.0
    data = raw()
    data["civilizations"][0]["native"] = {"pvp": 0.5}
    assert load(write(tmp_path, data)).civilizations[0].native == NativeWorth(0.0, 0.5)


def test_civilizations_without_guard_tower_or_keep_are_compensated() -> None:
    from ancienttdde.game.balance import Assumptions, civilization_value, load_inputs
    from ancienttdde.game.stock import load_stock

    inputs = load_inputs(ROOT)
    stock = load_stock(ROOT / "content/balance/stock.json")
    for civilization in inputs.profiles.civilizations:
        lacks = stock.civilization(civilization.id).lacks
        if lacks & {"GUARD_TOWER", "KEEP"}:
            # Its profile and its own bonuses together make up for the missing towers.
            worth = civilization_value(civilization, inputs, Assumptions())
            assert worth.solo >= 1.3, (civilization.key, worth)


def test_profiles_grant_only_technologies_their_civilization_can_research() -> None:
    from ancienttdde.game.stock import load_stock

    stock = load_stock(ROOT / "content/balance/stock.json")
    for civilization in load().civilizations:
        lacks = stock.civilization(civilization.id).lacks
        for name in civilization.profile.technologies:
            assert name not in lacks, (civilization.key, name)


def test_a_known_civilization_reads_its_own_line() -> None:
    profiles = load()
    huns = profiles.by_id(17)
    assert huns is not None
    text = profiles.text(huns)
    assert text.startswith(huns.identity + "; adjustments: ")
    assert "+1 land raider with PvP on" in text


def test_the_chat_line_holds_only_the_adjustments_and_stays_short() -> None:
    profiles = load()
    huns = profiles.by_id(17)
    assert huns is not None
    assert profiles.chat(huns) == ", ".join(adjustments_of(huns.profile))
    assert huns.identity not in profiles.chat(huns)
    assert profiles.chat(None) == "default profile: +3 starting Kings"
    from ancienttdde.game.civilizations import Civilization, Profile

    plain = Civilization("PLAIN", 100, "a plain civilization", Profile())
    assert profiles.chat(plain) == "no adjustments"
    # Seven lanes announce these at once; a line must not scroll the others away.
    assert all(len(profiles.chat(c)) <= 150 for c in profiles.civilizations)


def adjustments_of(profile: object) -> list[str]:
    from ancienttdde.game.civilizations import Profile, adjustments

    assert isinstance(profile, Profile)
    return adjustments(profile, load().purchase_names)


def test_purchases_granted_from_the_start_are_resolved_and_rendered() -> None:
    from ancienttdde.game.civilizations import NativeEffects, Profile, adjustments

    profiles = load()
    koreans = profiles.by_id(18)
    assert koreans is not None and "castle_age" in koreans.profile.purchases
    assert profiles.purchase_names["castle_age"] == "Castle Age and Guard Tower"
    assert "Castle Age and Guard Tower from the start" in adjustments(
        koreans.profile, profiles.purchase_names
    )
    assert "Castle Age and Guard Tower from the start" in profiles.chat(koreans)
    granted = Profile(purchases=("castle_age", "resource_villagers"))
    assert granted.native == NativeEffects(purchases=("castle_age", "resource_villagers"))
    assert not granted.neutral


def test_granted_once_only_purchases_make_an_ownership_mask() -> None:
    from ancienttdde.game.civilizations import Profile, owned_mask

    catalog = shop()
    castle_age = catalog.get("castle_age")
    assert owned_mask(Profile(purchases=("castle_age", "resource_villagers")), catalog) == (
        2**castle_age.bit
    )
    assert owned_mask(Profile(), catalog) == 0


def test_profiles_raise_bombard_attack_only_for_civilizations_with_bombard_towers() -> None:
    from ancienttdde.game.stock import load_stock

    stock = load_stock(ROOT / "content/balance/stock.json")
    for civilization in load().civilizations:
        lacks = stock.civilization(civilization.id).lacks
        for family, _ in civilization.profile.attack:
            if family == "bombard":
                assert "BOMBARD_TOWER" not in lacks, civilization.key


def test_kill_reward_text_names_what_it_scales() -> None:
    from ancienttdde.game.civilizations import Profile, adjustments

    assert adjustments(Profile(kill_reward_percent=125), {}) == [
        "kill rewards pay 25 percent more stone and wood"
    ]


def test_a_zero_attack_bonus_is_no_adjustment(tmp_path: Path) -> None:
    from ancienttdde.game.civilizations import summary

    data = raw()
    data["default"]["profile"] = {"attack": {"towers": 0, "bombard": 0}}
    profiles = load(write(tmp_path, data))
    assert profiles.default.neutral and profiles.default.attack == ()
    assert summary(profiles.default, profiles.purchase_names) == "no adjustments"


def test_granted_purchases_limited_to_some_civilizations_fit_their_tree() -> None:
    from ancienttdde.game.stock import load_stock

    stock = load_stock(ROOT / "content/balance/stock.json")
    for civilization in load().civilizations:
        lacks = stock.civilization(civilization.id).lacks
        for key in civilization.profile.purchases:
            limit = shop().get(key).only_with
            if limit is not None:
                assert limit[0] not in lacks, (civilization.key, key)


def test_civilizations_the_snapshot_predates_load_without_tree_checks(tmp_path: Path) -> None:
    from ancienttdde.game.civilizations import load_profiles

    data = raw()
    data["civilizations"].append(
        {
            "key": "ATLANTEANS",
            "id": 70,
            "identity": "",
            "profile": {"technologies": ["FLETCHING"], "purchases": ["bombard_attack_400"]},
        }
    )
    assert load(write(tmp_path, data)).by_id(70) is not None
    # Without the snapshot nothing is checked against a tree, as the tests of the loader alone do.
    data["civilizations"][0]["profile"]["attack"] = {"bombard": 5}
    assert load_profiles(write(tmp_path, data), balance(), shop()).by_id(1) is not None


def test_the_default_profile_has_one_display_name() -> None:
    from ancienttdde.game.civilizations import DEFAULT_NAME
    from ancienttdde.game.instructions import instructions

    assert DEFAULT_NAME == "Any other civilization"
    assert f"- {DEFAULT_NAME}: " in instructions(balance(), shop(), load())
