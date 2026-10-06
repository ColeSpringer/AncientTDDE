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
display/endpoint objects and provide readable captions. Point and region anchors
identify lanes, economy areas, life instances, expansion rows, purchase pads, trade
endpoints and 21 siege positions. Regions use inclusive `[x1, y1, x2, y2]` bounds.
The original Hay Stack barriers retain their visible stock identity and one-tile
footprints; they are not replaced by invisible Blockers. Terrain under them is
preserved, including the original ice along boundaries.

`stock-de-template.aoe2scenario` is the generated 1.59 template for future gameplay
generation. It contains stock placements, seven configurable human slots and a
computer slot, custom victory settings without victory logic, and English map
instructions with original-author credits. Shop captions retain **observed legacy
prices**, clearly labeled. Purchases and economy logic are not implemented.

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
uv run python -m ancienttdde.inspection.map \
  'legacy/original/resources/_common/scenario/++ Ancient TD v5.3 ++ By DRAX.aoe2scenario' \
  content/maps/legacy-map.json \
  --source-name 'legacy/original/resources/_common/scenario/++ Ancient TD v5.3 ++ By DRAX.aoe2scenario'
```

Extraction parses only the original in a child process. Construction parses only
the modern seed in another process. Reload verification uses a third process.
Opening the template, native footprints and actual routes still require the
[in-game checks](../../docs/map-foundation.md).
