# Ancient TD DE

Python tooling for migrating DRAX's Ancient Tower Defense v5.3 to a self-contained
Age of Empires II: Definitive Edition scenario using stock assets.

## Development

Use Python 3.14.4 and [uv](https://docs.astral.sh/uv/). The parser is pinned to
AoE2ScenarioParser **0.9.4**; `uv.lock` locks the complete environment.

```bash
uv sync --frozen
uv run ancienttdde audit
uv run ancienttdde validate --report .build/audit
uv run ancienttdde build
uv run ancienttdde validate --build .build/map
uv run ancienttdde probe
uv run ancienttdde validate --probes .build/probes
uv run pytest
uv run pyright
uv run ruff check .
uv run ruff format --check .
uv run python tools/check_xs.py
```

The audit requires the ignored original package and DAT reference snapshots;
see [legacy provenance](legacy/README.md). A fresh clone can run synthetic tests
without these files; original-data regression tests skip when they are absent.

Reports go to `.build/audit/`: readable Markdown, complete scenario/DAT evidence,
behavior models, migration inventory and a deterministic SHA-256 manifest.
Each scenario is parsed in a separate subprocess to avoid cross-version parser
state. The audit verifies input hashes and reads the legacy inputs without
rewriting them. Repeating the audit with the same content produces the same
manifest. `--root /path/to/project` permits invocation from another directory;
`--output /path/to/reports` selects a generated-output location.

`validate` checks source provenance, trigger and civilization mapping coverage,
and scenario references. With `--report`, it also verifies artifact hashes and
rejects reports whose configuration or content inputs have changed. Without a
report it extracts fresh evidence for the coverage checks. The XS check uses the
parser's bundled binary and rejects script errors; the map foundation contains no
gameplay XS.

`probe` generates seven compact solo scenarios in `.build/probes/`, covering King
payments, tower bonus persistence, stock trade, raiders, temporary exclusive siege,
and embedded XS with a passive enemy. Use `--only payments` (repeatable) to select
experiments. The generated `instructions.md` lists 30 manual checks;
`results.json` starts without observed outcomes. Scripts and passive AI are embedded
in each scenario that needs them, so only the `.aoe2scenario` file is installed.
`validate --probes .build/probes` reloads artifacts, regenerates expected logic and
checks XS, references, hashes and result attribution. Record actual DE observations
with `probe record`; rebuilding preserves them and rejects replacing scenarios
with different content under an existing observation. See the
[mechanic probe guide](docs/mechanic-probes.md) for commands and verification limits.

`build` generates the stock-DE map from versioned plain terrain and placement data.
It needs no ignored legacy files. `build` writes
`.build/map/ancient-td-de-map.aoe2scenario`, migrated data, named anchors, structural
validation results and a hash manifest. `validate --build .build/map` checks current
input and artifact hashes, reconstructs the expected migration and reloads the
scenario in a fresh parser process. `--root` and `--output` work for builds too.

The versioned [map template](content/maps/stock-de-template.aoe2scenario) preserves
the 200×200 seven-lane layout, economy and trade areas. It replaces modded blockers,
shop signs and life indicators with stock objects and reserves three siege islets
per lane. All 7,395 placement IDs remain stable. The original empty version-1.59
`format-seed.aoe2scenario` supplies only the format and stock player settings.
See [map inputs](content/maps/README.md) and the
[map verification record](docs/map-foundation.md) for migration decisions
and the remaining in-game checks.

Gameplay object mappings remain candidates until verified in-game. Map-only
identities use reviewed names from the pinned parser datasets; these identity
checks do not approve gameplay behavior. The catalog distinguishes
scenario behavior, displayed instructions and intended modern design; it records
the Hard-income asymmetry, unbounded King removal, wall-class tower bonuses and
timed final victory explicitly. Real engine and multiplayer testing remain required
for gameplay validation.

Python changes must pass strict Pyright. Local parser interfaces in `typings/`
are checked alongside `src/`; diagnostic ignores require a demonstrated need.
