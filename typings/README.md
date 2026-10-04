# Parser typing boundary

These partial stubs describe the AoE2ScenarioParser **0.9.4** entry points used by
this project. The distribution lacks a `py.typed` marker. Protocols describe the
specific managers and section fields used here, checked against the installed
source. The stubs do not declare arbitrary members or return `Any`.

`AoE2DEScenario` signatures were checked against the pinned implementation;
scenario construction and reload integration tests exercise them at runtime.
`CivilizationOld` and `TerrainId` are exported as their actual integer enums.
Object datasets expose the verified `InfoDatasetBase` properties and ID lookup.
Named map identities are checked
against the installed dataset and pinned parser version during every build.

Review these interfaces when changing the parser pin. Pyright reads them through
`stubPath` in `pyproject.toml`, and checks `typings/` in strict mode alongside `src/`.
