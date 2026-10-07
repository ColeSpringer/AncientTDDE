"""The purchase catalog: one definition per purchase drives its price, pad, caption and effect."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from AoE2ScenarioParser.datasets.techs import TechInfo

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
from ancienttdde.map.geometry import Cell, cells, footprint
from ancienttdde.map.models import FoundationConfig, MapAnchor, MapDocument

type Resource = Literal["food", "wood", "stone", "gold"]
RESOURCES: tuple[Resource, ...] = ("food", "wood", "stone", "gold")
type Payout = Literal["gold", "stone", "king", "attack"]
PAYOUTS: tuple[Payout, ...] = ("gold", "stone", "king", "attack")
# XS keeps a lane's once-only purchases as bits of one 32-bit trigger variable.
OWNERSHIP_BITS = 31


@dataclass(frozen=True)
class TowerAttack:
    family: str
    amount: int


@dataclass(frozen=True)
class Investment:
    """Pays its amount on every whole multiple of its period on the shared economy clock."""

    pays: Payout
    amount: int
    period: int
    family: str | None = None


@dataclass(frozen=True)
class ResourceGrant:
    resource: Resource
    amount: int


@dataclass(frozen=True)
class AgeUp:
    age: Literal["CASTLE_AGE", "IMPERIAL_AGE"]
    upgrade: Literal["GUARD_TOWER", "KEEP"]


@dataclass(frozen=True)
class SpecialTower:
    side: Literal["left", "right"]


@dataclass(frozen=True)
class Villagers:
    area: Literal["build", "economy"]


@dataclass(frozen=True)
class Traders:
    medium: Literal["land", "water"]


@dataclass(frozen=True)
class Relics:
    pass


@dataclass(frozen=True)
class RelicEnclosure:
    pass


@dataclass(frozen=True)
class Population:
    amount: int


@dataclass(frozen=True)
class Castle:
    pass


@dataclass(frozen=True)
class Expansion:
    row: Literal["third", "fourth"]


@dataclass(frozen=True)
class Repair:
    """Restores one life per interval, below the starting total, for the stone cost."""

    interval: int
    stone: int


type Effect = (
    TowerAttack
    | Investment
    | ResourceGrant
    | AgeUp
    | SpecialTower
    | Villagers
    | Traders
    | Relics
    | RelicEnclosure
    | Population
    | Castle
    | Expansion
    | Repair
)


@dataclass(frozen=True)
class Purchase:
    index: int
    key: str
    name: str
    legacy: str
    kings: int
    pad: str
    pad_region: tuple[int, int, int, int]
    label: int | None
    new_sign: tuple[float, float] | None
    once: bool
    requires: str | None
    required_name: str | None
    bit: int
    effect: Effect
    # A technology the buyer's civilization must not have disabled, and what it provides.
    only_with: tuple[str, str] | None = None

    @property
    def price(self) -> str:
        return f"{self.kings} King" + ("" if self.kings == 1 else "s")

    @property
    def caption(self) -> str:
        limits = (
            (", once" if self.once else "")
            + (f", after {self.required_name}" if self.required_name else "")
            + (f", for civilizations with {self.only_with[1]}" if self.only_with else "")
        )
        return f"{self.name}: {self.price}{limits}"


@dataclass(frozen=True)
class Shop:
    purchases: tuple[Purchase, ...]

    def get(self, key: str) -> Purchase:
        for purchase in self.purchases:
            if purchase.key == key:
                return purchase
        raise KeyError(key)

    def investments(self) -> tuple[Purchase, ...]:
        return tuple(p for p in self.purchases if isinstance(p.effect, Investment))

    def attack_family(self) -> str | None:
        """The tower family periodic attack purchases raise; loading allows only one."""
        for purchase in self.investments():
            if isinstance(purchase.effect, Investment) and purchase.effect.family is not None:
                return purchase.effect.family
        return None


def choice[T: str](row: dict[str, object], key: str, options: tuple[T, ...]) -> T:
    value = row.get(key)
    for option in options:
        if value == option:
            return option
    raise ValueError(f"{key} must be one of {', '.join(options)}")


def family(row: dict[str, object], families: Collection[str]) -> str:
    name = text_field(row, "family")
    if name not in families:
        raise ValueError(f"Unknown tower family: {name}")
    return name


def effect(row: dict[str, object], families: Collection[str]) -> Effect:
    match row.get("kind"):
        case "tower_attack":
            return TowerAttack(family(row, families), integer(row, "amount", 1, 1000))
        case "investment":
            pays: Payout = choice(row, "pays", PAYOUTS)
            return Investment(
                pays,
                integer(row, "amount", 1, 10000),
                integer(row, "period", 1, 600),
                family(row, families) if pays == "attack" else None,
            )
        case "resource":
            return ResourceGrant(
                choice(row, "resource", RESOURCES), integer(row, "amount", 1, 30000)
            )
        case "age":
            return AgeUp(
                choice(row, "age", ("CASTLE_AGE", "IMPERIAL_AGE")),
                choice(row, "upgrade", ("GUARD_TOWER", "KEEP")),
            )
        case "special_tower":
            return SpecialTower(choice(row, "side", ("left", "right")))
        case "villagers":
            return Villagers(choice(row, "area", ("build", "economy")))
        case "traders":
            return Traders(choice(row, "medium", ("land", "water")))
        case "relics":
            return Relics()
        case "relic_enclosure":
            return RelicEnclosure()
        case "population":
            return Population(integer(row, "amount", 1, 200))
        case "castle":
            return Castle()
        case "expansion":
            return Expansion(choice(row, "row", ("third", "fourth")))
        case "repair":
            return Repair(integer(row, "interval", 1, 600), integer(row, "stone", 0, 10000))
        case kind:
            raise ValueError(f"Unknown purchase effect: {kind}")


def pad(
    row: dict[str, object], anchors: Mapping[str, MapAnchor]
) -> tuple[str, tuple[int, int, int, int]]:
    key = text_field(row, "pad")
    region = anchors.get(key, MapAnchor()).get("region")
    bounds = anchors.get("shop.bounds", MapAnchor()).get("region")
    if not key.startswith("shop.") or region is None or bounds is None:
        raise ValueError(f"Purchase pad needs a shop region: {key}")
    x1, y1, x2, y2 = region
    if not (bounds[0] <= x1 <= x2 <= bounds[2] and bounds[1] <= y1 <= y2 <= bounds[3]):
        raise ValueError(f"Purchase pad lies outside the shop: {key}")
    return key, (x1, y1, x2, y2)


def label(row: dict[str, object], key: str) -> tuple[int | None, tuple[float, float] | None]:
    sign, new = row.get("sign"), row.get("new_sign")
    if (sign is None) == (new is None):
        raise ValueError(f"Purchase {key} needs exactly one of sign or new_sign")
    if sign is not None:
        return integer(row, "sign", 0, 2**31 - 1), None
    point = cast(list[object], new) if isinstance(new, list) else []
    if len(point) != 2 or any(type(v) not in (int, float) for v in point):
        raise ValueError(f"new_sign must be an [x, y] point: {key}")
    x, y = (float(cast(int | float, v)) for v in point)
    return None, (x, y)


def only_with(row: dict[str, object]) -> tuple[str, str] | None:
    if "only_with" not in row:
        return None
    limit = object_value(row.get("only_with"), "only_with")
    technology = text_field(limit, "technology")
    try:
        TechInfo[technology]
    except KeyError as error:
        raise ValueError(f"Unknown technology: {technology}") from error
    return technology, text_field(limit, "text")


def check_requirements(keys: dict[str, dict[str, object]]) -> None:
    for key in keys:
        seen = {key}
        current = keys[key].get("requires")
        while isinstance(current, str):
            if current in seen:
                raise ValueError(f"Purchase requirements form a cycle: {key}")
            seen.add(current)
            current = keys[current].get("requires")


def load_shop(path: Path, anchors: Mapping[str, MapAnchor], families: Collection[str]) -> Shop:
    """Read and check the catalog against the map's shop pads and the tower families."""
    raw = read_object(path)
    if integer(raw, "schema_version", 1, 1) != 1:
        raise ValueError("Unsupported shop schema")
    entries = rows(raw.get("purchases"), "purchases")
    keys: dict[str, dict[str, object]] = {}
    for row in entries:
        key = text_field(row, "key")
        if key in keys:
            raise ValueError(f"Duplicate purchase key: {key}")
        keys[key] = row
    bits = [key for key, row in keys.items() if row.get("once") is True]
    if len(bits) > OWNERSHIP_BITS:
        raise ValueError(f"At most {OWNERSHIP_BITS} purchases can be once-only")
    purchases: list[Purchase] = []
    for index, (key, row) in enumerate(keys.items(), 1):
        once = row.get("once", False)
        if type(once) is not bool:
            raise ValueError(f"once must be a boolean: {key}")
        requires = row.get("requires")
        required_name: str | None = None
        if requires is not None:
            if requires == key:
                raise ValueError(f"Purchase {key} cannot require itself")
            if not isinstance(requires, str) or requires not in keys:
                raise ValueError(f"Unknown required purchase: {requires}")
            if keys[requires].get("once") is not True:
                raise ValueError(f"Purchase {key} must require a once-only purchase")
            required_name = text_field(keys[requires], "name")
        sign, new_sign = label(row, key)
        pad_key, pad_region = pad(row, anchors)
        bought = effect(object_value(row.get("effect"), "effect"), families)
        if isinstance(bought, Investment | Repair) and not once:
            raise ValueError(f"Investments and repairs must be once-only: {key}")
        purchases.append(
            Purchase(
                index=index,
                key=key,
                name=text_field(row, "name"),
                legacy=text_field(row, "legacy"),
                kings=integer(row, "kings", 1, 100),
                pad=pad_key,
                pad_region=pad_region,
                label=sign,
                new_sign=new_sign,
                once=once,
                requires=requires,
                required_name=required_name,
                bit=bits.index(key) if once else -1,
                effect=bought,
                only_with=only_with(row),
            )
        )
    check_requirements(keys)
    attacks = {
        p.effect.family
        for p in purchases
        if isinstance(p.effect, Investment) and p.effect.pays == "attack"
    }
    if len(attacks) > 1:
        raise ValueError("Periodic attack purchases must share one tower family")
    # The engine keeps one repair schedule and one relic delivery per lane.
    for kind, name in ((Repair, "repair"), (Relics, "relics")):
        if sum(isinstance(p.effect, kind) for p in purchases) > 1:
            raise ValueError(f"At most one {name} purchase is supported")
    return Shop(tuple(purchases))


def check_pads(shop: Shop, data: MapDocument, config: FoundationConfig) -> None:
    """Reject pads that share a tile a King can stand on: XS counts each King on one pad."""
    sizes = {r["stock_id"]: r.get("blocking_size", 0) for r in config["objects"]}
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    claimed: dict[Cell, str] = {}
    for purchase in shop.purchases:
        for cell in sorted(cells(purchase.pad_region) - blocked):
            owner = claimed.setdefault(cell, purchase.key)
            if owner != purchase.key:
                raise ValueError(f"Shop pads of {owner} and {purchase.key} share tile {cell}")


def label_captions(shop: Shop) -> dict[int, str]:
    """Caption every existing label object with all the purchases it labels."""
    captions: dict[int, list[str]] = {}
    for purchase in shop.purchases:
        if purchase.label is not None:
            captions.setdefault(purchase.label, []).append(purchase.caption)
    return {label: " | ".join(texts) for label, texts in captions.items()}
