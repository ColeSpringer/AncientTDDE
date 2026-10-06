"""Export reproducible, parser-independent terrain and placement data."""

import argparse
from pathlib import Path
from typing import cast

from ancienttdde.common.data import write_json
from ancienttdde.common.hashing import hash_file
from ancienttdde.map.models import MapDocument
from ancienttdde.scenario.inspect import inspect_scenario
from ancienttdde.scenario.snapshot import TerrainData


def extract_map(source: Path, *, source_name: str) -> MapDocument:
    from AoE2ScenarioParser.datasets.object_support import (
        CivilizationOld,
    )

    evidence = inspect_scenario(source, include_terrain=True)
    terrain = evidence["map"]
    if "tiles" not in terrain:
        raise ValueError(f"Inspection of {source} returned no terrain tiles")
    return {
        "schema_version": 1,
        "scenario_version": evidence["scenario_version"],
        "source": {"path": source_name, "sha256": hash_file(source)},
        "map": TerrainData(
            width=terrain["width"], height=terrain["height"], tiles=terrain["tiles"]
        ),
        "players": [
            {
                "player_id": p["player_id"],
                "civilization_id": CivilizationOld[p["civilization"]].value,
            }
            for p in evidence["players"]
        ],
        "units": evidence["units"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-name", required=True)
    arguments = parser.parse_args()
    source = cast(Path, arguments.source)
    output = cast(Path, arguments.output)
    if output.resolve() == source.resolve():
        raise ValueError("Map extraction cannot overwrite its source")
    result = extract_map(source, source_name=cast(str, arguments.source_name))
    write_json(output, result, compact=True)


if __name__ == "__main__":
    main()
