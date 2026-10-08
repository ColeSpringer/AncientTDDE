from os import PathLike
from pathlib import Path

from genieutils.civ import Civ
from genieutils.effect import Effect
from genieutils.tech import Tech

class DatFile:
    version: str
    effects: list[Effect]
    civs: list[Civ]
    techs: list[Tech]
    @classmethod
    def parse(cls, input_file: Path | PathLike[str] | str) -> DatFile: ...
