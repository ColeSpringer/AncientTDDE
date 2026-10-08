"""Civilization profiles: what each civilization gets on top of its own technology tree.

A profile is a small set of adjustments, neutral unless the content says otherwise. The XS
applies Kings, King prices, kill rewards and raider caps; native triggers apply the rest once a
lane is initialized. A civilization without an explicit profile plays the default one.
"""

import re
from collections.abc import Mapping
from dataclasses import astuple, dataclass, field, fields
from functools import cached_property
from pathlib import Path
from typing import cast

from AoE2ScenarioParser.datasets.object_support import CivilizationOld

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
from ancienttdde.game.catalog import RESOURCES, Raider, Shop, SiegePowerUp, Traders
from ancienttdde.game.config import RESERVED_TECHNOLOGIES, UNRESEARCHABLE, Balance, Resources
from ancienttdde.game.restricted import POINTLESS, TECHNOLOGIES
from ancienttdde.game.sites import RAIDER_MEDIA, TRADE_MEDIA, RaiderMedium, TradeMedium
from ancienttdde.game.stock import Stock
from ancienttdde.scenario.objects import display_name, technology

# How the instructions and tables name the profile of a civilization the content does not list.
DEFAULT_NAME = "Any other civilization"
# Civilization IDs as xsGetPlayerCivilization reports them. The pinned dataset names the first
# of them; later civilizations are listed by the index DE gives them.
MAX_CIVILIZATION = 255
KNOWN_CIVILIZATIONS: dict[str, int] = {
    member.name: member.value for member in CivilizationOld if 0 < member.value <= MAX_CIVILIZATION
}
# Gaia and the random choices: dataset names no player's civilization ever reports.
NOT_PLAYABLE = frozenset(member.name for member in CivilizationOld) - KNOWN_CIVILIZATIONS.keys()
FIRST_NEWER_CIVILIZATION = max(KNOWN_CIVILIZATIONS.values()) + 1
NO_RESOURCES = Resources(0, 0, 0, 0)


@dataclass(frozen=True)
class NativeEffects:
    """The adjustments a lane's native triggers apply once: everything the XS cannot."""

    resources: Resources = NO_RESOURCES
    population: int = 0
    technologies: tuple[str, ...] = ()
    attack: tuple[tuple[str, int], ...] = ()
    tower_hit_points: int = 0
    tower_stone: int = 0
    relics: int = 0
    traders: tuple[tuple[TradeMedium, int], ...] = ()
    # Shop purchases the lane holds from the start, by key.
    purchases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Profile:
    kings: int = 0
    resources: Resources = NO_RESOURCES
    king_gold_percent: int = 100
    kill_reward_percent: int = 100
    attack: tuple[tuple[str, int], ...] = ()
    tower_hit_points: int = 0
    tower_stone: int = 0
    relics: int = 0
    traders: tuple[tuple[TradeMedium, int], ...] = ()
    technologies: tuple[str, ...] = ()
    population: int = 0
    raiders: tuple[tuple[RaiderMedium, int], ...] = ()
    purchases: tuple[str, ...] = ()

    def raider_extra(self, medium: RaiderMedium) -> int:
        return sum(extra for found, extra in self.raiders if found == medium)

    @property
    def native(self) -> NativeEffects | None:
        """The adjustments native triggers apply: every field NativeEffects shares."""
        effects = NativeEffects(**{f.name: getattr(self, f.name) for f in fields(NativeEffects)})
        return None if effects == NativeEffects() else effects

    @property
    def neutral(self) -> bool:
        return self == Profile()


@dataclass(frozen=True)
class NativeWorth:
    """What a civilization's own bonuses are worth here, estimated by hand in Kings over a
    run: in a solo run, and on top of that with PvP on. Bonuses the scenario levels or rules
    out count for nothing."""

    solo: float = 0.0
    pvp: float = 0.0


@dataclass(frozen=True)
class Civilization:
    key: str
    id: int
    # One sentence part about the civilization's own bonuses that matter here; may be empty.
    identity: str
    profile: Profile
    native: NativeWorth = NativeWorth()

    @property
    def name(self) -> str:
        return display_name(self.key)


