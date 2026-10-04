from collections.abc import Generator
from typing import Protocol, Self, TypedDict

class _TerrainTile(Protocol):
    terrain_id: int
    elevation: int
    layer: int

class _MapManager(Protocol):
    map_size: int
    terrain: list[_TerrainTile]
    @property
    def map_width(self) -> int: ...
    @property
    def map_height(self) -> int: ...

class _Unit(Protocol):
    reference_id: int
    unit_const: int
    x: float
    y: float
    z: float
    rotation: float
    garrisoned_in_id: int

class _UnitManager(Protocol):
    units: list[list[_Unit]]
    reference_id_generator: Generator[int]
    def get_all_units(self) -> list[_Unit]: ...
    def add_unit(
        self,
        player: int,
        unit_const: int,
        x: float = 0,
        y: float = 0,
        z: float = 0,
        rotation: float = 0,
        garrisoned_in_id: int = -1,
        animation_frame: int = 0,
        status: int = 2,
        reference_id: int | None = None,
        capture_flag: int = -1,
        caption_string_id: int = -1,
        caption_string: str = "",
    ) -> _Unit: ...

class _Trigger(Protocol):
    trigger_id: int
    condition_order: list[int]
    effect_order: list[int]
    conditions: list[object]
    effects: list[object]

class _Variable(Protocol):
    variable_id: int
    name: str

class _TriggerManager(Protocol):
    triggers: list[_Trigger]
    variables: list[_Variable]
    trigger_display_order: list[int]

class _Player(Protocol):
    _object_attributes: list[str]
    _object_attributes_non_gaia: list[str]
    player_id: int
    human: bool
    initial_camera_x: int | None
    initial_camera_y: int | None
    initial_player_view_x: int | None
    initial_player_view_y: int | None
    @property
    def active(self) -> bool: ...

class _PlayerManager(Protocol):
    active_players: int
    players: list[_Player]

class _MessageManager(Protocol):
    instructions: str
    history: str

class _XsManager(Protocol):
    script_name: str

class _OptionManager(Protocol):
    victory_condition: int
    victory_custom_conditions_required: bool

class _FileHeader(Protocol):
    creator_name: str

class _DataHeader(Protocol):
    next_unit_id_to_place: int

class _Files(Protocol):
    script_file_content: str
    ai_files: list[object]

class _Cinematics(Protocol):
    ascii_pregame: str
    ascii_victory: str
    ascii_loss: str

class _BackgroundImage(Protocol):
    ascii_filename: str

class _Sections(TypedDict):
    FileHeader: _FileHeader
    DataHeader: _DataHeader
    Files: _Files
    Cinematics: _Cinematics
    BackgroundImage: _BackgroundImage

class AoE2DEScenario:
    sections: _Sections
    @property
    def scenario_version(self) -> str: ...
    @classmethod
    def from_default(cls, scenario_version: str | tuple[int, int] | None = None) -> Self: ...
    @classmethod
    def from_file(cls, path: str, game_version: str = "DE", name: str = "") -> Self: ...
    def write_to_file(self, filename: str) -> None: ...
    @property
    def trigger_manager(self) -> _TriggerManager: ...
    @property
    def unit_manager(self) -> _UnitManager: ...
    @property
    def map_manager(self) -> _MapManager: ...
    @property
    def xs_manager(self) -> _XsManager: ...
    @property
    def player_manager(self) -> _PlayerManager: ...
    @property
    def message_manager(self) -> _MessageManager: ...
    @property
    def option_manager(self) -> _OptionManager: ...
