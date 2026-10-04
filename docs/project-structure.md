# Repository organization

| Location | Ownership |
| --- | --- |
| `legacy/original.zip`, `legacy/original/` | Immutable, ignored original package |
| `legacy/reference/dat/` | Ignored supplied reference snapshot, retained unchanged |
| `legacy/reference/dat-verified/` | Ignored regenerated and validated C++ genieutils export |
| `legacy/provenance.json` | Versioned hashes, source relationships and original credits |
| `content/maps/` | Format seed, plain original map, reviewed map definitions and stock-DE template |
| `content/legacy/` | Reviewed legacy observations and trigger classification |
| `content/migration/` | Explicit mechanic and object migration decisions |
| `content/balance/` | Future modern balance definitions |
| `src/ancienttdde/inspection/` | Isolated scenario extraction and DAT dependency inspection |
| `src/ancienttdde/models.py`, `registry.py` | Shared vocabulary and named reference resolution |
| `src/ancienttdde/audit.py`, `reports.py` | Audit orchestration and readable evidence reports |
| `src/ancienttdde/validation.py`, `cli.py` | Validation boundary and development commands |
| `src/ancienttdde/generation/` | Typed map migration, geometry checks, isolated construction and build validation |
| `src/ancienttdde/xs/` | Future embedded gameplay XS |
| `typings/` | Strictly checked interfaces for the pinned parser |
| `tests/` | Synthetic fixtures, behavior regressions and optional original-data checks |
| `tools/dat/` | Maintained C++/GDB legacy DAT export utilities |
| `tools/check_xs.py` | Repeatable validation using the parser's bundled xs-check |
| `docs/` | Reviewed catalog, migration decisions and future playtest records |
| `.build/`, `build/`, `output/`, `dist/` | Ignored reports, generated scenarios and packages |

The inspection subprocess parses one version per process. It never constructs a
new scenario in the same process as the legacy parser. Content and provenance
paths are relative to the project root, and generated outputs cannot overwrite
the source directories. Scenario object IDs, placed-instance IDs, technology IDs,
trigger IDs and variable IDs are separate reference namespaces.

Gameplay migration stock IDs are candidates until checked in-game. The central
registry requires verified mappings for gameplay and scopes legacy IDs by
civilization. Map construction uses a separate reviewed identity check against
the pinned stock datasets; structural checks do not establish engine behavior.
DAT variant comparisons do not establish which fields differ from stock: a
version-matched stock DAT is not present in the supplied material.