@dataclass(frozen=True)
class Profiles:
    default_identity: str
    default: Profile
    civilizations: tuple[Civilization, ...]
    # What each shop purchase is called, for the lines that name granted purchases.
    purchase_names: Mapping[str, str] = field(default_factory=dict[str, str])

    def by_id(self, civilization_id: int) -> Civilization | None:
        for civilization in self.civilizations:
            if civilization.id == civilization_id:
                return civilization
        return None

    def raider_bonuses(self) -> tuple[tuple[str, RaiderMedium, int], ...]:
        """Every extra living raider a civilization keeps, by key, medium and amount."""
        return tuple(
            sorted(
                (civilization.key, medium, extra)
                for civilization in self.civilizations
                for medium, extra in civilization.profile.raiders
            )
        )

    def text(self, civilization: Civilization | None) -> str:
        """The instructions' line about a civilization; None describes the default."""
        if civilization is None:
            return profile_text(self.default_identity, self.default, self.purchase_names)
        return profile_text(civilization.identity, civilization.profile, self.purchase_names)

    def chat(self, civilization: Civilization | None) -> str:
        """The short line the game chats for a lane: the adjustments alone."""
        if civilization is None:
            return "default profile: " + summary(self.default, self.purchase_names)
        return summary(civilization.profile, self.purchase_names)

    @cached_property
    def native_sets(self) -> tuple[NativeEffects, ...]:
        """The distinct native effect sets, the default's first when it has any."""
        groups: dict[NativeEffects, None] = {}
        for profile in (self.default, *(c.profile for c in self.civilizations)):
            effects = profile.native
            if effects is not None:
                groups.setdefault(effects)
        return tuple(groups)

    def native_groups(self) -> tuple[NativeEffects, ...]:
        return self.native_sets

    def native_index(self, profile: Profile) -> int:
        """The profile's native effect set as the triggers number them: 1 upward, 0 for none."""
        effects = profile.native
        return 0 if effects is None else self.native_sets.index(effects) + 1


def plural(amount: int, word: str) -> str:
    return word if amount == 1 else word + "s"


def owned_mask(profile: Profile, shop: Shop) -> int:
    """The ownership bits of the once-only purchases a profile grants, as the XS keeps them."""
    return sum(shop.get(key).mask for key in profile.purchases)


def adjustments(profile: Profile, names: Mapping[str, str]) -> list[str]:
    """Each adjustment as players read it, in the order the profile lists them."""
    parts: list[str] = []
    if profile.kings:
        parts.append(f"+{profile.kings} starting {plural(profile.kings, 'King')}")
    amounts: tuple[int, int, int, int] = astuple(profile.resources)
    for name, amount in zip(("food", "wood", "stone", "gold"), amounts, strict=True):
        if amount:
            parts.append(f"+{amount} {name}")
    if profile.king_gold_percent != 100:
        less = 100 - profile.king_gold_percent
        parts.append(f"Kings cost {abs(less)} percent {'less' if less > 0 else 'more'} gold")
    if profile.kill_reward_percent != 100:
        more = profile.kill_reward_percent - 100
        parts.append(
            f"kill rewards pay {abs(more)} percent {'more' if more > 0 else 'less'} stone and wood"
        )
    for family, amount in profile.attack:
        kind = "tower" if family == "towers" else f"{family} tower"
        parts.append(f"+{amount} {kind} attack")
    if profile.tower_hit_points:
        parts.append(f"+{profile.tower_hit_points} tower hit points")
    if profile.tower_stone:
        parts.append(f"towers cost {profile.tower_stone} less stone")
    if profile.relics:
        parts.append(f"+{profile.relics} starting {plural(profile.relics, 'relic')}")
    for medium, amount in profile.traders:
        trader = "cart" if medium == "land" else "cog"
        parts.append(f"+{amount} starting trade {plural(amount, trader)}")
    for name in profile.technologies:
        parts.append(f"{display_name(name)} researched")
    if profile.population:
        parts.append(f"+{profile.population} population")
    for key in profile.purchases:
        parts.append(f"{names.get(key, key)} from the start")
    for medium, amount in profile.raiders:
        parts.append(f"+{amount} {medium} {plural(amount, 'raider')} with PvP on")
    return parts


def summary(profile: Profile, names: Mapping[str, str]) -> str:
    changes = adjustments(profile, names)
    return ", ".join(changes) if changes else "no adjustments"


def profile_text(identity: str, profile: Profile, names: Mapping[str, str]) -> str:
    changes = adjustments(profile, names)
    listed = f"adjustments: {', '.join(changes)}" if changes else "no adjustments"
    return f"{identity}; {listed}" if identity else listed


