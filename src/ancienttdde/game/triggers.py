"""The playable game's named variables, triggers and map placements."""

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

from ancienttdde.game.script import variable_names
from ancienttdde.scenario.triggers import Builder


class Game(Builder):
    def __init__(self, scenario: AoE2DEScenario) -> None:
        super().__init__(scenario)
        for index, name in enumerate(variable_names()):
            self.variable(name, variable_id=index)
        self.placements = {unit.reference_id for unit in scenario.unit_manager.get_all_units()}
        self.gaia_positions: dict[str, dict[int, tuple[float, float]]] = {}

    def gaia(self, kind: str) -> dict[int, tuple[float, float]]:
        """The Gaia objects of a stock kind by instance ID, with their positions."""
        if kind not in self.gaia_positions:
            wanted = self.stock(kind)
            self.gaia_positions[kind] = {
                unit.reference_id: (unit.x, unit.y)
                for unit in self.scenario.unit_manager.units[0]
                if unit.unit_const == wanted
            }
        return self.gaia_positions[kind]

    def forget_gaia(self, kind: str) -> None:
        """Drop the cached Gaia objects of a kind after adding or removing some."""
        self.gaia_positions.pop(kind, None)

    def placement(self, reference_id: int) -> int:
        """Return the ID of an instance the map placed, rejecting any other ID."""
        if reference_id not in self.placements:
            raise ValueError(f"Missing map placement: {reference_id}")
        return reference_id
