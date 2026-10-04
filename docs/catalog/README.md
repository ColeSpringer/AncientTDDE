# Reviewed Ancient TD v5.3 behavior catalog

This catalog records original behavior and reviewed migration decisions. Modern
balance definitions are maintained separately. The original scenario is version
**1.49**, **200 × 200**, with **1,018
triggers**, **7,395 placed objects**, seven human lanes and enemy player 8.
The package credits DRAX6869 / DRAX. The empty modern version-1.59 file is only a
format seed and lives in `content/maps/format-seed.aoe2scenario`.

Evidence uses zero-based trigger storage IDs from the original. Inspect a
specific condition or effect in the audit's `scenario.json`, or its readable
`triggers.md`. Display order and component order are retained independently.
`legacy/provenance.json` identifies the exact source bytes. Generated reports
are ignored, while the reviewed catalog and migration decisions are versioned.

## Schedule and enemy behavior

The complete composition and timing are in [waves.md](waves.md) and
`content/legacy/waves.json`. There are **46 regular subwaves**: levels 1–9 have
five phases A–E, followed by level 10-A; then **ten boss waves**.
Each regular spawn targets every lane simultaneously. Levels 1–6 create two
units per lane per pulse; levels 7–10 create three. Most pulses repeat every
three game-seconds, while 1-E repeats every five. The first wave activates at
650 game-seconds. Earlier regular phases spawn for 45 seconds, followed by a
delay; level 9 and 10-A run for 75 seconds. The static timer chain reaches Boss 10
at 6,365 seconds and the timed WIN trigger at **6,435 seconds (107.25 minutes)**.
Engine ticks and activation ordering may affect exact runtime boundaries.

Composition and timing do not depend on selected difficulty. Difficulty changes
gold-to-King conversion. Enemy player 8 uses the **Persians** DAT table and is
renamed DRAXARMY; seven humans initially select Huns but may change civilization.
Gaia must use **DAT table 0** even though its scenario civilization selector
contains Saracens. Wave units are tasked through lane exits by trigger 659.
HP loops 648–658 and 997 operate on the spawn strip; several use negative damage
to increase current health, rather than explicit immutable wave definitions.
Destroyed map markers enable enemy Husbandry (817) and Squires (861).

Each boss creates one repurposed unit per lane (IDs 1777–1786). Negative damage
adds roughly 6–15 million health to their base 55 HP. The boss chain does not wait
for the prior boss to die. Boss damage triggers 1011–1017 are one-shot area checks
and damage life buildings by 25,000, then remove units in the exit region.
Boss 1 starts after 60 seconds; subsequent bosses generally use 60-second gaps,
with 75 seconds before Boss 10. The modern run length and actual-completion
victory are deliberate replacements for this legacy schedule.

## King shop and economy

The complete 36 purchase families and all **252 player-specific purchase
triggers** are in [shop.md](shop.md) and `content/legacy/purchases.json`.
The original shop is shared physical geometry with player-filtered conditions.
Most payments filter object group 59 (Kings). Every payment removes all matching
objects in its removal region; there is no quantity cap. Some condition and
removal regions differ, and Building Villager conditions are not King-filtered.
The audit preserves these differences instead of treating thresholds as exact
payment behavior.

Easy converts 2,500 gold per King (26–32), Hard 5,000 (33–39), and Medium 3,500
(809–815). Easy and Hard use five-second timers; Medium has no timer guard.
Blue chooses by destroying selector objects; auto-selection destroys the Easy
selector at 30 seconds. Hard trigger 485 **deactivates** player 2's conversion
trigger 34 while activating the other six. This is an observed asymmetry to fix.

Starting tribute trigger 800 gives player 1 1,500 food, 3,000 wood, 3,000 stone
and 800 gold through negative tribute to Gaia. Triggers 801–806 give equivalent
resources to other slots when their sheep guard is satisfied. Trigger 807's
deactivation list repeats 804 and omits 805, leaving player 6's guarded grant
available after the five-second cleanup. Initialization must become once-only.

The economy includes villagers gathering resources, market exchange, land trade
carts, water trade cogs, garrisoned relics, population and castle purchases, and
resource/King investments. Caravan is granted after five seconds (396–402),
except the Huns probe disables it. Existing trade carts/cogs are tasked in 9–15;
shop purchases create and task replacements. Each player starts with two
automatic garrisoned relics (864–870); relic purchases create three relics plus
two monks, subject to the Gaia relic-area count condition. Extra-relic purchases
transfer ownership of an existing region rather than creating twenty relics.

Reaching the end of a resource area grants 10,000 gold (338–344), 1,000 food
(345–351), or 3,000 stone (352–358), then activates renewable resource spawns.
Gold and stone use modded Gaia resource IDs 1738/1739; renewable food uses berry
bush ID 59. Conditions such as `objects_in_area quantity=0` are recorded as-is;
their engine interpretation must be verified before reusing this implementation.
The exact periodic investment timers and yields are linked to the purchases in
the machine-readable catalog. Preserve the economy's choices and replace its
payment, initialization and renewable-deposit implementation.