def civilization_text(value: object, label: str) -> str:
    """Text the XS chats or the instructions print; it may be empty."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    if any(character in value for character in '"\\%'):
        raise ValueError(
            f"Civilization text cannot hold quotes, backslashes or percent signs: {label}"
        )
    return value


def bounded(row: dict[str, object], key: str, low: int, high: int) -> int:
    return integer(row, key, low, high) if key in row else 0


def media[T: str](
    raw: dict[str, object], key: str, allowed: tuple[T, ...]
) -> tuple[tuple[T, int], ...]:
    """Counts by medium, in the media's order; a missing or zero count is left out."""
    if key not in raw:
        return ()
    counts = object_value(raw.get(key), key)
    for medium in counts:
        if medium not in allowed:
            raise ValueError(f"{key} must name {' or '.join(allowed)}: {medium}")
    found = [(medium, bounded(counts, medium, 0, 3)) for medium in allowed]
    return tuple((medium, extra) for medium, extra in found if extra > 0)


def profile_technologies(raw: dict[str, object], balance: Balance) -> tuple[str, ...]:
    names = raw.get("technologies", [])
    if not isinstance(names, list):
        raise ValueError("technologies must list technology names")
    listed: list[str] = []
    for name in cast(list[object], names):
        if not isinstance(name, str):
            raise ValueError("technologies must list technology names")
        identifier = technology(name)
        if name in RESERVED_TECHNOLOGIES:
            raise ValueError(f"{name} cannot be a profile technology: the game grants or sells it")
        if name in UNRESEARCHABLE or identifier in TECHNOLOGIES or identifier in POINTLESS:
            raise ValueError(f"{name} cannot be a profile technology: the game rules it out")
        if name in balance.economy.starting_technologies:
            raise ValueError(f"{name} is a starting technology")
        if name in listed:
            raise ValueError(f"Technology listed twice: {name}")
        listed.append(name)
    return tuple(listed)


PROFILE_SETTINGS = frozenset(
    {
        "kings",
        "resources",
        "king_gold_percent",
        "kill_reward_percent",
        "attack",
        "tower_hit_points",
        "tower_stone",
        "relics",
        "traders",
        "technologies",
        "population",
        "raiders",
        "purchases",
    }
)


def granted_purchases(raw: dict[str, object], shop: Shop) -> tuple[str, ...]:
    keys = raw.get("purchases", [])
    if not isinstance(keys, list):
        raise ValueError("purchases must list purchase keys")
    listed: list[str] = []
    for key in cast(list[object], keys):
        if not isinstance(key, str):
            raise ValueError("purchases must list purchase keys")
        try:
            purchase = shop.get(key)
        except KeyError as error:
            raise ValueError(f"Unknown purchase: {key}") from error
        if isinstance(purchase.effect, Raider | SiegePowerUp):
            raise ValueError(f"{key} cannot be granted: raiders and the siege act on rivals")
        if key in listed:
            raise ValueError(f"Purchase listed twice: {key}")
        if purchase.requires is not None and purchase.requires not in listed:
            raise ValueError(f"{key} needs {purchase.requires} granted as well")
        listed.append(key)
    return tuple(listed)


def load_profile(raw: dict[str, object], balance: Balance, shop: Shop) -> Profile:
    for key in raw:
        if key not in PROFILE_SETTINGS:
            raise ValueError(f"Unknown profile setting: {key}")
    resources = object_value(raw.get("resources", {}), "resources")
    for name in resources:
        if name not in RESOURCES:
            raise ValueError(f"resources must name food, wood, stone or gold: {name}")
    attack = object_value(raw.get("attack", {}), "attack")
    families = [name for name, _ in balance.towers.families]
    for family in attack:
        if family not in families:
            raise ValueError(f"Unknown tower family: {family}")
    amounts = [(family, bounded(attack, family, 0, 200)) for family in families]
    traders: tuple[tuple[TradeMedium, int], ...] = media(raw, "traders", TRADE_MEDIA)
    purchases = granted_purchases(raw, shop)
    for key in purchases:
        effect = shop.get(key).effect
        if isinstance(effect, Traders) and any(medium == effect.medium for medium, _ in traders):
            raise ValueError(
                f"{key} cannot be granted beside starting {effect.medium} traders: they share spots"
            )
    return Profile(
        kings=bounded(raw, "kings", 0, 5),
        resources=Resources(*(bounded(resources, name, 0, 10000) for name in RESOURCES)),
        king_gold_percent=integer(raw, "king_gold_percent", 50, 150)
        if "king_gold_percent" in raw
        else 100,
        kill_reward_percent=integer(raw, "kill_reward_percent", 50, 300)
        if "kill_reward_percent" in raw
        else 100,
        attack=tuple((family, amount) for family, amount in amounts if amount > 0),
        tower_hit_points=bounded(raw, "tower_hit_points", 0, 3000),
        tower_stone=bounded(raw, "tower_stone", 0, 100),
        relics=bounded(raw, "relics", 0, 3),
        traders=traders,
        technologies=profile_technologies(raw, balance),
        population=bounded(raw, "population", 0, 100),
        raiders=media(raw, "raiders", RAIDER_MEDIA),
        purchases=purchases,
    )


