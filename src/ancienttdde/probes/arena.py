"""A 64x64 stock-DE arena for one solo mechanic experiment."""

from AoE2ScenarioParser.datasets.buildings import BuildingInfo
from AoE2ScenarioParser.datasets.support.info_dataset_base import InfoDatasetBase
from AoE2ScenarioParser.datasets.trigger_lists.action_type import ActionType
from AoE2ScenarioParser.datasets.trigger_lists.capture_flag import CaptureFlag
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.models import Rect
from ancienttdde.scenario.objects import OBJECTS, stock
from ancienttdde.scenario.triggers import Builder, TriggerHandle, effect

# Each probe player's life marker is a Barracks: a Keep alone does not keep a player in the
# game, and a counted building does. The game marks a lane's life with an Outpost instead.
PROBE_OBJECTS: dict[str, tuple[type[InfoDatasetBase], str]] = {
    **OBJECTS,
    "life": (BuildingInfo, "BARRACKS"),
    "militia": (UnitInfo, "MILITIA"),
    "knight": (UnitInfo, "KNIGHT"),
    "war-elephant": (UnitInfo, "WAR_ELEPHANT"),
    "light-cavalry": (UnitInfo, "LIGHT_CAVALRY"),
    "fire-galley": (UnitInfo, "FIRE_GALLEY"),
}

# The engine defeats a player who owns nothing but towers (including Outposts), walls,
# gates, farms, fish traps, trade units, fishing or transport ships. A defeated enemy
# satisfies conquest, so every active player must keep one of these counted objects.
SURVIVAL_OBJECTS: frozenset[str] = frozenset(
    {
        "king",
        "villager",
        "scout",
        "spearman",
        "galley",
        "trebuchet",
        "packed-trebuchet",
        "market",
        "dock",
        "town-center",
        "life",
    }
)

# Stock footprints in tiles. A building's position is the center of its footprint, so
# even sizes sit on tile corners (whole coordinates) and odd sizes on tile centers.
FOOTPRINTS: dict[str, int] = {
    "market": 4,
    "dock": 3,
    "mill": 2,
    "town-center": 4,
    "watch-tower": 1,
    "guard-tower": 1,
    "keep": 1,
    "bombard-tower": 1,
    "accursed-tower": 1,
    "blocker": 1,
    "sign": 1,
    "life": 3,
}


def survival_ids() -> frozenset[int]:
    return frozenset(stock(key, PROBE_OBJECTS) for key in SURVIVAL_OBJECTS)


def footprint_sizes() -> dict[int, int]:
    return {stock(key, PROBE_OBJECTS): size for key, size in FOOTPRINTS.items()}


def grid_offset(size: int) -> float:
    return 0.5 if size % 2 else 0.0


def center(key: str, x: int, y: int) -> tuple[float, float]:
    """Return the stored position for an object anchored at tile (x, y).

    Units and odd footprints are centered on that tile; even footprints are centered on
    the tile's corner, so the footprint covers tiles x - size / 2 through x + size / 2 - 1.
    """
    dataset, _ = PROBE_OBJECTS[key]
    if dataset is UnitInfo:
        return x + 0.5, y + 0.5
    if key not in FOOTPRINTS:
        raise ValueError(f"Unknown footprint for placed object: {key}")
    offset = grid_offset(FOOTPRINTS[key])
    return x + offset, y + offset


def tile_text(tile: tuple[int, int]) -> str:
    """Write a tile position the way probe instructions show it: (x,y)."""
    x, y = tile
    return f"({x},{y})"


class Arena(Builder):
    def __init__(self, scenario: AoE2DEScenario) -> None:
        super().__init__(scenario, PROBE_OBJECTS)
        self.scenario.map_manager.map_size = 64
        for tile in self.scenario.map_manager.terrain:
            tile.terrain_id, tile.elevation, tile.layer = 0, 0, -1

    def terrain(self, region: Rect, terrain: int) -> None:
        x1, y1, x2, y2 = region
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self.scenario.map_manager.terrain[y * 64 + x].terrain_id = terrain

    def unit(
        self,
        key: str,
        kind: str,
        player: int,
        x: int,
        y: int,
        caption: str = "",
        *,
        capture_flag: int = CaptureFlag.DEFAULT,
    ) -> int:
        position_x, position_y = center(kind, x, y)
        unit = self.scenario.unit_manager.add_unit(
            player=player,
            unit_const=self.stock(kind),
            x=position_x,
            y=position_y,
            caption_string=caption,
            capture_flag=capture_flag,
        )
        self.names.register("object", key, unit.reference_id)
        return unit.reference_id

    def trade_pair(
        self,
        start: TriggerHandle,
        key: str,
        kind: str,
        trader: str,
        home_x: int,
        partner_x: int,
        y: int,
        partner_player: int,
        partner_caption: str,
    ) -> tuple[int, int]:
        """P1's home market or dock, a partner that cannot be captured, and one trader six
        tiles from home sent to trade when the start trigger fires; the two endpoints."""
        home = self.unit(f"{key}.home", kind, 1, home_x, y, f"P1 home {kind}")
        partner = self.unit(
            f"{key}.partner",
            kind,
            partner_player,
            partner_x,
            y,
            partner_caption,
            capture_flag=CaptureFlag.NEVER,
        )
        unit = self.unit(f"{key}.trader", trader, 1, home_x + 6, y)
        effect(
            start,
            "task_object",
            source_player=1,
            selected_object_ids=[unit],
            location_object_reference=partner,
            action_type=ActionType.DEFAULT,
        )
        return home, partner

    def kings(self, key: str, player: int, count: int, x: int, y: int) -> None:
        for index in range(count):
            self.unit(f"{key}.{index}", "king", player, x + index % 6, y + index // 6)

    def objective(self, title: str, description: str) -> None:
        # Objectives are listed only while their trigger is enabled, and the entry is marked
        # complete once the trigger fires. A condition no trigger satisfies keeps the setup
        # text listed and open; the title is the short line shown on screen.
        pinned = self.scenario.trigger_manager.add_trigger(
            "Probe instructions",
            description=description,
            short_description=title,
            display_as_objective=True,
            display_on_screen=True,
        )
        self.variable("probe.instructions.complete")
        self.value(pinned, "probe.instructions.complete", 1)

    def pad(self, key: str, x: int, y: int, label: str) -> Rect:
        self.unit(key, "sign", 0, x - 1, y, label)
        region = (x, y, x + 5, y + 4)
        # A terrain contrast marks a purchase region without blocking movement.
        self.terrain(region, 4)
        return region
