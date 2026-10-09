"""The purchase catalog: one definition per purchase drives its price, pad, caption and effect."""

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from ancienttdde.common.data import integer, object_value, read_object, rows, text_field
from ancienttdde.game.sites import RAIDER_MEDIA, RaiderMedium, TradeMedium
from ancienttdde.map.geometry import Cell, blocking_sizes, cells, flood, footprint
from ancienttdde.map.models import FoundationConfig, MapAnchor, MapDocument
from ancienttdde.scenario.objects import technology
from ancienttdde.scenario.snapshot import MapUnit

type Resource = Literal["food", "wood", "stone", "gold"]
RESOURCES: tuple[Resource, ...] = ("food", "wood", "stone", "gold")
type Payout = Literal["gold", "stone", "king", "attack"]
PAYOUTS: tuple[Payout, ...] = ("gold", "stone", "king", "attack")
# XS keeps a lane's once-only purchases as bits of one 32-bit trigger variable.
OWNERSHIP_BITS = 31
# A display unit stands within this many tiles of the pad it names.
DISPLAY_REACH = 4.0


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
    medium: TradeMedium


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


@dataclass(frozen=True)
class Raider:
    """A living raider for the buyer's side of a trade area, while PvP is on."""

    medium: RaiderMedium


@dataclass(frozen=True)
class SiegePowerUp:
    """Exclusive temporary siege near every rival; the price rises with each surviving rival."""

    kings_per_rival: int


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
    | Raider
    | SiegePowerUp
)


@dataclass(frozen=True)
class Purchase:
    index: int
    key: str
    name: str
    # The short form of the name DE draws above the exhibit, with the price: written in the
    # catalog, or taken from the effect's own numbers where those say it all.
    label: str
    # The original purchase this one restores; purchases the original lacked have none.
    legacy: str | None
    kings: int
    pad: str
    pad_region: tuple[int, int, int, int]
    # The exhibit beside the pad that is renamed to this purchase, as in the original map: a
    # placed object, which stays where the map put it, or a King the build places where the
    # original's mod had a named object.
    display: int | None
    # Where the build places that King.
    display_at: tuple[float, float] | None
    once: bool
    requires: str | None
    required_name: str | None
    bit: int
    effect: Effect
    # A technology the buyer's civilization must not have disabled, and what it provides.
    only_with: tuple[str, str] | None = None

    def surcharge(self, wording: str) -> str:
        """The siege power-up's extra Kings per surviving rival, in the given wording."""
        if isinstance(self.effect, SiegePowerUp):
            return wording.format(self.effect.kings_per_rival)
        return ""

    @property
    def price(self) -> str:
        kings = f"{self.kings} King" + ("" if self.kings == 1 else "s")
        return kings + self.surcharge(" plus {} per surviving rival")

    @property
    def tag(self) -> str:
        """The caption DE draws above the exhibit, kept short: the font does not shrink with
        the view, so long lines run into each other once the view is zoomed out."""
        kings = f"{self.kings} King" + ("" if self.kings == 1 else "s")
        return f"{self.label}: {kings}" + self.surcharge(" +{}/rival")

    @property
    def pvp(self) -> bool:
        """Sold only while PvP is on: these purchases act on rivals."""
        return isinstance(self.effect, Raider | SiegePowerUp)

    @property
    def mask(self) -> int:
        """The ownership bit as the value XS divides by; repeatable purchases have none."""
        return 2**self.bit if self.bit >= 0 else 0

    @property
    def brief(self) -> str:
        """The name and the price, which open the name DE shows on selection."""
        return f"{self.name}: {self.price}"

    @property
    def caption(self) -> str:
        limits = (
            (", once" if self.once else "")
            + (f", after {self.required_name}" if self.required_name else "")
            + (f", for civilizations with {self.only_with[1]}" if self.only_with else "")
            + (", when PvP is on" if self.pvp else "")
        )
        return f"{self.brief}{limits}"


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

    def first(self, kind: type[object]) -> Purchase | None:
        """The first purchase with an effect of this kind, in catalog order."""
        return next((p for p in self.purchases if isinstance(p.effect, kind)), None)


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
        case "raider":
            return Raider(choice(row, "medium", RAIDER_MEDIA))
        case "siege":
            return SiegePowerUp(integer(row, "kings_per_rival", 1, 20))
        case kind:
            raise ValueError(f"Unknown purchase effect: {kind}")


