"""Export reproducible, parser-independent terrain and placement data."""

import argparse
import json
from pathlib import Path
from typing import cast

from ancienttdde.generation.models import MapDocument, MapUnit, TerrainData
from ancienttdde.inspection.scenario import inspect_scenario
from ancienttdde.provenance import hash_file


def extract_map(source: Path, *, source_name: str) -> MapDocument:
    from AoE2ScenarioParser.datasets.object_support import (
        CivilizationOld,
    )

    evidence = inspect_scenario(source, include_terrain=True)
    return {
        "schema_version": 1,
        "scenario_version": evidence["scenario_version"],
        "source": {"path": source_name, "sha256": hash_file(source)},
        "map": cast(
            TerrainData, {key: evidence["map"][key] for key in ("width", "height", "tiles")}
        ),
        "players": [
            {
                "player_id": p["player_id"],
                "civilization_id": CivilizationOld[p["civilization"]].value,
            }
            for p in evidence["players"]
        ],
        "units": cast(list[MapUnit], evidence["units"]),
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
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