Kill triggers 460–466 consume 25 accumulated kills, issue negative tribute for
125 stone and 25 wood, and create a Gaia marker (692). Four markers in the
player's counter area enable the 100-kill reward (854–860), remove all matching
markers and activate a one-shot King grant. Level-stop triggers also activate
King grants; reward activation does not test whether the player killed every
unit. Named state must replace these Gaia object proxies.

## Towers, civilizations and geometry

[towers.md](towers.md) records DAT stats, wall-class changes, construction and
upgrade references. Native watch/guard/keep/bombard towers are IDs 79/234/235/236.
The legacy DAT sets their unit class to **27 (wall)**; general attack purchases
therefore select walls broadly. Special Accursed towers and life meters both
use ID **684**, with custom graphics and different scenario-local roles. The
modern registry must distinguish those roles as named references.

[civilizations.md](civilizations.md) covers all **40 legacy DAT tables**, including
Gaia, each tech-tree and team-bonus effect, and the eight special civilization
trigger families. The audit records full per-civilization object definitions,
resources, all DAT technologies and all effects. Native civilization differences
are not proof of mod changes: no matching unmodified `VER 7.4` DAT was supplied.
The modern game supports more civilizations than this historical package. Their
profiles require separate balance review using current game data.

`content/legacy/lanes.json` identifies lane centers, spawn/exit columns, life
instance references and display variables. Villager transfer triggers 487–500
move villagers between economy/build areas; 692–705 move them across lane sides.
Player 4's right-to-left transfer (702) is one-shot while the other slots loop.
Third/fourth-row purchases (677–690) remove Gaia blockers; the fourth row is gated
by the third-row purchase. Anti-blocking kill zones are in 502–508. Illegal
repairs, conversions and enemy-area access are constrained by 779–785 and
833–839. Preserve the recognizable layout, transfers and expansion progression;
verify replacement blockers and routes in-game.

## Lives, defeat and victory

The life meters are seven placed Accursed towers, references 20332, 20330,
20329, 20328, 20327, 20326 and 20325. Trigger 816 applies 11,500 HP at three seconds;
the operation field differs between player 1 and the other slots and is retained
in the evidence. Base DAT life-tower HP is 3,500. Life display variables start at
15 (871–877), and the HP-band triggers 878–989 continually rewrite them.
Byzantine triggers 826–832 add 5,000 building HP and five to the display variable.
The display is therefore not the authority for elimination.

Regular leak triggers 661–667 deal 1,000 life-building damage when an enemy reaches
an exit, then remove all enemies in that area. Elimination follows destruction
of the corresponding life building: 669–675 repeatedly place Gaia blockers,
735–741 remove economy/shop objects, 772–778 remove remaining lane objects after
five seconds, 840–846 stop leak cleanup after 120 seconds, and 847–853 deactivate
75 player-specific triggers after another 15 seconds. Player-defeated triggers
707–713 also kill the life building. The cleanup is delayed and does not
establish simultaneous elimination handling or save/load safety.

Legacy last-survivor triggers 476–482 have seven destruction conditions and
**no effects**. Final trigger 1010 has only a 70-second timer and seven declare
victory effects, with no final-boss death, surviving-player or cleared-lane
condition. The instructions claim the game is unbeatable; later announcements
claim killing the last boss wins. Both differ from the actual timed trigger.
Replace this with actual-completion solo victory and explicit competitive
elimination/sudden death.

## Migration inventory and review limits

[migration.md](migration.md) and `content/legacy/classification.json` assign every
trigger exactly once to 23 mechanic groups with keep/replace/drop decisions.
`content/migration/objects.json` covers every audited object type in every legacy
civilization context. [objects.md](objects.md) and [dependencies.md](dependencies.md)
identify custom graphics, Gaia display/resource repurposing, boss IDs, blockers,
and replacement strategies. Stock IDs are **candidates** until the stock map and
small in-game probes prove them. No original graphics or DAT is part of the
future gameplay package; wall drag-building and host boot controls are dropped.

The complete original package and supplied DAT reference hashes are retained.
The supplied French and Cumans reference JSON contained structural byte
corruption. A separate complete `legacy/reference/dat-verified/` export was
regenerated from the original DAT with the existing C++ genieutils/GDB tooling;
the original reference directory was preserved. Provenance records both.

This catalog is reviewed against scenario/DAT evidence and the migration decisions.
Automated checks establish reproducible extraction, coverage and references.
They do not establish engine behavior, actual tower-bonus persistence, stock
equivalence, route validity, or multiplayer synchronization. Those checks remain
part of in-game map, mechanic and release validation.
