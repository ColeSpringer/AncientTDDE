"""The balance model: what towers deal, what waves demand, what Kings buy and what each
civilization profile is worth, from the content and the stock data snapshot.

Everything here is arithmetic over the definitions; the in-game checks and probes measure what
the model assumes. Values are expressed in Kings where they can be compared.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ancienttdde.common.data import object_value, read_object
from ancienttdde.game.catalog import (
    Castle,
    Investment,
    Population,
    Purchase,
    Relics,
    ResourceGrant,
    Shop,
    SiegePowerUp,
    TowerAttack,
    Traders,
    load_shop,
)
from ancienttdde.game.civilizations import (
    DEFAULT_NAME,
    Civilization,
    NativeWorth,
    Profile,
    Profiles,
    load_profiles,
)
from ancienttdde.game.config import Balance, EngineLane, load_balance, load_lanes
from ancienttdde.game.sites import anchor, numbers
from ancienttdde.game.stock import (
    BUILDING_CLASS,
    MELEE_CLASS,
    PIERCE_CLASS,
    Stock,
    StockUnit,
    load_stock,
)
from ancienttdde.game.waves import ENEMY_SPEED
from ancienttdde.map.models import MapAnchor

# Caravan, a starting technology, speeds traders up by this factor (DE data).
CARAVAN_SPEED = 1.2
# Food has no shop price; technology costs value it at this many per King.
FOOD_PER_KING = 3000
# A tile of tower range covers more of the lane; its worth in Kings when a profile adds it.
RANGE_KINGS = 0.25
# The population a bought castle supports, and the building's own worth in Kings.
CASTLE_POPULATION = 20
CASTLE_KINGS = 1.0
# The family the attack ladder and tower technologies raise: every stock tower.
TOWER_FAMILY = "towers"


@dataclass(frozen=True)
class Assumptions:
    """Numbers the data files cannot give. The trade probe measures the first."""

    # Gold a trader brings home per trip on the map's full-length routes.
    trade_gold_per_trip: int = 100
    starting_carts: int = 8
    starting_cogs: int = 4
    # Villagers a lane keeps on gold and on stone, and what each gathers in a minute.
    gold_villagers: int = 4
    stone_villagers: int = 4
    villager_gold_per_minute: int = 22
    villager_stone_per_minute: int = 20
    # Towers a lane builds over a run, for pricing a stone discount.
    towers_per_run: int = 24
    # PvP-only worth: a tower hit point against siege, a raider slot, and a point of population.
    tower_hit_point_kings: float = 0.0005
    raider_slot_kings: float = 0.5
    population_kings: float = 0.03


@dataclass(frozen=True)
class Inputs:
    balance: Balance
    shop: Shop
    profiles: Profiles
    stock: Stock
    lanes: tuple[EngineLane, ...]
    # Tiles between a lane's home and partner market, and dock.
    land_route: float
    water_route: float

    @property
    def level(self) -> int:
        """The difficulty level the model prices: the one every competitive game plays."""
        return self.balance.difficulty.competitive

    @property
    def minutes(self) -> float:
        return self.balance.scheduled_seconds / 60

    @property
    def lane_tiles(self) -> int:
        return self.lanes[0].exit_x - self.lanes[0].spawn_x


def route_tiles(anchors: dict[str, object], medium: str) -> float:
    (x1, y1), (x2, y2) = (
        numbers(anchor(anchors, f"trade.{medium}.p1.{end}").get("point"), end, 2)
        for end in ("home", "partner")
    )
    return math.hypot(x2 - x1, y2 - y1)


def load_inputs(root: Path) -> Inputs:
    balance = load_balance(root / "content/balance/game.json")
    anchors = object_value(
        read_object(root / "content/maps/foundation.json").get("anchors"), "anchors"
    )
    families = [name for name, _ in balance.towers.families]
    shop = load_shop(
        root / "content/balance/shop.json", cast(dict[str, MapAnchor], anchors), families
    )
    stock = load_stock(root / "content/balance/stock.json")
    return Inputs(
        balance=balance,
        shop=shop,
        profiles=load_profiles(root / "content/balance/civilizations.json", balance, shop, stock),
        stock=stock,
        lanes=load_lanes(anchors),
        land_route=route_tiles(anchors, "land"),
        water_route=route_tiles(anchors, "water"),
    )


def damage_per_hit(attack: float, armor: float) -> float:
    """DE's rule: attack less armor in the class, never below one."""
    return max(1.0, attack - armor)


