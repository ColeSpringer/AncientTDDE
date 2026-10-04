# Stock-DE map foundation

The implementation produces a version-1.59 map template from the original 200×200
terrain and placements. It preserves all 7,395 instance IDs, positions, rotations,
elevations and garrison references. The only terrain changes are 189 water tiles
forming 21 isolated 3×3 siege positions. No original trigger logic is copied.

## Migration decisions

| Legacy placement | Stock foundation | Reason |
| --- | --- | --- |
| 5,550 Hay Stack blockers, ID 857 | Stock Blocker, ID 1776 | Explicit blockers preserve boundaries and expansion rows without relying on modded haystack behavior. |
| Custom signs, IDs 1740–1776 | Stock Sign, ID 819, with captions | Remove custom SMX art; display observed shop names and prices as text. |
| Life/display Accursed Towers, ID 684 | Outpost, ID 598 | Keep one-tile life-marker geometry without attacks or custom graphics. Final life/protection logic comes later. |
| Full Trade Carts, ID 204 | Empty Trade Carts, ID 128 | Start stock traders without relying on a preloaded cargo state. |
| Gallery units and legacy enemy-owned endpoints | Gaia ownership | Bake in neutral display/endpoint ownership without legacy initialization triggers. Stock Gaia trading is an in-game probe requirement. |
| Stock buildings, resources, relics, cliffs and other decorations | Reviewed stock identities | Retain recognizable economy and map geometry; native appearances and footprints need editor review. |
| Empty format seed | Stock settings, configurable civilizations, seven human slots and one computer slot | Do not import legacy civilization restrictions, technology disables, victory or AI behavior. |

The 129 map object definitions are scoped to the original Gaia, Huns and Persian
civilization IDs. This refers to **source interpretation**, not allowed modern
civilizations. Modern human slots retain the seed's unrestricted civilization
selection. Gameplay mappings in `content/migration/objects.json` remain unchanged.

## Named anchors and geometry checks

The 178 anchors cover each lane's spawn, exit, build areas, economy, life instance
and expansion rows; land and water trade homes, partners and initial trader
positions; all 36 distinct purchase pads; and three siege positions per lane.
The third siege position is reserved for the planned prototype comparison.

The 71 route checks cover seven lane paths, 28 trade endpoint/spawn paths and 36
shop paths. The 28 isolation checks cover seven lanes and 21 siege islets. These
checks use four-direction tile connectivity and explicit conservative footprints.
They cannot reproduce the game's sub-tile pathing, unit radii, diagonal movement,
trade targeting, damage rules or AI behavior.

Build manifests record all three map inputs and all generated artifacts by SHA-256.
Validation regenerates the expected migration, verifies sidecar contents, reloads
the scenario, compares terrain and placements, and checks a normalized content
digest. Builds require no ignored original package. Optional regression tests
compare the plain export with the immutable source when it is present.
Reload checks reject duplicate placement IDs and require the saved next-unit ID
to exceed all imported IDs, so subsequent editor and parser placements stay unique.

## In-game verification record

**Status: pending. No DE engine run has been performed in this development environment.**
The implementation and automated checks are available; the map's engine
acceptance remains open until the following checks are recorded.

Open `content/maps/stock-de-template.aoe2scenario` directly in the DE scenario
editor using the standard data set. Record the game build, tested civilization,
lane and result for each check below. The template has no purchases or waves;
use editor-placed units to exercise routes.

| Check | Expected result | Recorded result |
| --- | --- | --- |
| Open and save with stock DE | 200×200 map opens without mod, missing assets or external scripts. | Pending |
| Native blockers and expansion rows | Boundaries stop units and construction; removable row blockers retain the intended build space. | Pending |
| Every lane, including first and last | Representative infantry and cavalry can reach the exit and cannot escape the lane. | Pending |
| Every purchase pad | A King can reach each pad; captions display the corresponding legacy purchase. | Pending |
| Land trade, every endpoint pair | Stock carts can reach both markets and complete a trade trip. | Pending |
| Water trade, every endpoint pair | Stock cogs can reach both docks and complete a trade trip. | Pending |
| Economy and life displays | Stock resources, buildings and life Outposts appear correctly without overlap or unwanted attacks. | Pending |
| Every siege islet | A placed trebuchet fits, remains isolated and can target the intended tower rows; reserve position can be tested separately. | Pending |
| Editor test and save/reload | Map stays available for route inspection and retains placements after save/reload. | Pending |

Protection, passive enemy behavior, stock trade income, exact King payments and
siege targeting/expiry require focused in-game probes. The template contains no
gameplay logic.