def every(period: int) -> str:
    if period < 60:
        return f"{period} s"
    return "min" if period == 60 else f"{period / 60:g} min"


def derived_label(effect: Effect) -> str | None:
    """The label for an effect whose numbers say it all, so the catalog cannot misstate them."""
    match effect:
        case TowerAttack(family="towers", amount=amount):
            return f"+{amount} attack"
        case Investment(pays="attack", amount=amount, period=period):
            return f"+{amount} attack/{every(period)}"
        case Investment(pays="king", amount=amount, period=period):
            return f"{amount} King{'' if amount == 1 else 's'}/{every(period)}"
        case Investment(pays=pays, amount=amount, period=period):
            return f"{amount} {pays}/{every(period)}"
        case ResourceGrant(resource=resource, amount=amount):
            return f"{amount} {resource}"
        case AgeUp(age=age):
            return "Castle Age" if age == "CASTLE_AGE" else "Imperial Age"
        case Population(amount=amount):
            return f"+{amount} population"
        case Expansion(row=row):
            return ("3rd" if row == "third" else "4th") + " tower row"
        case _:
            return None


def label(row: dict[str, object], key: str, bought: Effect) -> str:
    if "label" in row:
        return text_field(row, "label")
    text = derived_label(bought)
    if text is None:
        raise ValueError(f"Purchase {key} needs a label: its effect does not name one")
    return text


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


def only_with(row: dict[str, object]) -> tuple[str, str] | None:
    if "only_with" not in row:
        return None
    limit = object_value(row.get("only_with"), "only_with")
    name = text_field(limit, "technology")
    technology(name)
    return name, text_field(limit, "text")


def display(row: dict[str, object], key: str) -> tuple[int | None, tuple[float, float] | None]:
    placed, created = row.get("display"), row.get("display_at")
    if (placed is None) == (created is None):
        raise ValueError(f"Purchase {key} needs exactly one of display or display_at")
    if placed is not None:
        return integer(row, "display", 1, 2**31 - 1), None
    point = cast(list[object], created) if isinstance(created, list) else []
    if len(point) != 2 or any(type(v) not in (int, float) for v in point):
        raise ValueError(f"display_at must be an [x, y] point: {key}")
    x, y = (float(cast(int | float, v)) for v in point)
    return None, (x, y)


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
    if raw.get("schema_version") != 4:
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
        pad_key, pad_region = pad(row, anchors)
        placed, created = display(row, key)
        bought = effect(object_value(row.get("effect"), "effect"), families)
        if isinstance(bought, Investment | Repair) and not once:
            raise ValueError(f"Investments and repairs must be once-only: {key}")
        purchases.append(
            Purchase(
                index=index,
                key=key,
                name=text_field(row, "name"),
                label=label(row, key, bought),
                legacy=text_field(row, "legacy") if "legacy" in row else None,
                kings=integer(row, "kings", 1, 100),
                pad=pad_key,
                pad_region=pad_region,
                display=placed,
                display_at=created,
                once=once,
                requires=requires,
                required_name=required_name,
                bit=bits.index(key) if once else -1,
                effect=bought,
                only_with=only_with(row),
            )
        )
    check_requirements(keys)
    # The engine keeps one repair schedule, one relic delivery and one siege holder.
    for kind, name in ((Repair, "repair"), (Relics, "relics"), (SiegePowerUp, "siege")):
        if sum(isinstance(p.effect, kind) for p in purchases) > 1:
            raise ValueError(f"At most one {name} purchase is supported")
    for medium in RAIDER_MEDIA:
        if sum(p.effect == Raider(medium) for p in purchases) > 1:
            raise ValueError(f"At most one {medium} raider purchase is supported")
    return Shop(tuple(purchases))


def check_pads(shop: Shop, data: MapDocument, config: FoundationConfig) -> None:
    """Reject pads that share a tile a King can stand on: XS counts each King on one pad."""
    sizes = blocking_sizes(config)
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    claimed: dict[Cell, str] = {}
    for purchase in shop.purchases:
        for cell in sorted(cells(purchase.pad_region) - blocked):
            owner = claimed.setdefault(cell, purchase.key)
            if owner != purchase.key:
                raise ValueError(f"Shop pads of {owner} and {purchase.key} share tile {cell}")