def tower_dps(unit: StockUnit, bonus: float, pierce_armor: float) -> float:
    return damage_per_hit(unit.attack(PIERCE_CLASS) + bonus, pierce_armor) / unit.reload


@dataclass(frozen=True)
class LadderStep:
    """A tower attack purchase with the attack and Kings accumulated up to it."""

    purchase: Purchase
    attack: int
    kings: int


def attack_ladder(shop: Shop) -> tuple[LadderStep, ...]:
    """The repeatable tower attack purchases on the whole family, in catalog order."""
    steps: list[LadderStep] = []
    attack = kings = 0
    for purchase in shop.purchases:
        effect = purchase.effect
        if isinstance(effect, TowerAttack) and effect.family == TOWER_FAMILY:
            attack += effect.amount
            kings += purchase.kings
            steps.append(LadderStep(purchase, attack, kings))
    return tuple(steps)


@dataclass(frozen=True)
class Rates:
    """What a King buys, from the shop's resource grants and the attack ladder."""

    stone_per_king: float
    wood_per_king: float
    gold_per_king: float
    food_per_king: float
    kings_per_attack: float

    def kings(
        self, *, food: float = 0, wood: float = 0, stone: float = 0, gold: float = 0
    ) -> float:
        return (
            food / self.food_per_king
            + wood / self.wood_per_king
            + stone / self.stone_per_king
            + gold / self.gold_per_king
        )


def rates(inputs: Inputs) -> Rates:
    """The shop's yardsticks: one stone grant, one wood grant and the attack ladder."""
    grants: dict[str, float] = {}
    for purchase in inputs.shop.purchases:
        effect = purchase.effect
        if isinstance(effect, ResourceGrant):
            if effect.resource in grants:
                raise ValueError(
                    f"The tables need one {effect.resource} grant in the shop, not two"
                )
            grants[effect.resource] = effect.amount / purchase.kings
    for resource in ("stone", "wood"):
        if resource not in grants:
            raise ValueError(f"The tables need a {resource} grant in the shop")
    ladder = attack_ladder(inputs.shop)
    if not ladder:
        raise ValueError("The tables need the tower attack ladder in the shop")
    return Rates(
        stone_per_king=grants["stone"],
        wood_per_king=grants["wood"],
        gold_per_king=inputs.balance.difficulty.levels[inputs.level].king_gold,
        food_per_king=FOOD_PER_KING,
        kings_per_attack=ladder[-1].kings / ladder[-1].attack,
    )


@dataclass(frozen=True)
class WaveNeed:
    key: str
    unit: str
    enemies: int
    hit_points: int
    pierce_armor: float
    total_hit_points: int
    spawn_seconds: int
    crossing_seconds: float
    required_dps: float


def wave_needs(inputs: Inputs) -> tuple[WaveNeed, ...]:
    """What a lane must deal to stop every enemy of a wave before the exit, as a lower bound:
    the wave's hit points over the time its last enemy takes to spawn and cross the lane."""
    crossing = inputs.lane_tiles / ENEMY_SPEED
    needs: list[WaveNeed] = []
    for index, wave in enumerate(inputs.balance.waves):
        hit_points = inputs.balance.hit_points(index, inputs.level)
        enemies = wave.count * wave.batches
        spawn = (wave.batches - 1) * wave.interval
        needs.append(
            WaveNeed(
                key=wave.key,
                unit=wave.unit,
                enemies=enemies,
                hit_points=hit_points,
                pierce_armor=inputs.stock.unit(wave.unit).armor(PIERCE_CLASS),
                total_hit_points=enemies * hit_points,
                spawn_seconds=spawn,
                crossing_seconds=crossing,
                required_dps=enemies * hit_points / (spawn + crossing),
            )
        )
    return tuple(needs)


