"""Bind named scenario variables and validated content to the shared XS engine."""

from collections.abc import Mapping
from enum import IntEnum

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.techs import TechInfo
from AoE2ScenarioParser.datasets.units import UnitInfo

from ancienttdde.common.data import asset_text
from ancienttdde.game.catalog import (
    PAYOUTS,
    AgeUp,
    Investment,
    Raider,
    Relics,
    Repair,
    Shop,
    SiegePowerUp,
)
from ancienttdde.game.civilizations import Profile, Profiles, owned_mask
from ancienttdde.game.config import Balance, EngineLane, Towers
from ancienttdde.game.controls import CONTROLS, MODES, controls
from ancienttdde.game.messages import MESSAGES
from ancienttdde.game.sites import RAIDER_MEDIA, TRANSFERS
from ancienttdde.game.spawns import Spawned, center, purchase_spawns
from ancienttdde.scenario.objects import display_name


class State(IntEnum):
    INITIALIZATION = 0
    SETUP = 1
    PREPARATION = 2
    WAVE = 3
    BOSS = 4
    ELIMINATION = 5
    VICTORY = 6
    DEFEAT = 8


# What follows the scheduled waves: nothing yet, endless waves in a solo Endless run, or endless
# waves and a growing loss of lives for every competitor who survives the finale.
STAGES = ("scheduled", "endless", "sudden")
# The pierce armor endless waves may add stays within the engine's 16-bit armor values.
ARMOR_LIMIT = 30000
# Siege positions per lane in the siege tables.
SIEGE_SLOTS = 3


GLOBAL_VARIABLES = (
    "phase",
    "participants",
    "survivors",
    "winner",
    "wave",
    "elapsed",
    "remaining",
    "batches",
    "spawn_clock",
    # Seconds since preparation began; investments and repairs pay on its multiples.
    "economy",
    "resume_phase",
    "sudden_round",
    "configured",
    # What the objectives show: the current wave number and seconds until the next one.
    "display_wave",
    "countdown",
    # The run options: mode, difficulty level and PvP, the lane that chooses them, whether
    # they are fixed, and how many practice controls were used.
    "mode",
    "difficulty",
    "pvp",
    "chooser",
    "locked",
    "assists",
    # Waves cleared, for the result.
    "cleared",
    # After the schedule: the stage, the endless growth level applied and one awaiting the
    # native triggers, the pierce armor added and steps awaiting them, and seconds until sudden
    # death next costs lives. wave_display asks the native triggers to count down to the next
    # endless wave (1) or to clear the countdown when a wave starts (2).
    "stage",
    "endless_level",
    "endless_request",
    "armor",
    "armor_request",
    "drain",
    "wave_display",
    # The siege power-up: its holder, stage (warning, then active), seconds left in the stage,
    # the shared cooldown, and a request to show a countdown for a new stage.
    "siege_owner",
    "siege_phase",
    "siege_left",
    "siege_cooldown",
    "siege_display",
)
# A lane's purchase, King, attack and message fields are requests its native triggers
# acknowledge; owned holds its once-only purchases as bits, kills the kill rewards already paid.
LANE_VARIABLES = (
    "active",
    "lives",
    "initialized",
    "spawn",
    "purchase",
    "cleanup",
    "count",
    "owned",
    "kings",
    "kills",
    "notice",
    "attack",
    "message",
    # A new selection of a control, waiting for the XS to act on it, and the control the lane's
    # player holds selected, which the native triggers keep to notice the next new selection.
    "control",
    "control_held",
    # Seconds until this lane may buy the siege power-up again.
    "siege_cooldown",
    # The native effect set of the lane's civilization profile, 0 for none.
    "profile",
)
# Seconds between repeated explanations of the same refused purchase.
NOTICE_SECONDS = 10
# Kings per lane the shop follows between samples to tell standing Kings from walking ones.
KING_SLOTS = 128
# Consecutive one-second samples a King must stand still on a pad before it pays.
STILL_SAMPLES = 2
# The technology a civilization tech tree disables to remove a tower family member.
# Members without one, such as the Watch Tower the game enables everywhere, are always built.
TOWER_TECHS = {"GUARD_TOWER": "GUARD_TOWER", "KEEP": "KEEP", "BOMBARD_TOWER": "BOMBARD_TOWER"}


def tower_access(towers: Towers) -> tuple[tuple[str, int], ...]:
    """The towers whose availability differs by civilization, in tower family order."""
    access: list[tuple[str, int]] = []
    for _, members in towers.families:
        for member in members:
            name = display_name(member)
            if member in TOWER_TECHS and (name, TechInfo[TOWER_TECHS[member]].ID) not in access:
                access.append((name, TechInfo[TOWER_TECHS[member]].ID))
    return tuple(access)


