# Stock-DE map foundation

`format-seed.aoe2scenario` is the empty version-1.59 scenario supplied with the
repository. Its SHA-256 is recorded in `legacy/provenance.json`. Use it only to
seed the current file format.

`legacy-map.json` contains the version-1.49 map's complete plain data: 40,000 terrain
tiles, 7,395 placements, source civilization contexts and the original scenario's
SHA-256. Tile triples are `[terrain_id, elevation, layer]`, ordered by `y * width + x`.
It contains no legacy triggers, scripts, DAT attributes or custom graphics.

`foundation.json` owns map migration decisions. Each object identity names a pinned
parser dataset, stock name and ID, original civilization contexts, review status,
and conservative blocking footprint. Placement overrides neutralize the legacy
display/endpoint objects and provide readable captions. Point, points and region anchors
identify lanes, economy areas, life instances, expansion rows, purchase pads, trade
endpoints, 21 siege positions, the run controls, the enemy keeper's islet, and each lane's
transfer pads, resource bonuses and the sites where bought units and raiders appear. Regions
use inclusive `[x1, y1, x2, y2]` bounds.
The original Hay Stack barriers retain their visible stock identity and one-tile
footprints; they are not replaced by invisible Blockers. Terrain under them is
preserved, including the original ice along boundaries.

`stock-de-template.aoe2scenario` is the versioned output of `ancienttdde build --map-only`:
the migrated map that `ancienttdde build` also constructs before adding the game's
triggers and XS. It contains stock placements, seven configurable human slots and a
computer slot, custom victory settings without victory logic, and English map
instructions with original-author credits. Shop captions retain **observed legacy
prices**, clearly labeled. The template contains no purchase or economy logic.

## Migration decisions

| Legacy placement | Stock foundation | Reason |
| --- | --- | --- |
| 5,550 Hay Stack barriers, ID 857 | Stock Hay Stack, ID 857 | Retain visible barriers over the original ice terrain, with the original one-tile footprints. Invisible Blockers hid these boundaries and reserved building positions. |
| Custom signs, IDs 1740–1776 | Stock Sign, ID 819, with captions | Remove custom SMX art; display observed shop names and prices as text. |
| Life/display Accursed Towers, ID 684 | Outpost, ID 598 | Keep one-tile life-marker geometry without attacks or custom graphics. Outposts do not keep a player in the game, so each player needs a counted object. |
| Full Trade Carts, ID 204 | Empty Trade Carts, ID 128 | Start stock traders without relying on a preloaded cargo state. |
| Gallery units and legacy enemy-owned endpoints | Gaia ownership | Bake in neutral display/endpoint ownership without legacy initialization triggers. The `trade-gaia` probe tests stock Gaia trading. |
| Stock buildings, resources, relics, cliffs and other decorations | Reviewed stock identities | Retain recognizable economy and map geometry; native appearances and footprints need editor review. |
| Empty format seed | Stock settings, configurable civilizations, seven human slots and one computer slot | Do not import legacy civilization restrictions, technology disables, victory or AI behavior. |

The 129 map object definitions are scoped to the original Gaia, Huns and Persian
civilization IDs. This refers to **source interpretation**, not allowed modern
civilizations. Modern human slots retain the seed's unrestricted civilization
selection. Gameplay mappings in `content/migration/objects.json` remain unchanged.

Generate and validate from a fresh clone:

```bash
uv run ancienttdde build --map-only
uv run ancienttdde validate --build .build/map
```

Refresh the versioned template after changing map definitions:

```bash
uv run ancienttdde build --map-only
cp .build/map/ancient-td-de-map.aoe2scenario content/maps/stock-de-template.aoe2scenario
uv run pytest tests/test_map_regression.py
```

To regenerate the plain original data when the ignored source is available:

```bash
uv run python -m ancienttdde.map.extract \
  'legacy/original/resources/_common/scenario/++ Ancient TD v5.3 ++ By DRAX.aoe2scenario' \
  content/maps/legacy-map.json \
  --source-name 'legacy/original/resources/_common/scenario/++ Ancient TD v5.3 ++ By DRAX.aoe2scenario'
```

Extraction parses only the original in a child process. Construction parses only
the modern seed in another process. Reload verification uses a third process.
Opening the template, native footprints and actual routes need the
[in-game checks](../../docs/in-game-checks.md#map-template).