def trader_gold_per_minute(inputs: Inputs, assumptions: Assumptions, medium: str) -> float:
    """What one trader brings home per minute on its full-length route."""
    if medium == "land":
        unit, route = inputs.stock.unit("TRADE_CART_EMPTY"), inputs.land_route
    else:
        unit, route = inputs.stock.unit("TRADE_COG"), inputs.water_route
    trip = 2 * route / (unit.speed * CARAVAN_SPEED)
    return 60 * assumptions.trade_gold_per_trip / trip


@dataclass(frozen=True)
class Income:
    """Kings a lane earns over the scheduled run without buying anything."""

    minutes: float
    wave_kings: int
    kills: int
    rewards: int
    kill_kings: int
    kill_stone: int
    kill_wood: int
    trade_gold_per_minute: float
    relic_gold_per_minute: float
    mining_gold_per_minute: float
    mining_stone_per_minute: float
    gold_kings: float

    @property
    def gold_per_minute(self) -> float:
        return self.trade_gold_per_minute + self.relic_gold_per_minute + self.mining_gold_per_minute

    @property
    def total_kings(self) -> float:
        return self.wave_kings + self.kill_kings + self.gold_kings


def baseline_income(inputs: Inputs, assumptions: Assumptions) -> Income:
    balance = inputs.balance
    economy = balance.economy
    kills = sum(w.count * w.batches for w in balance.waves)
    rewards = kills // economy.kills_per_reward
    trade = assumptions.starting_carts * trader_gold_per_minute(
        inputs, assumptions, "land"
    ) + assumptions.starting_cogs * trader_gold_per_minute(inputs, assumptions, "water")
    relics = economy.starting_relics * inputs.stock.relic_gold_per_minute
    mining = assumptions.gold_villagers * assumptions.villager_gold_per_minute
    minutes = inputs.minutes
    gold_per_minute = trade + relics + mining
    return Income(
        minutes=minutes,
        wave_kings=len(balance.waves) * economy.wave_kings,
        kills=kills,
        rewards=rewards,
        kill_kings=rewards // economy.rewards_per_king,
        kill_stone=rewards * economy.kill_stone,
        kill_wood=rewards * economy.kill_wood,
        trade_gold_per_minute=trade,
        relic_gold_per_minute=relics,
        mining_gold_per_minute=mining,
        mining_stone_per_minute=assumptions.stone_villagers * assumptions.villager_stone_per_minute,
        gold_kings=gold_per_minute * minutes / rates(inputs).gold_per_king,
    )


@dataclass(frozen=True)
class InvestmentReturn:
    key: str
    name: str
    kings: int
    pays: str
    amount: int
    period: int
    kings_per_minute: float
    payback_minutes: float
    run_minutes: float

    @property
    def run_value(self) -> float:
        """Kings it pays when bought at the start of the run."""
        return self.kings_per_minute * self.run_minutes

    @property
    def half_run_value(self) -> float:
        return self.kings_per_minute * self.run_minutes / 2


def payout_kings(effect: Investment, exchange: Rates) -> float:
    match effect.pays:
        case "gold":
            return effect.amount / exchange.gold_per_king
        case "stone":
            return effect.amount / exchange.stone_per_king
        case "king":
            return float(effect.amount)
        case "attack":
            return effect.amount * exchange.kings_per_attack


def investment_returns(inputs: Inputs) -> tuple[InvestmentReturn, ...]:
    exchange = rates(inputs)
    returns: list[InvestmentReturn] = []
    for purchase in inputs.shop.investments():
        effect = purchase.effect
        if not isinstance(effect, Investment):
            continue
        per_minute = payout_kings(effect, exchange) * 60 / effect.period
        returns.append(
            InvestmentReturn(
                key=purchase.key,
                name=purchase.name,
                kings=purchase.kings,
                pays=effect.pays,
                amount=effect.amount,
                period=effect.period,
                kings_per_minute=per_minute,
                payback_minutes=purchase.kings / per_minute,
                run_minutes=inputs.minutes,
            )
        )
    return tuple(returns)


@dataclass(frozen=True)
class ProfileValue:
    """A profile's worth in Kings: in a solo run, and with PvP on (its solo worth included)."""

    solo: float
    pvp: float


