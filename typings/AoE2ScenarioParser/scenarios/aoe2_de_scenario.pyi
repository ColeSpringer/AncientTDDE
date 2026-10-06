from collections.abc import Generator
from pathlib import Path
from typing import Protocol, Self, TypedDict

from AoE2ScenarioParser.datasets.object_support import Civilization

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
    def get_tile(
        self, x: int | None = None, y: int | None = None, i: int | None = None
    ) -> _TerrainTile: ...

class _Unit(Protocol):
    reference_id: int
    unit_const: int
    x: float
    y: float
    z: float
    rotation: float
    garrisoned_in_id: int
    capture_flag: int
    caption_string: str

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

class _Effect(Protocol):
    effect_type: int
    source_player: int
    selected_object_ids: list[int]
    max_units_affected: int

class _ComponentFactory(Protocol):
    def __call__(self, **attributes: object) -> object: ...

class _NewComponents:
    """The parser's new_effect/new_condition helpers: one factory per component name."""

    def __getattr__(self, name: str) -> _ComponentFactory: ...

class _Trigger(Protocol):
    name: str
    new_effect: _NewComponents
    new_condition: _NewComponents
    trigger_id: int
    condition_order: list[int]
    effect_order: list[int]
    conditions: list[object]
    effects: list[_Effect]

class _Variable(Protocol):
    variable_id: int
    name: str

class _TriggerManager(Protocol):
    triggers: list[_Trigger]
    variables: list[_Variable]
    trigger_display_order: list[int]
    def add_trigger(
        self,
        name: str,
        description: str | None = None,
        display_as_objective: bool | None = None,
        short_description: str | None = None,
        display_on_screen: bool | None = None,
        enabled: bool | None = None,
        looping: bool | None = None,
        execute_on_load: bool | None = None,
    ) -> _Trigger: ...
    def add_variable(self, name: str, variable_id: int = -1) -> _Variable: ...

class _Player(Protocol):
    _object_attributes: list[str]
    _object_attributes_non_gaia: list[str]
    player_id: int
    human: bool
    @property
    def civilization(self) -> Civilization: ...
    @civilization.setter
    def civilization(self, value: Civilization | str | int) -> None: ...
    lock_civ: bool
    lock_personality: bool
    starting_age: int
    population_cap: int | None
    allied_victory: bool | None
    diplomacy: list[int] | None
    food: int
    wood: int
    gold: int
    stone: int
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
    hints: str
    history: str

class _XsManager(Protocol):
    script_name: str
    xs_check: _XsCheck
    def add_script(
        self,
        xs_file_path: str = "",
        xs_string: str = "",
        validate: bool = False,
    ) -> None: ...
    def validate_scenario_xs(self) -> None: ...

class _XsCheck(Protocol):
    path: Path | None
    enabled: bool
    raise_on_error: bool
    @property
    def is_disabled(self) -> bool: ...
    def validate(self, xs_file: Path | str | None, show_tmpfile: bool = True) -> bool | None: ...

class _EmbeddedAi(Protocol):
    ai_per_file_text: str

class _PlayerDataTwo(Protocol):
    ai_names: list[str]
    ai_files: list[_EmbeddedAi]
    ai_type: list[int]

class _OptionManager(Protocol):
    victory_condition: int
    victory_custom_conditions_required: bool
    lock_teams: bool
    allow_players_choose_teams: bool
    random_start_points: bool
    secondary_game_modes: int | bytes | None
    legacy_execution_order: bool | None

class _Options(Protocol):
    all_techs: int

class _GlobalVictory(Protocol):
    conquest_required: int
    ruins: int
    artifacts_required: int
    discovery: int
    explored_percent_of_map_required: int
    gold_required: int

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

class _EffectRecord(Protocol):
    """Stored effect fields; reading a field the scenario version lacks raises KeyError."""

    effect_type: int
    quantity: int
    quantity_float: float
    object_attributes: int
    object_list_unit_id: int
    source_player: int

class _TriggerRecord(Protocol):
    effect_data: list[_EffectRecord]

class _Triggers(Protocol):
    trigger_data: list[_TriggerRecord]

class _Sections(TypedDict):
    FileHeader: _FileHeader
    DataHeader: _DataHeader
    Files: _Files
    Cinematics: _Cinematics
    BackgroundImage: _BackgroundImage
    PlayerDataTwo: _PlayerDataTwo
    Options: _Options
    GlobalVictory: _GlobalVictory
    Triggers: _Triggers

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