def display_captions(shop: Shop, *, overhead: bool = False) -> dict[int, str]:
    """The name each placed display unit gets, or with `overhead` the caption DE draws above
    it: every purchase it stands for, joined, an identical overhead line only once."""
    captions: dict[int, list[str]] = {}
    for purchase in shop.purchases:
        if purchase.display is not None:
            text = purchase.tag if overhead else purchase.caption
            lines = captions.setdefault(purchase.display, [])
            if not (overhead and text in lines):
                lines.append(text)
    return {display: " | ".join(texts) for display, texts in captions.items()}


def distance(region: tuple[int, int, int, int], x: float, y: float) -> float:
    x1, y1, x2, y2 = region
    dx = max(x1 - x, 0.0, x - (x2 + 1))
    dy = max(y1 - y, 0.0, y - (y2 + 1))
    return (dx * dx + dy * dy) ** 0.5


def exhibit_position(purchase: Purchase, units: Mapping[int, MapUnit]) -> tuple[float, float]:
    """Where the exhibit stands: at display_at, or else where the map placed the display."""
    if purchase.display_at is not None:
        return purchase.display_at
    unit = units.get(purchase.display if purchase.display is not None else -1)
    if unit is None:
        raise ValueError(f"Display of {purchase.key} is not a placed object")
    return unit["x"], unit["y"]


def check_displays(
    shop: Shop,
    data: MapDocument,
    config: FoundationConfig,
    *,
    reserved: Collection[Cell] = (),
    entrances: Collection[Cell] = (),
) -> None:
    """Every exhibit stands beside its own pad and off every pad: a placed one is a Gaia
    object, and a King the build places stands on land that nothing else holds; no two
    exhibits share a tile; and with the exhibits in place a King can still walk from every
    entrance to every pad."""
    units = {u["reference_id"]: u for u in data["units"]}
    sizes = blocking_sizes(config)
    signs = {
        r["stock_id"]
        for r in config["objects"]
        if (identity := r.get("map_identity")) is not None and identity["name"] == "SIGN"
    }
    blocked = {c for u in data["units"] for c in footprint(u, sizes.get(u["unit_const"], 0))}
    # Tiles other objects hold; the signs beside the pads go.
    held = {
        (math.floor(u["x"]), math.floor(u["y"]))
        for u in data["units"]
        if u["unit_const"] not in signs
    }
    pads = {cell for purchase in shop.purchases for cell in cells(purchase.pad_region)}
    width, height = data["map"]["width"], data["map"]["height"]
    land = set(config["land_terrain"])

    def terrain(cell: Cell) -> int:
        return data["map"]["tiles"][cell[1] * width + cell[0]][0]

    taken: dict[Cell, str] = {}
    for purchase in shop.purchases:
        if purchase.display is not None:
            unit = units.get(purchase.display)
            if unit is None:
                raise ValueError(f"Display of {purchase.key} is not a placed object")
            if unit["player_id"] != 0:
                raise ValueError(f"Display of {purchase.key} must belong to Gaia")
        x, y = exhibit_position(purchase, units)
        cell = (math.floor(x), math.floor(y))
        if purchase.display_at is not None:
            if not (0 <= cell[0] < width and 0 <= cell[1] < height):
                raise ValueError(f"Display of {purchase.key} stands off the map")
            if terrain(cell) not in land:
                raise ValueError(f"Display of {purchase.key} stands on the wrong terrain")
            if cell in blocked:
                raise ValueError(f"Display of {purchase.key} stands on a placed object")
            if cell in held:
                raise ValueError(f"Display of {purchase.key} stands on another object")
        if cell in pads:
            raise ValueError(f"Display of {purchase.key} stands on a pad")
        if distance(purchase.pad_region, x, y) > DISPLAY_REACH:
            raise ValueError(f"Display of {purchase.key} does not stand beside its pad")
        if cell in reserved:
            raise ValueError(f"Display of {purchase.key} stands on a creation tile")
        owner = taken.setdefault(cell, purchase.key)
        shared = purchase.display is not None and shop.get(owner).display == purchase.display
        if owner != purchase.key and not shared:
            raise ValueError(f"Displays of {owner} and {purchase.key} share tile {cell}")
    walkable = {
        (index % width, index // width)
        for index, tile in enumerate(data["map"]["tiles"])
        if tile[0] in land
    }
    reached = flood(set(entrances), walkable - blocked - set(taken))
    for purchase in shop.purchases:
        if entrances and not cells(purchase.pad_region) & reached:
            raise ValueError(f"Exhibits cut the {purchase.key} pad off from the Kings' entrances")
