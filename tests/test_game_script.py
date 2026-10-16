"""Execute the generated XS with a small implementation of DE's query API."""

import re
import subprocess
from functools import cache
from pathlib import Path
from typing import cast

import pytest
from conftest import ROOT, WATCH_TOWER, compile_harness, stock

from ancienttdde.common.data import object_value, read_object
from ancienttdde.game.catalog import Population, Shop
from ancienttdde.game.civilizations import Civilization, Profile, Profiles
from ancienttdde.game.config import Balance, EngineLane, Keeper
from ancienttdde.game.sites import SiegeRows
from ancienttdde.map.models import MapAnchor

# Tiles a King walks in a game second in DE, as the harness's KING_SPEED.
KING_SPEED = 1.32
# Civilizations the harness plays that no content defines, so every profile path runs
# whatever the content says: one with every XS-applied adjustment, one neutral.
TEST_CIVILIZATIONS = (
    Civilization(
        "TESTONE",
        100,
        "a test civilization",
        Profile(
            kings=2,
            king_gold_percent=80,
            kill_reward_percent=150,
            raiders=(("land", 1),),
            purchases=("castle_age", "castle", "bombard_attack_400"),
        ),
    ),
    Civilization("TESTTWO", 101, "", Profile()),
    Civilization("TESTFOUR", 103, "", Profile(purchases=("trade_carts",))),
    Civilization(
        "TESTTHREE",
        102,
        "",
        Profile(attack=(("towers", 3), ("bombard", 5)), purchases=("bombard_attack_400",)),
    ),
)


def content() -> tuple[Balance, tuple[EngineLane, ...], Shop, Profiles]:
    from ancienttdde.game.catalog import load_shop
    from ancienttdde.game.civilizations import load_profiles
    from ancienttdde.game.config import load_balance, load_lanes

    balance = load_balance(ROOT / "content/balance/game.json")
    anchors = object_value(read_object(ROOT / "content/maps/foundation.json")["anchors"], "anchors")
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(
        ROOT / "content/balance/shop.json", cast(dict[str, MapAnchor], anchors), families
    )
    profiles = load_profiles(ROOT / "content/balance/civilizations.json", balance, shop)
    return balance, load_lanes(anchors), shop, profiles


@cache
def keeper() -> Keeper:
    from ancienttdde.game.config import load_keeper

    anchors = object_value(read_object(ROOT / "content/maps/foundation.json")["anchors"], "anchors")
    return load_keeper(anchors)


def siege_rows() -> SiegeRows:
    from ancienttdde.game.sites import load_siege_rows

    anchors = object_value(read_object(ROOT / "content/maps/foundation.json")["anchors"], "anchors")
    return load_siege_rows(anchors)


def harness_profiles(profiles: Profiles) -> Profiles:
    return Profiles(
        profiles.default_identity,
        profiles.default,
        profiles.civilizations + TEST_CIVILIZATIONS,
        profiles.purchase_names,
    )


def prelude() -> str:
    from ancienttdde.game.script import render_prelude

    balance, lanes, shop, profiles = content()
    return render_prelude(balance, lanes, shop, profiles, stock(), keeper(), siege_rows())


def filled(text: str, name: str) -> dict[int, int]:
    """An array table's values by index: its fills over the default it was created with."""
    [(size, default)] = re.findall(rf'xsArrayCreateInt\((\d+), (-?\d+), "{name}"\)', text)
    values = dict.fromkeys(range(int(size)), int(default))
    for index, value in re.findall(rf"xsArraySetInt\({name}Table, (\d+), (-?\d+)\);", text):
        values[int(index)] = int(value)
    return values


def fallback(text: str, name: str) -> int:
    """What an array table's accessor reads past its last index."""
    [value] = re.findall(rf"int {name}\(int index = 0\) {{\n.*\n.*return \((-?\d+)\);", text)
    return int(value)