def variable_names() -> tuple[str, ...]:
    return tuple(f"game.{name}" for name in GLOBAL_VARIABLES) + tuple(
        f"lane.p{p}.{name}" for p in range(1, 8) for name in LANE_VARIABLES
    )


def camel(name: str) -> str:
    return "".join(word.title() for word in name.split("_"))


def table(name: str, values: list[int]) -> str:
    cases = "\n".join(f"    if (index == {i}) return ({value});" for i, value in enumerate(values))
    return f"int {name}(int index = 0) {{\n{cases}\n    return (0);\n}}\n"


def sparse(name: str, values: Mapping[int, int], fallback: int = 0) -> str:
    """A table over scattered indexes; any index it does not list reads the fallback."""
    cases = "\n".join(
        f"    if (index == {i}) return ({v});" for i, v in sorted(values.items()) if v != fallback
    )
    return f"int {name}(int index = 0) {{\n{cases}\n    return ({fallback});\n}}\n"


def sparse_strings(name: str, values: Mapping[int, str], fallback: str) -> str:
    """A string table over scattered indexes; any index it does not list reads the fallback."""
    for value in (*values.values(), fallback):
        xs_text(value, name)
    cases = "\n".join(
        f'    if (index == {i}) return ("{v}");' for i, v in sorted(values.items()) if v != fallback
    )
    return f'string {name}(int index = 0) {{\n{cases}\n    return ("{fallback}");\n}}\n'


def raider_table(profiles: Profiles) -> str:
    """Extra living raiders by medium (1 upward, in RAIDER_MEDIA order) and civilization ID: a
    listed civilization reads its own profile, any other the default."""
    default = profiles.default
    lines = [
        f"    if ((medium == {number}) && (civ == {c.id})) return ({extra});"
        for number, medium in enumerate(RAIDER_MEDIA, 1)
        for c in profiles.civilizations
        if (extra := c.profile.raider_extra(medium)) != default.raider_extra(medium)
    ]
    lines += [
        f"    if (medium == {number}) return ({default.raider_extra(medium)});"
        for number, medium in enumerate(RAIDER_MEDIA, 1)
    ]
    return (
        "int civRaiders(int medium = 1, int civ = 0) {\n"
        + "\n".join(lines)
        + "\n    return (0);\n}\n"
    )


def granted_indexes(profile: Profile, shop: Shop) -> list[int]:
    return [shop.get(key).index for key in profile.purchases]


def grant_slots(profiles: Profiles, shop: Shop) -> int:
    """How many purchases the longest grant list holds; the XS loops over this many slots."""
    lists = [profiles.default, *(c.profile for c in profiles.civilizations)]
    return max(1, *(len(granted_indexes(profile, shop)) for profile in lists))


def grant_table(profiles: Profiles, shop: Shop) -> str:
    """Granted purchase indexes by civilization ID and slot (0 upward), -1 past the last: a
    listed civilization reads its own list, any other the default's."""
    default = granted_indexes(profiles.default, shop)
    slots = grant_slots(profiles, shop)

    def at(listed: list[int], slot: int) -> int:
        return listed[slot] if slot < len(listed) else -1

    lines: list[str] = []
    for civilization in profiles.civilizations:
        own = granted_indexes(civilization.profile, shop)
        lines += [
            f"    if ((civ == {civilization.id}) && (slot == {slot})) return ({at(own, slot)});"
            for slot in range(slots)
            if at(own, slot) != at(default, slot)
        ]
    lines += [f"    if (slot == {slot}) return ({index});" for slot, index in enumerate(default)]
    return (
        "int civGrant(int civ = 0, int slot = 0) {\n" + "\n".join(lines) + "\n    return (-1);\n}\n"
    )


