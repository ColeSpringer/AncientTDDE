# Content ownership

- `maps/format-seed.aoe2scenario`: the supplied empty version-1.59 scenario,
  relocated from the Python package. It is a format seed, not the migrated map.
- `legacy/`: reviewed observations extracted from the original; these files are
  documentation data, not the future game's balance settings.
- `migration/`: explicit keep/replace/drop decisions and candidate stock IDs.
- `balance/`: future readable game definitions. Legacy observations never become
  modern defaults implicitly.
- `audit.toml`: repository-relative inputs and default generated-report location.

IDs retain their legacy civilization context. Gameplay mappings require in-game
verification before generation. Reviewed map identities and geometry are defined
in `maps/foundation.json`; native behavior and routes require in-game checks.