def harness_constants() -> str:
    """Purchase and tower technology names the harness cases use; the game needs none."""
    from ancienttdde.game.script import camel, tower_access

    balance, _, shop, _ = content()
    lines = [f"const int cBuy{camel(p.key)} = {p.index};" for p in shop.purchases]
    # The room the native setup gives a lane, and what the population purchase adds.
    population = shop.get("population").effect
    assert isinstance(population, Population)
    lines.append(f"const int cStartingPopulation = {balance.economy.starting_population};")
    lines.append(f"const int cPopulationAmount = {population.amount};")
    lines += [
        f"const int c{name.replace(' ', '')}Tech = {tech};"
        for name, tech in tower_access(balance.towers)
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def engine_runner(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from ancienttdde.game.script import render_xs

    balance, lanes, shop, profiles = content()
    script = harness_constants() + render_xs(
        balance, lanes, shop, harness_profiles(profiles), stock(), keeper(), siege_rows()
    )
    # XS counted loops implicitly declare/increment their integer counter.
    script = re.sub(
        r"for \((\w+) = ([^;]+); ([<]=?) (.+)\) \{",
        r"for (int \1 = \2; \1 \3 \4; ++\1) {",
        script,
    )
    return compile_harness(
        tmp_path_factory.mktemp("engine-xs"), "engine_xs_harness.cpp", {"// EMBEDDED_XS": script}
    )


def test_prelude_lists_tower_access_from_the_tower_families() -> None:
    from ancienttdde.game.config import Towers
    from ancienttdde.game.script import tower_access

    balance, _, _, _ = content()
    assert tower_access(balance.towers) == (
        ("Guard Tower", 140),
        ("Keep", 63),
        ("Bombard Tower", 64),
    )
    donjons = Towers((("donjons", ("WATCH_TOWER", "DONJON")),), "DONJON", 0, 0, 1)
    assert tower_access(donjons) == ()
    text = prelude()
    assert "const int cTowerKinds = 3;" in text
    assert "int enemyBoss(" in text and "int enemyLives(" in text
    assert 'if (index == 2) return ("Bombard Tower");' in text.split("string towerName")[1]


def test_prelude_names_the_bombard_tower_research() -> None:
    from AoE2ScenarioParser.datasets.techs import TechInfo

    from ancienttdde.game.config import Towers
    from ancienttdde.game.script import bombard_research

    balance, _, _, _ = content()
    assert bombard_research(balance.towers) == TechInfo["BOMBARD_TOWER"].ID
    donjons = Towers((("donjons", ("WATCH_TOWER", "DONJON")),), "DONJON", 0, 0, 1)
    assert bombard_research(donjons) == 0
    text = prelude()
    assert f"const int cBombardTowerResearch = {TechInfo['BOMBARD_TOWER'].ID};" in text


def test_prelude_tables_are_arrays_filled_once() -> None:
    text = prelude()
    # Integer tables are arrays; only the setup and message tables stay if-chains.
    assert not re.search(r"if \(index == \d+\) return \(-?\d+\);", text)
    assert "int shopX1Table = -1;" in text
    assert "void ancientTables()" in text and 'xsArrayCreateInt(40, 0, "shopX1")' in text
    accessor = (
        "int shopX1(int index = 0) {\n    ancientEnsureTables();\n"
        "    if ((index < 0) || (index >= 40)) return (0);\n"
        "    return (xsArrayGetInt(shopX1Table, index));\n}"
    )
    assert accessor in text
    order = [
        "int shopX1Table = -1;",
        "bool ancientTablesReady = false;",
        "void ancientTables() {",
        "void ancientEnsureTables() {",
        "int shopX1(int index = 0) {",
    ]
    assert [text.index(line) for line in order] == sorted(text.index(line) for line in order)
    _, _, shop, _ = content()
    assert filled(text, "shopX1") == {0: 0} | {p.index: p.pad_region[0] for p in shop.purchases}


def test_each_table_fills_in_its_own_function() -> None:
    """No generated function grows past one table's values: the size the earlier lookup
    functions ran at in DE."""
    text = prelude()
    names = re.findall(r'xsArrayCreateInt\(\d+, -?\d+, "(\w+)"\)', text)
    fillers = [f"ancientFill{name[0].upper()}{name[1:]}" for name in names]
    body = text.split("void ancientTables() {\n")[1].split("}")[0]
    assert body.split() == [f"{filler}();" for filler in fillers]
    for name, filler in zip(names, fillers, strict=True):
        fill = text.split(f"void {filler}() {{\n")[1].split("}")[0]
        assert fill.count("xsArrayCreateInt") == 1 and f'"{name}")' in fill
        assert text.index(f"void {filler}()") < text.index("void ancientTables()")


def test_prelude_passes_the_relic_pocket_and_enclosure_and_the_relic_numbers() -> None:
    _, lanes, shop, _ = content()
    text = prelude()
    sites = lanes[0].sites
    for name, region in (("Pocket", sites.relic_pocket), ("Enclosure", sites.relic_enclosure)):
        x1, y1, x2, y2 = region
        assert filled(text, f"lane{name}X1")[1] == x1 and filled(text, f"lane{name}Y1")[1] == y1
        assert filled(text, f"lane{name}X2")[1] == x2 and filled(text, f"lane{name}Y2")[1] == y2
    assert "const int cMonastery = 104;" in text and "const int cMonkWithRelic = 286;" in text
    assert (
        "const int cMonasteryRelics = 10;" in text and "const int cRelicsPerPurchase = 3;" in text
    )
    enclosure = shop.get("relic_enclosure").index
    assert f"const int cRelicEnclosurePurchase = {enclosure};" in text


def test_prelude_counts_still_samples() -> None:
    from ancienttdde.game.script import STILL_SAMPLES

    text = prelude()
    assert f"const int cStillSamples = {STILL_SAMPLES};" in text and STILL_SAMPLES >= 2


def test_prelude_counts_shuffling_kings_that_keep_within_their_radius() -> None:
    """A King kept shuffling for room counts once it has stayed within cShuffleRadius tiles
    of a spot for cShuffleSamples samples; a King walking at its own speed leaves the radius
    first, whatever the pad's shape."""
    from ancienttdde.game.script import SHUFFLE_RADIUS, SHUFFLE_SAMPLES

    text = prelude()
    assert f"const int cShuffleSamples = {SHUFFLE_SAMPLES};" in text
    assert f"const int cShuffleRadius = {SHUFFLE_RADIUS};" in text
    assert SHUFFLE_RADIUS // KING_SPEED < SHUFFLE_SAMPLES


def test_prelude_lists_every_siege_islet_row() -> None:
    """Trebuchets stand on the first islets of every row, so the prelude indexes all eight rows
    by row and position and prices the siege without a per-rival share."""
    from ancienttdde.game.sites import SIEGE_ISLETS, SIEGE_ROWS

    text = prelude()
    assert f"const int cSiegeRows = {SIEGE_ROWS};" in text
    assert f"const int cSiegeSlots = {SIEGE_ISLETS};" in text
    assert "const int cSiegeTrebuchets = 2;" in text and "cSiegeRivalKings" not in text
    xs, ys = filled(text, "siegeX10"), filled(text, "siegeY10")
    assert len(xs) == len(ys) == (SIEGE_ROWS + 1) * SIEGE_ISLETS
    for row, islets in enumerate(siege_rows(), 1):
        for position, (x, y) in enumerate(islets):
            index = row * SIEGE_ISLETS + position
            assert (xs[index], ys[index]) == (10 * x + 5, 10 * y + 5)


def test_prelude_refuses_islet_rows_that_do_not_fit_its_constants() -> None:
    """The XS loops over cSiegeRows rows of cSiegeSlots islets, so the tables must hold them."""
    from ancienttdde.game.script import render_prelude

    balance, lanes, shop, profiles = content()
    rows = siege_rows()
    for broken in (rows[:-1], (*rows[:-1], rows[-1][:2])):
        with pytest.raises(ValueError, match="islet rows"):
            render_prelude(balance, lanes, shop, profiles, stock(), keeper(), broken)


def test_prelude_names_the_keeper_building_and_its_spots() -> None:
    """An enemy holding a lane slot keeps its King and tower on the islet above slot 8's, not
    on a siege row's spare islet, which an Accursed Tower reaches."""
    text = prelude()
    assert f"const int cKeeperBuilding = {WATCH_TOWER};" in text
    spots = keeper()
    assert (spots.lane_king_tile, spots.lane_tower_tile) == ((142, 83), (142, 84))
    assert (spots.king_tile, spots.tower_tile) == ((142, 87), (142, 88))
    # Every cleared lane's King stands around slot 8's tower, one tile each, in lane order.
    assert spots.lane_kings == (
        (141, 87),
        (141, 88),
        (141, 89),
        (142, 89),
        (143, 87),
        (143, 88),
        (143, 89),
    )
    for lane, (x, y) in enumerate(spots.lane_kings, 1):
        assert (filled(text, "keeperX10")[lane], filled(text, "keeperY10")[lane]) == (
            10 * x + 5,
            10 * y + 5,
        )
    assert "cSpareSiegeSlot" not in text
    assert "const int cKeeperKingX10 = 1425;" in text and "const int cKeeperKingY10 = 835;" in text
    assert "const int cKeeperTowerX10 = 1425;" in text
    assert "const int cKeeperTowerY10 = 845;" in text


def test_prelude_declares_message_codes_and_ownership_masks() -> None:
    from ancienttdde.game.messages import MESSAGES, message_code

    _, _, shop, _ = content()
    text = prelude()
    for key, _ in MESSAGES:
        assert (
            f"const int cMessage{''.join(w.title() for w in key.split('_'))} = {message_code(key)};"
            in text
        )
    assert "const int cRepairMask = " in text and "shopBit" not in text
    masks = filled(text, "shopMask")
    assert all(masks[p.index] == (2**p.bit if p.once else 0) for p in shop.purchases)
    assert "int shopName" not in text


def test_prelude_maps_lobby_settings_to_difficulty_levels() -> None:
    balance, _, _, _ = content()
    text = prelude()
    # xsGetDifficulty runs from Extreme (-1) to Easiest (4); the table starts at Extreme.
    assert list(filled(text, "lobbyLevel").values()) == [2, 2, 2, 1, 1, 0]
    assert list(filled(text, "kingGold").values()) == [
        level.king_gold for level in balance.difficulty.levels
    ]
    # The table's bounds, and the level a value outside them plays: the Standard setting's.
    assert "const int cLobbyLow = -1;" in text and "const int cLobbyHigh = 4;" in text
    assert f"const int cFallbackLevel = {balance.difficulty.fallback};" in text
    last = 2 * len(balance.waves) + len(balance.waves) - 1
    assert filled(text, "waveHitPoints")[last] == balance.hit_points(len(balance.waves) - 1, 2)


def test_prelude_lists_the_armor_a_wave_sets_and_the_enemy_variable() -> None:
    """The XS configures each wave on the enemy's definitions itself, whatever number the enemy
    holds: a wave without its own pierce armor reads -1."""
    from ancienttdde.game.script import GLOBAL_VARIABLES, State

    balance, _, _, _ = content()
    text = prelude()
    armor = filled(text, "wavePierceArmor")
    assert armor == {
        index: -1 if wave.pierce_armor is None else wave.pierce_armor
        for index, wave in enumerate(balance.waves)
    }
    keys = [wave.key for wave in balance.waves]
    # The rams keep their own full armor; a tier wave reads its own plus the tier's step.
    assert armor[keys.index("Siege Rams")] == -1
    assert armor[keys.index("Nobunaga")] == stock().unit("NOBUNAGA").armor(3) + 10
    assert f"const int vEnemy = {GLOBAL_VARIABLES.index('enemy')};" in text
    assert f"const int sUnplayable = {State.UNPLAYABLE};" in text
    assert "configured" not in GLOBAL_VARIABLES and "endless_request" not in GLOBAL_VARIABLES


def test_prelude_declares_the_population_rule() -> None:
    """The shop refuses units the lane has no population room for, against DE's headroom and
    population attributes and the game's own limit; relics' monks and the castle take none."""
    balance, _, shop, _ = content()
    text = prelude()
    assert f"const int cPopulationCap = {balance.population_cap};" in text
    assert f"const int cPopulationPurchase = {shop.get('population').index};" in text
    # The runtime reads DE's own attribute constants; the prelude declares no copies.
    from ancienttdde.common.data import asset_text

    runtime = asset_text("runtime.xs")
    assert "cAttributePopulationCap" in runtime and "cAttributePopulation)" in runtime
    # The siege phases are named once, for the prelude, the XS and the protection trigger.
    from ancienttdde.game.script import SIEGE_PHASE_ACTIVE, SIEGE_PHASE_WARNING

    assert (SIEGE_PHASE_WARNING, SIEGE_PHASE_ACTIVE) == (1, 2)
    assert (
        "const int cSiegePhaseWarning = 1;" in text and "const int cSiegePhaseActive = 2;" in text
    )
    assert "cSiegePhaseActive" in runtime and "vSiegePhase, 2)" not in runtime
    assert (
        "vSiegePhase, 1)" not in runtime
        and "== 1) {"
        not in runtime.split("void ancientSiege()")[1].split("ancientEndSiege(false)")[0]
    )
    assert "cAttrHeadroom" not in text + runtime and "cAttrPopulation" not in text + runtime
    from ancienttdde.game.script import GLOBAL_VARIABLES, LANE_VARIABLES

    assert f"const int fFallen = {LANE_VARIABLES.index('fallen')};" in text
    # The siege holds no population room: its trebuchets take none.
    assert "siege_reserved" not in GLOBAL_VARIABLES and "vSiegeReserved" not in text + runtime
    expected = {0: 0} | {p.index: 0 for p in shop.purchases}
    for key, taken in (
        ("building_villagers", 2),
        ("resource_villagers", 2),
        ("trade_carts", 3),
        ("trade_cogs", 3),
        ("land_raider", 1),
        ("naval_raider", 1),
    ):
        expected[shop.get(key).index] = taken
    assert filled(text, "shopPopulation") == expected


def test_prelude_refuses_lanes_whose_purchases_take_different_population() -> None:
    from dataclasses import replace

    from ancienttdde.game.script import render_prelude

    balance, lanes, shop, profiles = content()
    fewer = replace(lanes[1], sites=replace(lanes[1].sites, carts=lanes[1].sites.carts[:2]))
    with pytest.raises(ValueError, match="population"):
        render_prelude(
            balance, (lanes[0], fewer, *lanes[2:]), shop, profiles, stock(), keeper(), siege_rows()
        )


def test_prelude_holds_no_test_only_names() -> None:
    text = prelude()
    assert "cBuy" not in text and "Tech =" not in text
    assert "Testone" not in text and "raiderBonus" not in text


def test_prelude_maps_civilizations_to_their_profiles() -> None:
    _, _, _, profiles = content()
    text = prelude()
    _, _, shop, _ = content()
    from ancienttdde.game.civilizations import owned_mask

    # A civilization the content does not list reads the default profile, inside the table's
    # range and past it.
    default = profiles.default
    for name, value in (
        ("civKings", default.kings),
        ("civGoldPercent", default.king_gold_percent),
        ("civKillPercent", default.kill_reward_percent),
        ("civNative", profiles.native_index(default)),
        ("civOwned", owned_mask(default, shop)),
    ):
        listed = {c.id for c in profiles.civilizations}
        values = filled(text, name)
        assert fallback(text, name) == value, name
        assert all(values[i] == value for i in values if i not in listed), name
    assert filled(text, "civOwned")[18] == 2 ** shop.get("castle_age").bit
    raiders = text.split("int civRaiders")[1].split("}")[0]
    assert "if ((medium == 1) && (civ == 17)) return (1);" in raiders
    assert "if ((medium == 2) && (civ == 11)) return (1);" in raiders
    assert "if (medium == 1) return (0);" in raiders and "if (medium == 2) return (0);" in raiders
    names = text.split("string civName")[1].split("}")[0]
    assert 'if (index == 1) return ("Britons");' in names
    assert 'if (index == 62) return ("Danes");' in names and names.strip().endswith('return ("");')
    texts = text.split("string civText")[1].split("}")[0]
    huns = profiles.by_id(17)
    assert huns is not None
    assert f'if (index == 17) return ("{profiles.chat(huns)}");' in texts
    assert texts.strip().endswith(f'return ("{profiles.chat(None)}");')


def test_prelude_lists_granted_purchases_by_slot() -> None:
    from ancienttdde.game.script import grant_table, render_prelude

    balance, lanes, shop, profiles = content()
    text = render_prelude(
        balance, lanes, shop, harness_profiles(profiles), stock(), keeper(), siege_rows()
    )
    assert "const int cGrantSlots = 3;" in text and "const int cGrantSlots = 1;" in prelude()
    grants = text.split("int civGrant")[1].split("}")[0]
    castle_age, castle = shop.get("castle_age").index, shop.get("castle").index
    assert f"if ((civ == 100) && (slot == 0)) return ({castle_age});" in grants
    assert f"if ((civ == 100) && (slot == 1)) return ({castle});" in grants
    assert (
        f"if ((civ == 100) && (slot == 2)) return ({shop.get('bombard_attack_400').index});"
        in grants
    )
    assert f"if ((civ == 18) && (slot == 0)) return ({castle_age});" in grants
    assert "civ == 101" not in grants and grants.strip().endswith("return (-1);")
    # A default grant reaches every civilization the content does not list, and no other.
    generous = Profiles(
        "",
        Profile(purchases=("trade_carts",)),
        (Civilization("PLAIN", 100, "", Profile()), *profiles.civilizations[:1]),
    )
    table = grant_table(generous, shop)
    carts = shop.get("trade_carts").index
    assert "    if ((civ == 100) && (slot == 0)) return (-1);" in table
    assert "    if (slot == 0) return (" + str(carts) + ");" in table
    assert "civ == 1)" not in table or "if ((civ == 1) && (slot == 0)) return (-1);" in table


def test_raider_table_gives_listed_civilizations_their_own_counts() -> None:
    from ancienttdde.game.script import raider_table

    plain = Civilization("PLAIN", 100, "", Profile())
    sailor = Civilization("SAILOR", 101, "", Profile(raiders=(("naval", 1),)))
    table = raider_table(Profiles("", Profile(raiders=(("land", 1),)), (plain, sailor)))
    assert "    if ((medium == 1) && (civ == 100)) return (0);" in table
    assert "    if ((medium == 1) && (civ == 101)) return (0);" in table
    assert "    if ((medium == 2) && (civ == 101)) return (1);" in table
    assert "civ == 100)) return (1)" not in table
    assert (
        "    if (medium == 1) return (1);" in table and "    if (medium == 2) return (0);" in table
    )


@pytest.mark.parametrize(
    "case",
    [
        "cleared_lanes",
        "slots",
        "ai_departures",
        "no_humans",
        "initialize",
        "solo",
        "defeat",
        "simultaneous",
        "survivor",
        "sudden",
        "resume",
        "cap",
        "resign",
        "leaks",
        "exit_arrival",
        "first_wave",
        "first_wave_marks",
        "shop_exact",
        "shop_repeat",
        "shop_walking",
        "shop_insufficient",
        "shop_once",
        "shop_requires",
        "shop_pending",
        "shop_relics",
        "shop_monasteries",
        "shop_inactive",
        "gold_kings",
        "kill_rewards",
        "wave_kings",
        "investments",
        "attack_investment",
        "attack_chunks",
        "attack_750",
        "repair",
        "life_display",
        "tower_access",
        "shop_walk_across",
        "shop_walk_rows",
        "shop_single_file",
        "shop_settle",
        "spawn_blocked",
        "spawn_unchecked",
        "spawn_built_over",
        "king_stall_shared",
        "shop_civ_lacks",
        "age_upgrades",
        "bombard_on_chemistry",
        "status_display",
        "pending_elimination",
        "tower_access_none",
        "shop_pause",
        "shop_requires_together",
        "notice_change",
        "options_default",
        "options_competitive",
        "pvp_opt_in",
        "difficulty_hard",
        "difficulty_competitive",
        "difficulty_unknown",
        "options_choose",
        "options_reload_held",
        "options_chooser_only",
        "options_solo_only",
        "options_pvp_solo",
        "options_pvp_only_its_own",
        "options_chooser_leaves",
        "options_locked",
        "practice_controls",
        "practice_next_wave",
        "practice_refused",
        "results_victory",
        "results_practice",
        "results_defeat",
        "sudden_survivor",
        "endless_continues",
        "endless_waves",
        "endless_configures",
        "endless_armor_past_255",
        "endless_result",
        "resume_endless",
        "raider_pvp_off",
        "raider_before_first_wave",
        "raider_solo",
        "raider_buy",
        "raider_cap",
        "raider_line",
        "raider_civilization",
        "profile_default",
        "profile_kings",
        "profile_gold",
        "profile_kills",
        "profile_text",
        "profile_grant_blocked",
        "profile_grant_tree",
        "profile_purchase",
        "profile_attack",
        "siege_price",
        "siege_exclusive",
        "siege_timeline",
        "siege_buyer_waits",
        "siege_owner_eliminated",
        "siege_resume",
        "siege_tie",
        "turns_fair",
        "kill_rewards_waves_only",
        "siege_holder_again",
        "sudden_labels",
        "practice_repeat",
        "shared_arrivals",
        "economy_towers",
        "choice_timeout",
        "choice_once",
        "spawn_rows",
        "spawn_silent",
        "walk_watchdog",
        "shop_cached_pad_moves",
        "shop_shuffling_kings",
        "shop_wanderer_recalled",
        "collect_sweep",
        "boss_hitpoints",
        "boss_leak",
        "pvp_waits_for_first_wave",
        "enemy_last_computer",
        "enemy_first_slot",
        "enemy_missing",
        "enemy_refused",
        "enemy_human_eighth",
        "wave_hitpoints",
        "shop_population",
        "shop_population_limit",
        "population_repeat",
        "shop_relics_free",
        "siege_free",
        "raider_population",
        "grant_headroom",
        "fallen_after_result",
        "fallen_competitive",
        "population_limit_first",
        "next_line_armor",
    ],
)
def test_shared_engine(engine_runner: Path, case: str) -> None:
    result = subprocess.run([str(engine_runner), case], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_xs_text_tables_reject_percent_signs() -> None:
    from ancienttdde.game.script import sparse_strings, strings

    with pytest.raises(ValueError, match="percent"):
        strings("civName", ["Castle Age (5% off)"])
    with pytest.raises(ValueError, match="percent"):
        sparse_strings("civText", {1: "100% more"}, "")
    with pytest.raises(ValueError, match="percent"):
        sparse_strings("civText", {}, "a 10% discount")
