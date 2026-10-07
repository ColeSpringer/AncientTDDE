# Ancient TD DE

Python tooling that migrates DRAX's Ancient Tower Defense v5.3 to a self-contained
Age of Empires II: Definitive Edition scenario built from stock assets.

## Setup

Use Python 3.14.4 and [uv](https://docs.astral.sh/uv/). `uv.lock` pins the environment,
including AoE2ScenarioParser 0.9.4.

```bash
uv sync --frozen
```

## Commands

```bash
uv run ancienttdde build                           # playable game in .build/game
uv run ancienttdde validate --build .build/game    # reload, rebuild and compare the game
uv run ancienttdde build --map-only                # logic-free map template in .build/map
uv run ancienttdde validate --build .build/map     # reload and check the template; no rebuild
uv run ancienttdde probe                           # solo mechanic scenarios in .build/probes
uv run ancienttdde validate --probes .build/probes # check probes and recorded observations
uv run ancienttdde probe record --help             # record an observation from a DE run
uv run ancienttdde audit                           # original-behavior evidence in .build/audit
uv run ancienttdde validate --report .build/audit  # check an audit against current inputs
uv run ancienttdde validate                        # check content coverage and provenance
uv run pytest                                      # tests
uv run pyright                                     # strict type checks of src, tests and tools
uv run ruff check . && uv run ruff format --check .
```

`--root` runs a command against another project directory, and `--output` writes to
another directory. Builds refuse to overwrite sources or another tool's output. Only the
generated `.aoe2scenario` file needs installing in DE.

## Editing XS

Game builds write `.build/game/runtime-prelude.xs`, the generated declarations that
`src/ancienttdde/assets/runtime.xs` uses. For VS Code's XS extension, add to the workspace
settings:

```json
"xsc.extraPreludePath": ".build/game/runtime-prelude.xs",
"files.associations": { "**/.build/**/*.xs": "plaintext" }
```

## Fresh clones

The original package and its DAT exports are not committed; see
[legacy inputs](legacy/README.md). Builds, probes and tests run without them. The audit
and `validate` without options read them, and tests that compare against the original
data skip when it is absent.

## Documentation

- [Legacy inputs](legacy/README.md): the immutable original package and its provenance.
- [Map inputs](content/maps/README.md): map data, migration decisions and the template.
- [Legacy behavior](docs/legacy-behavior.md): the original scenario and migration decisions.
- [In-game checks](docs/in-game-checks.md): hosting, and what only DE can verify.