def civilization_tables(profiles: Profiles, shop: Shop) -> str:
    """Per-civilization profile values the XS applies; unlisted civilizations read the default."""
    default = profiles.default
    tables = {
        "civOwned": (
            {c.id: owned_mask(c.profile, shop) for c in profiles.civilizations},
            owned_mask(default, shop),
        ),
        "civKings": ({c.id: c.profile.kings for c in profiles.civilizations}, default.kings),
        "civGoldPercent": (
            {c.id: c.profile.king_gold_percent for c in profiles.civilizations},
            default.king_gold_percent,
        ),
        "civKillPercent": (
            {c.id: c.profile.kill_reward_percent for c in profiles.civilizations},
            default.kill_reward_percent,
        ),
        "civNative": (
            {c.id: profiles.native_index(c.profile) for c in profiles.civilizations},
            profiles.native_index(default),
        ),
    }
    return (
        "".join(sparse(name, values, fallback) for name, (values, fallback) in tables.items())
        + raider_table(profiles)
        + grant_table(profiles, shop)
        + sparse_strings("civName", {c.id: c.name for c in profiles.civilizations}, "")
        + sparse_strings(
            "civText",
            {c.id: profiles.chat(c) for c in profiles.civilizations},
            profiles.chat(None),
        )
    )


def xs_text(value: str, name: str) -> str:
    """Text an XS string table may hold: no quotes or backslashes, and no percent signs, which
    xsChatData reads as format specifiers and refuses."""
    if any(character in value for character in '"\\%'):
        raise ValueError(f"XS text cannot hold quotes, backslashes or percent signs: {name}")
    return value


def strings(name: str, values: list[str]) -> str:
    for value in values:
        xs_text(value, name)
    cases = "\n".join(
        f'    if (index == {i}) return ("{value}");' for i, value in enumerate(values)
    )
    return f'string {name}(int index = 0) {{\n{cases}\n    return ("");\n}}\n'