def attack_kings(family: str, amount: int, inputs: Inputs, exchange: Rates) -> float:
    """A flat attack bonus, held from the first wave, is worth what the shop charges for it on
    the smallest rung of the family's ladder; a family without a ladder is priced at the
    towers' average by its share of the tower definitions."""
    rungs: list[tuple[int, int]] = []
    for purchase in inputs.shop.purchases:
        effect = purchase.effect
        if isinstance(effect, TowerAttack) and effect.family == family:
            rungs.append((effect.amount, purchase.kings))
    if rungs:
        rung_attack, rung_kings = min(rungs)
        return amount * rung_kings / rung_attack
    towers = inputs.balance.towers
    return amount * exchange.kings_per_attack * len(towers.family_ids(family)) / len(towers.members)


def technology_kings(name: str, inputs: Inputs, exchange: Rates) -> float:
    """A free technology saves its cost and, for tower technologies, adds attack and range."""
    found = inputs.stock.technologies.get(name)
    if found is None:
        raise ValueError(f"{name} is not in the stock snapshot, so its worth is unknown")
    saved = exchange.kings(**{resource: amount for resource, amount in found.cost.items()})
    towers = found.towers
    return (
        saved
        + attack_kings(TOWER_FAMILY, towers.attack, inputs, exchange)
        + towers.range * RANGE_KINGS
    )


def trader_kings(
    medium: str, count: int, inputs: Inputs, assumptions: Assumptions, exchange: Rates
) -> float:
    """What this many traders bring home over the run, in Kings."""
    gold = count * trader_gold_per_minute(inputs, assumptions, medium) * inputs.minutes
    return exchange.kings(gold=gold)


def relic_kings(count: int, inputs: Inputs, exchange: Rates) -> float:
    return exchange.kings(gold=count * inputs.stock.relic_gold_per_minute * inputs.minutes)


def purchase_kings(key: str, inputs: Inputs, assumptions: Assumptions, exchange: Rates) -> float:
    """What a purchase held from the start is worth: its price, what an investment pays over
    the run, what its traders or relics bring in, or a castle's population and building."""
    purchase = inputs.shop.get(key)
    effect = purchase.effect
    sites = inputs.lanes[0].sites
    if isinstance(effect, Investment):
        return next(r.run_value for r in investment_returns(inputs) if r.key == key)
    if isinstance(effect, Traders):
        spots = sites.carts if effect.medium == "land" else sites.cogs
        return trader_kings(effect.medium, len(spots), inputs, assumptions, exchange)
    if isinstance(effect, Relics):
        return relic_kings(len(sites.relics), inputs, exchange)
    if isinstance(effect, Castle):
        return CASTLE_KINGS + CASTLE_POPULATION * assumptions.population_kings
    if isinstance(effect, Population):
        return effect.amount * assumptions.population_kings
    return float(purchase.kings)


def profile_value(profile: Profile, inputs: Inputs, assumptions: Assumptions) -> ProfileValue:
    exchange = rates(inputs)
    income = baseline_income(inputs, assumptions)
    solo = float(profile.kings)
    solo += exchange.kings(
        food=profile.resources.food,
        wood=profile.resources.wood,
        stone=profile.resources.stone,
        gold=profile.resources.gold,
    )
    # The same gold makes this many more Kings at the discounted price.
    solo += income.gold_kings * (100 / profile.king_gold_percent - 1)
    solo += (
        (profile.kill_reward_percent - 100)
        / 100
        * exchange.kings(stone=income.kill_stone, wood=income.kill_wood)
    )
    for family, amount in profile.attack:
        solo += attack_kings(family, amount, inputs, exchange)
    solo += exchange.kings(stone=profile.tower_stone * assumptions.towers_per_run)
    solo += relic_kings(profile.relics, inputs, exchange)
    for medium, count in profile.traders:
        solo += trader_kings(medium, count, inputs, assumptions, exchange)
    for name in profile.technologies:
        solo += technology_kings(name, inputs, exchange)
    solo += profile.population * assumptions.population_kings
    for key in profile.purchases:
        solo += purchase_kings(key, inputs, assumptions, exchange)
    pvp = solo + profile.tower_hit_points * assumptions.tower_hit_point_kings
    pvp += sum(extra for _, extra in profile.raiders) * assumptions.raider_slot_kings
    return ProfileValue(solo=solo, pvp=pvp)


