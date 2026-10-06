"""Modern-only parser worker: construct a map from plain JSON and an empty seed."""

import contextlib
import json
import os
import sys
from itertools import count
from pathlib import Path
from typing import cast

from ancienttdde.common.worker import capture_stdout_for_errors
from ancienttdde.map.models import MapDocument


def construct_scenario(seed: Path, data_path: Path, destination: Path) -> None:
    from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import (
        AoE2DEScenario,
    )

    data = cast(MapDocument, json.loads(data_path.read_text(encoding="utf-8")))
    with Path(os.devnull).open("w") as quiet, contextlib.redirect_stdout(quiet):
        scenario = AoE2DEScenario.from_file(str(seed))
        if scenario.scenario_version != "1.59":
            raise ValueError("The map format seed must use scenario version 1.59")
        if scenario.unit_manager.get_all_units() or scenario.trigger_manager.triggers:
            raise ValueError("The map format seed must be empty")
        scenario.map_manager.map_size = data["map"]["width"]
        for tile, values in zip(scenario.map_manager.terrain, data["map"]["tiles"], strict=True):
            tile.terrain_id, tile.elevation, tile.layer = values
        for unit in data["units"]:
            scenario.unit_manager.add_unit(
                player=unit["player_id"],
                unit_const=unit["unit_const"],
                reference_id=unit["reference_id"],
                x=unit["x"],
                y=unit["y"],
                z=unit["z"],
                rotation=unit["rotation"],
                status=unit["status"],
                animation_frame=unit["initial_animation_frame"],
                garrisoned_in_id=unit["garrisoned_in_id"],
                caption_string=unit.get("caption_string", ""),
            )
        # Explicit preserved IDs do not advance the seed's automatic ID generator.
        next_unit_id = max((unit["reference_id"] for unit in data["units"]), default=-1) + 1
        scenario.unit_manager.reference_id_generator = (
            identifier for identifier in count(next_unit_id)
        )
        # The seed supplies stock civ settings, tech access, diplomacy and empty scripts.
        scenario.player_manager.active_players = 8
        scenario.option_manager.victory_condition = VictoryCondition.CUSTOM
        scenario.option_manager.victory_custom_conditions_required = True
        for player in scenario.player_manager.players[1:]:
            player.human = player.player_id != 8
            spawn = data.get("anchors", {}).get(f"lane.p{player.player_id}.spawn")
            if spawn is not None and "point" in spawn:
                player.initial_camera_x = int(spawn["point"][0])
                player.initial_camera_y = int(spawn["point"][1])
                player.initial_player_view_x = int(spawn["point"][0])
                player.initial_player_view_y = int(spawn["point"][1])
        scenario.sections["FileHeader"].creator_name = "Ancient TD DE; original map by DRAX"
        scenario.message_manager.instructions = (
            "Ancient TD DE map foundation\r"
            "Editor template: seven defense lanes, economy, shops and trade.\r"
            "This map has no waves, purchases or victory logic.\r"
            "Open with the standard DE data set. In-game route verification is pending."
        )
        scenario.message_manager.history = (
            "Original Ancient Tower Defense v5.3 map by DRAX6869 / DRAX."
        )
        scenario.write_to_file(str(destination))


if __name__ == "__main__":
    with capture_stdout_for_errors():
        construct_scenario(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