def render_prelude(
    balance: Balance,
    lanes: tuple[EngineLane, ...],
    shop: Shop,
    profiles: Profiles,
    *,
    extern: bool = False,
) -> str:
    """Declare this build's constants and lookup tables for assets/runtime.xs.

    The parser's xs-check 0.2.30 sees constants declared in another file only when they are
    extern, so the build's prelude sidecar sets extern for checking runtime.xs on its own.
    """
    economy = balance.economy
    difficulty = balance.difficulty
    purchases = shop.purchases
    investments = shop.investments()
    repair = shop.first(Repair)
    repairs = repair.effect if repair and isinstance(repair.effect, Repair) else Repair(1, 0)
    relics = shop.first(Relics)
    siege = shop.first(SiegePowerUp)
    interaction = balance.interaction
    lines = [interaction.raiders.kind(medium).line_ids for medium in RAIDER_MEDIA]
    line_size = max(len(line) for line in lines)
    access = tower_access(balance.towers)
    constants: dict[str, int] = {f"v{camel(n)}": i for i, n in enumerate(GLOBAL_VARIABLES)}
    constants.update({f"f{camel(n)}": i for i, n in enumerate(LANE_VARIABLES)})
    constants.update({f"s{camel(s.name.lower())}": s.value for s in State})
    constants.update({f"cPays{camel(n)}": i for i, n in enumerate(PAYOUTS)})
    constants.update({f"cMessage{camel(key)}": i for i, (key, _) in enumerate(MESSAGES, 1)})
    constants.update({f"cMode{camel(mode)}": i for i, mode in enumerate(MODES)})
    constants.update({f"cStage{camel(stage)}": i for i, stage in enumerate(STAGES)})
    constants.update({f"cControl{camel(c.key)}": i for i, c in enumerate(CONTROLS, 1)})
    constants.update(
        cLaneBase=len(GLOBAL_VARIABLES),
        cLaneStride=len(LANE_VARIABLES),
        cLives=balance.lives,
        cSetup=balance.setup_seconds,
        cPreparation=balance.preparation_seconds,
        cIntermission=balance.intermission_seconds,
        cEnemyCap=balance.max_enemies_per_lane,
        cSuddenInterval=balance.sudden_death_interval,
        cSuddenDamage=balance.sudden_death_damage,
        cWaveCount=len(balance.waves),
        cKing=UnitInfo["KING"].ID,
        cRelic=OtherInfo["RELIC"].ID,
        cWaveKings=economy.wave_kings,
        cKillsPerReward=economy.kills_per_reward,
        cKillStone=economy.kill_stone,
        cKillWood=economy.kill_wood,
        cRewardsPerKing=economy.rewards_per_king,
        cNoticeSeconds=NOTICE_SECONDS,
        cKingSlots=KING_SLOTS,
        cStillSamples=STILL_SAMPLES,
        cTransferCount=len(TRANSFERS),
        cLifeObject=BuildingInfo["OUTPOST"].ID,
        cShopCount=len(purchases),
        cInvestCount=len(investments),
        cRelicsPurchase=relics.index if relics else 0,
        cRepairMask=repair.mask if repair else 0,
        cRepairInterval=repairs.interval,
        cRepairStone=repairs.stone,
        cTowerKinds=len(access),
        cRunOptions=len(controls("run")),
        cCompetitiveLevel=difficulty.competitive,
        cPracticeKings=balance.practice.kings,
        cPracticeResources=balance.practice.resources,
        cEndlessTemplates=len(balance.endless.templates),
        cEndlessLevels=balance.endless_levels,
        cArmorStep=balance.endless.armor_step,
        cArmorLimit=ARMOR_LIMIT,
        cRaiderLineSize=line_size,
        cSiegePurchase=siege.index if siege else 0,
        cSiegeRivalKings=siege.effect.kings_per_rival
        if siege and isinstance(siege.effect, SiegePowerUp)
        else 0,
        cSiegeTrebuchets=interaction.siege.trebuchets_per_rival,
        cSiegeWarning=interaction.siege.warning_seconds,
        cSiegeActive=interaction.siege.active_seconds,
        cSiegeSharedCooldown=interaction.siege.shared_cooldown,
        cSiegeBuyerCooldown=interaction.siege.buyer_cooldown,
        cSiegeSlots=SIEGE_SLOTS,
        cTrebuchet=UnitInfo["TREBUCHET"].ID,
        cPackedTrebuchet=UnitInfo["TREBUCHET_PACKED"].ID,
    )
    stride = len(purchases) + 1
    starts: dict[int, int] = {}
    counts: dict[int, int] = {}
    entries: list[Spawned] = []
    for lane in lanes:
        for purchase in purchases:
            if made := purchase_spawns(lane, purchase, interaction.raiders):
                starts[lane.player * stride + purchase.index] = len(entries)
                counts[lane.player * stride + purchase.index] = len(made)
                entries.extend(made)
    constants.update(
        cSpawnStride=stride,
        cSpawnSlots=max(counts.values(), default=1),
        cGrantSlots=grant_slots(profiles, shop),
    )
    transfers = [(0, 0, 0, 0, 0, 0)] * len(TRANSFERS) + [
        (*lane.sites.transfers[name].pad, *center(lane.sites.transfers[name].arrival))
        for lane in lanes
        for name in TRANSFERS
    ]
    pads = [(0, 0, 0, 0)] + [
        (p.pad_region[0], p.pad_region[1], p.pad_region[2], p.pad_region[3]) for p in purchases
    ]
    invested = [p.effect for p in investments if isinstance(p.effect, Investment)]
    tables: dict[str, list[int]] = {
        "waveUnit": [w.object_id for w in balance.waves],
        "waveCount": [w.count for w in balance.waves],
        "waveBatches": [w.batches for w in balance.waves],
        "waveInterval": [w.interval for w in balance.waves],
        "waveDuration": [w.duration for w in balance.waves],
        "waveBoss": [int(w.boss) for w in balance.waves],
        "waveEnemies": [w.count * w.batches for w in balance.waves],
        # Indexed by level * cWaveCount + wave.
        "waveHitPoints": [
            balance.hit_points(wave, level)
            for level in range(len(difficulty.levels))
            for wave in range(len(balance.waves))
        ],
        # xsGetDifficulty reports -1 for Extreme to 4 for Easiest; the table starts at Extreme.
        "lobbyLevel": [level for _, level in sorted(difficulty.lobby)],
        "kingGold": [level.king_gold for level in difficulty.levels],
        # The medium a purchase buys raiders for: 0 for none, then land and naval.
        "shopRaider": [0]
        + [
            RAIDER_MEDIA.index(p.effect.medium) + 1 if isinstance(p.effect, Raider) else 0
            for p in purchases
        ],
        "raiderCap": [0] + [interaction.raiders.kind(medium).cap for medium in RAIDER_MEDIA],
        # Indexed by medium * cRaiderLineSize + member; a shorter line ends in zeros.
        "raiderLine": [0] * line_size
        + [unit for line in lines for unit in line + (0,) * (line_size - len(line))],
        # Indexed by lane * cSiegeSlots + position, in tenths of a tile at the islet centers.
        "siegeX10": [0] * SIEGE_SLOTS
        + [center(tile)[0] for lane in lanes for tile in lane.sites.siege],
        "siegeY10": [0] * SIEGE_SLOTS
        + [center(tile)[1] for lane in lanes for tile in lane.sites.siege],
        "endlessTemplate": list(balance.endless.templates),
        # Indexed by (level * cEndlessTemplates + template) * cEndlessLevels + growth - 1.
        "endlessHitPoints": [
            balance.endless_hit_points(growth, position, level)
            for level in range(len(difficulty.levels))
            for position in range(len(balance.endless.templates))
            for growth in range(1, balance.endless_levels + 1)
        ],
        "laneSpawnX": [0] + [lane.spawn_x for lane in lanes],
        "laneExitX": [0] + [lane.exit_x for lane in lanes],
        "laneY": [0] + [lane.center_y for lane in lanes],
        "laneLowY": [0] + [lane.path[1] for lane in lanes],
        "laneHighY": [0] + [lane.path[3] for lane in lanes],
        "laneLife": [0] + [lane.life_reference for lane in lanes],
        "laneStallX10": [0] + [center(lane.sites.king_spawn)[0] for lane in lanes],
        "laneStallY10": [0] + [center(lane.sites.king_spawn)[1] for lane in lanes],
        "laneRelicX1": [0] + [lane.sites.relic_column[0] for lane in lanes],
        "laneRelicY1": [0] + [lane.sites.relic_column[1] for lane in lanes],
        "laneRelicX2": [0] + [lane.sites.relic_column[2] for lane in lanes],
        "laneRelicY2": [0] + [lane.sites.relic_column[3] for lane in lanes],
        "laneEconomyX1": [0] + [lane.economy[0] for lane in lanes],
        "laneEconomyY1": [0] + [lane.economy[1] for lane in lanes],
        "laneEconomyX2": [0] + [lane.economy[2] for lane in lanes],
        "laneEconomyY2": [0] + [lane.economy[3] for lane in lanes],
        "enemyType": sorted({w.object_id for w in balance.waves}),
        "shopX1": [pad[0] for pad in pads],
        "shopY1": [pad[1] for pad in pads],
        "shopX2": [pad[2] for pad in pads],
        "shopY2": [pad[3] for pad in pads],
        "shopPrice": [0] + [p.kings for p in purchases],
        "shopMask": [0] + [p.mask for p in purchases],
        "shopRequires": [0] + [shop.get(p.requires).index if p.requires else 0 for p in purchases],
        "shopUpgrade": [0]
        + [TechInfo[p.effect.upgrade].ID if isinstance(p.effect, AgeUp) else 0 for p in purchases],
        "shopTech": [0] + [TechInfo[p.only_with[0]].ID if p.only_with else 0 for p in purchases],
        "spawnUnit": [e.unit for e in entries],
        "spawnGaia": [int(e.gaia) for e in entries],
        "spawnShared": [int(e.shared) for e in entries],
        "spawnX10": [e.x10 for e in entries],
        "spawnY10": [e.y10 for e in entries],
        "transferX1": [t[0] for t in transfers],
        "transferY1": [t[1] for t in transfers],
        "transferX2": [t[2] for t in transfers],
        "transferY2": [t[3] for t in transfers],
        "transferX10": [t[4] for t in transfers],
        "transferY10": [t[5] for t in transfers],
        "investMask": [p.mask for p in investments],
        "investPeriod": [e.period for e in invested],
        "investPays": [PAYOUTS.index(e.pays) for e in invested],
        "investAmount": [e.amount for e in invested],
        "towerTech": [tech for _, tech in access],
    }
    texts: dict[str, list[str]] = {
        "waveKey": [wave.key for wave in balance.waves],
        "towerName": [name for name, _ in access],
        "difficultyName": [level.name for level in difficulty.levels],
        "modeName": [mode.title() for mode in MODES],
        "modeText": [
            "the scheduled waves, then victory",
            "waves keep coming and growing after the finale until the lane falls",
            "practice controls below the shop; the result counts the help used",
        ],
    }
    constants["cEnemyTypes"] = len(tables["enemyType"])
    declaration = "extern const int" if extern else "const int"
    return (
        "\n".join(f"{declaration} {name} = {value};" for name, value in constants.items())
        + "\n"
        + "\n".join(table(name, values) for name, values in tables.items())
        + sparse("spawnStart", starts)
        + sparse("spawnCount", counts)
        + civilization_tables(profiles, shop)
        + "\n".join(strings(name, values) for name, values in texts.items())
    )


def render_xs(
    balance: Balance, lanes: tuple[EngineLane, ...], shop: Shop, profiles: Profiles
) -> str:
    """Prefix the shared runtime with this build's constants and lookup tables.

    The runtime eliminates a lane once xsGetPlayerInGame turns false, which DE reports for
    defeated, resigned and dropped players. assets/runtime.xs is embedded verbatim in the
    game scenario, so notes about it live here rather than in its comments.
    """
    return render_prelude(balance, lanes, shop, profiles) + asset_text("runtime.xs")