@dataclass(frozen=True)
class Rivalry:
    """What raids and sieges cost and do with this many players in the game."""

    players: int
    land_raider: str
    naval_raider: str
    siege_price: int
    trebuchets: int
    siege_damage_per_rival: float
    watch_towers_per_rival: float
    keeps_per_rival: float
    rebuild_kings_per_rival: float
    cart_seconds: float
    cog_seconds: float
    trader_replacement_kings: float


def damage_per_hit_on(trebuchet: StockUnit, tower: StockUnit) -> float:
    return damage_per_hit(
        trebuchet.attack(PIERCE_CLASS), tower.armor(PIERCE_CLASS)
    ) + damage_per_hit(trebuchet.attack(BUILDING_CLASS), tower.armor(BUILDING_CLASS))


def kill_seconds(attacker: StockUnit, victim: StockUnit) -> float:
    per_hit = damage_per_hit(attacker.attack(MELEE_CLASS), victim.armor(MELEE_CLASS))
    return victim.hit_points / (per_hit / attacker.reload)


def rivalry(inputs: Inputs) -> tuple[Rivalry, ...]:
    shop, stock = inputs.shop, inputs.stock
    siege, raiders = inputs.balance.interaction.siege, inputs.balance.interaction.raiders
    purchase = shop.first(SiegePowerUp)
    carts = next((p for p in shop.purchases if p.effect == Traders("land")), None)
    if purchase is None or not isinstance(purchase.effect, SiegePowerUp):
        raise ValueError("The rivalry tables need a siege purchase in the shop")
    if carts is None:
        raise ValueError("The rivalry tables need a trade cart purchase in the shop")
    per_rival = purchase.effect.kings_per_rival
    cart_spots = len(inputs.lanes[0].sites.carts)
    trebuchet, keep, watch = stock.unit("TREBUCHET"), stock.unit("KEEP"), stock.unit("WATCH_TOWER")
    land, naval = raiders.kind("land").unit, raiders.kind("naval").unit
    shots = siege.active_seconds // int(trebuchet.reload)
    exchange = rates(inputs)
    rows: list[Rivalry] = []
    for players in range(2, 8):
        rivals = players - 1
        keep_damage = siege.trebuchets_per_rival * shots * damage_per_hit_on(trebuchet, keep)
        watch_damage = siege.trebuchets_per_rival * shots * damage_per_hit_on(trebuchet, watch)
        watch_towers = watch_damage / watch.hit_points
        rows.append(
            Rivalry(
                players=players,
                land_raider=land,
                naval_raider=naval,
                siege_price=purchase.kings + per_rival * rivals,
                trebuchets=siege.trebuchets_per_rival * rivals,
                siege_damage_per_rival=keep_damage,
                watch_towers_per_rival=watch_towers,
                keeps_per_rival=keep_damage / keep.hit_points,
                rebuild_kings_per_rival=watch_towers
                * exchange.kings(**{r: float(a) for r, a in watch.cost.items()}),
                cart_seconds=kill_seconds(stock.unit(land), stock.unit("TRADE_CART_EMPTY")),
                cog_seconds=kill_seconds(stock.unit(naval), stock.unit("TRADE_COG")),
                trader_replacement_kings=carts.kings / cart_spots,
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class CivilizationValue:
    """A civilization's worth in Kings: its profile, the content's estimate of its own
    bonuses, and the two together."""

    profile: ProfileValue
    native: NativeWorth

    @property
    def solo(self) -> float:
        return self.profile.solo + self.native.solo

    @property
    def pvp(self) -> float:
        return self.profile.pvp + self.native.solo + self.native.pvp


def civilization_value(
    civilization: Civilization, inputs: Inputs, assumptions: Assumptions
) -> CivilizationValue:
    return CivilizationValue(
        profile_value(civilization.profile, inputs, assumptions), civilization.native
    )


def profile_table(inputs: Inputs, assumptions: Assumptions) -> Mapping[str, CivilizationValue]:
    """Every civilization's worth by name, the default last."""
    values = {
        civilization.name: civilization_value(civilization, inputs, assumptions)
        for civilization in inputs.profiles.civilizations
    }
    values[DEFAULT_NAME] = CivilizationValue(
        profile_value(inputs.profiles.default, inputs, assumptions), NativeWorth()
    )
    return values