NATIVE_SETTINGS = frozenset({"solo", "pvp"})


def worth(raw: dict[str, object], key: str) -> float:
    value = raw.get(key, 0)
    if type(value) not in (int, float) or not 0 <= cast(int | float, value) <= 5:
        raise ValueError(f"{key} must be a number between 0 and 5")
    return float(cast(int | float, value))


def native_worth(row: dict[str, object]) -> NativeWorth:
    if "native" not in row:
        return NativeWorth()
    raw = object_value(row.get("native"), "native")
    for key in raw:
        if key not in NATIVE_SETTINGS:
            raise ValueError(f"Unknown native setting: {key}")
    return NativeWorth(solo=worth(raw, "solo"), pvp=worth(raw, "pvp"))


ROW_SETTINGS = frozenset({"key", "id", "identity", "profile", "native"})
DEFAULT_SETTINGS = frozenset({"identity", "profile"})


def check_settings(row: dict[str, object], allowed: frozenset[str], label: str) -> None:
    for key in row:
        if key not in allowed:
            raise ValueError(f"Unknown {label} setting: {key}")


def check_tree(key: str, profile: Profile, shop: Shop, balance: Balance, stock: Stock) -> None:
    """A profile may not grant what the civilization's own technology tree rules out, as the
    stock data snapshot records it; a civilization the snapshot predates is not checked."""
    for name in profile.technologies:
        if name not in stock.technologies:
            raise ValueError(f"{name} is not in the stock snapshot; add it to the watched ones")
    record = stock.find(by_key(key))
    if record is None:
        return
    for name in profile.technologies:
        if name in record.lacks:
            raise ValueError(f"{key} cannot research {name}")
    for purchase_key in profile.purchases:
        limit = shop.get(purchase_key).only_with
        if limit is not None and limit[0] in record.lacks:
            raise ValueError(f"{key} cannot be granted {purchase_key}: it needs {limit[1]}")
    for family, _ in profile.attack:
        members = next(m for name, m in balance.towers.families if name == family)
        if all(member in record.lacks for member in members):
            lacked = " and ".join(f"{display_name(member)}s" for member in members)
            raise ValueError(f"{key} cannot raise {family} attack: it lacks {lacked}")


def by_key(key: str) -> int:
    return KNOWN_CIVILIZATIONS.get(key, 0)


def load_profiles(path: Path, balance: Balance, shop: Shop, stock: Stock | None = None) -> Profiles:
    """Read the profiles; with the stock data snapshot, every profile is also checked against
    its civilization's technology tree."""
    raw = read_object(path)
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported civilizations schema")
    default = object_value(raw.get("default"), "default")
    check_settings(default, DEFAULT_SETTINGS, "default")
    civilizations: list[Civilization] = []
    for row in rows(raw.get("civilizations"), "civilizations"):
        check_settings(row, ROW_SETTINGS, "civilization")
        key = text_field(row, "key")
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key) is None:
            raise ValueError(f"Civilization keys are uppercase identifiers: {key}")
        if key in {c.key for c in civilizations}:
            raise ValueError(f"Duplicate civilization key: {key}")
        if key in NOT_PLAYABLE:
            raise ValueError(f"{key} is not a playable civilization")
        identifier = integer(row, "id", 1, MAX_CIVILIZATION)
        known = KNOWN_CIVILIZATIONS.get(key)
        if known is not None and identifier != known:
            raise ValueError(f"{key} must carry its dataset id {known}")
        if known is None and identifier < FIRST_NEWER_CIVILIZATION:
            raise ValueError(
                f"{key} is not in the dataset: its id must be {FIRST_NEWER_CIVILIZATION} or more"
            )
        if identifier in {c.id for c in civilizations}:
            raise ValueError(f"Duplicate civilization id: {identifier}")
        profile = load_profile(object_value(row.get("profile", {}), "profile"), balance, shop)
        if stock is not None:
            check_tree(key, profile, shop, balance, stock)
        civilizations.append(
            Civilization(
                key=key,
                id=identifier,
                identity=civilization_text(row.get("identity", ""), key),
                profile=profile,
                native=native_worth(row),
            )
        )
    return Profiles(
        default_identity=civilization_text(default.get("identity", ""), "default"),
        default=load_profile(object_value(default.get("profile", {}), "profile"), balance, shop),
        civilizations=tuple(civilizations),
        purchase_names={purchase.key: purchase.name for purchase in shop.purchases},
    )
