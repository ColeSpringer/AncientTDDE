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
report it extracts fresh evidence for the coverage checks. `build` and `probe`
expose the planned CLI names and explain
the future milestone that implements them. The relocated
`content/maps/format-seed.aoe2scenario` is the original empty version-1.59 seed,
not the version-1.49 legacy map. The XS check uses the parser's bundled binary;
there are no gameplay XS files in milestone 1.

Stock object mappings are candidate migration choices. The registry prevents
using them for generation until verified in-game. The catalog distinguishes
scenario behavior, displayed instructions and intended modern design; it records
the Hard-income asymmetry, unbounded King removal, wall-class tower bonuses and
timed final victory explicitly. Real engine and multiplayer testing remain later
milestone requirements.
