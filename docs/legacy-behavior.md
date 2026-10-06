# Original Ancient TD v5.3 behavior

This catalog records original behavior and reviewed migration decisions. Modern
balance definitions are maintained separately. The original scenario is version
**1.49**, **200 × 200**, with **1,018
triggers**, **7,395 placed objects**, seven human lanes and enemy player 8.
The package credits DRAX6869 / DRAX. The empty modern version-1.59 file is only a
format seed and lives in `content/maps/format-seed.aoe2scenario`.

Evidence uses zero-based trigger storage IDs from the original. Inspect a
specific condition or effect in the audit's `scenario.json`, or its readable
`triggers.md`. Display order and component order are retained independently.
`legacy/provenance.json` identifies the exact source bytes. `uv run ancienttdde audit`
writes the readable reports to `.build/audit/`; the reviewed snapshots and migration
decisions are versioned under `content/`.

## Schedule and enemy behavior

The complete composition and timing are in `content/legacy/waves.json` and the
audit's `waves.md`. There are **46 regular subwaves**: levels 1–9 have
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
triggers** are in `content/legacy/purchases.json` and the audit's `shop.md`.
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
trigger 34 while activating the other six. This asymmetry is observed, not intended.

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

[Tower modifications](#tower-modifications-and-upgrade-dependencies) below records DAT
stats, wall-class changes, construction and upgrade references. Native watch/guard/keep/bombard towers are IDs 79/234/235/236.
The legacy DAT sets their unit class to **27 (wall)**; general attack purchases
therefore select walls broadly. Special Accursed towers and life meters both
use ID **684**, with custom graphics and different scenario-local roles. The
modern registry must distinguish those roles as named references.

The audit's `civilizations.md` covers all **40 legacy DAT tables**, including
Gaia, each tech-tree and team-bonus effect, and the eight special civilization
trigger families. The audit records full per-civilization object definitions,
resources, all DAT technologies and all effects. Native civilization differences
are not proof of mod changes: no matching unmodified `VER 7.4` DAT was supplied.
The modern game supports more civilizations than this historical package. Their
profiles require separate balance review using current game data.

Villager transfer triggers 487–500
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

`content/legacy/classification.json` (rendered as the audit's `mechanics.md`) assigns
every trigger exactly once to 23 mechanic groups with keep/replace/drop decisions.
`content/migration/objects.json` covers every audited object type in every legacy
civilization context. The audit's `objects.md` and [mod dependencies](#mod-dependencies)
identify custom graphics, Gaia display/resource repurposing, boss IDs, blockers,
and replacement strategies. Stock IDs are **candidates** until the stock map and
small in-game probes prove them. No original graphics or DAT is part of the
generated game; wall drag-building and host boot controls are dropped.

The complete original package and supplied DAT reference hashes are retained.
The supplied French and Cumans reference JSON failed to parse when first read, so a
separate complete `legacy/reference/dat-verified/` export was regenerated from the
original DAT with the existing C++ genieutils/GDB tooling. The supplied files now match
that export byte for byte. Provenance records both.

This catalog is reviewed against scenario/DAT evidence and the migration decisions.
Automated checks establish reproducible extraction, coverage and references.
They do not establish engine behavior, actual tower-bonus persistence, stock
equivalence, route validity, or multiplayer synchronization; see
[in-game checks](in-game-checks.md).

## Tower modifications and upgrade dependencies

The following are observed DAT fields, not inferred differences from stock.

| ID | Family | Gaia HP | Class | Range | Reload s | Attack entries | Costs | Adjacent mode | Stack unit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 79 | Watch Tower | 700 | 27 | 8.0 | 2.0 | [{'Class': 27, 'Amount': 2}, {'Class': 11, 'Amount': 0}, {'Class': 16, 'Amount': 7}, {'Class': 3, 'Amount': 5}, {'Class': 30, 'Amount': 1}, {'Class': 34, 'Amount': 7}] | [{'Type': 2, 'Amount': 125, 'Paid': 1}, {'Type': 1, 'Amount': 50, 'Paid': 1}, {'Type': -1, 'Amount': 0, 'Paid': 0}] | 0 | -1 |
| 234 | Guard Tower | 1500 | 27 | 8.0 | 2.0 | [{'Class': 27, 'Amount': 2}, {'Class': 11, 'Amount': 0}, {'Class': 16, 'Amount': 9}, {'Class': 3, 'Amount': 7}, {'Class': 30, 'Amount': 1}, {'Class': 34, 'Amount': 9}] | [{'Type': 2, 'Amount': 125, 'Paid': 1}, {'Type': 1, 'Amount': 50, 'Paid': 1}, {'Type': -1, 'Amount': 0, 'Paid': 0}] | 0 | -1 |
| 235 | Keep | 2250 | 27 | 8.0 | 2.0 | [{'Class': 27, 'Amount': 2}, {'Class': 11, 'Amount': 0}, {'Class': 16, 'Amount': 10}, {'Class': 3, 'Amount': 8}, {'Class': 30, 'Amount': 1}, {'Class': 34, 'Amount': 10}] | [{'Type': 2, 'Amount': 125, 'Paid': 1}, {'Type': 1, 'Amount': 50, 'Paid': 1}, {'Type': -1, 'Amount': 0, 'Paid': 0}] | 0 | -1 |
| 236 | Bombard Tower | 2220 | 27 | 8.0 | 6.0 | [{'Class': 16, 'Amount': 40}, {'Class': 3, 'Amount': 120}, {'Class': 30, 'Amount': 1}, {'Class': 34, 'Amount': 40}] | [{'Type': 3, 'Amount': 100, 'Paid': 1}, {'Type': 2, 'Amount': 125, 'Paid': 1}, {'Type': -1, 'Amount': 0, 'Paid': 0}] | 0 | -1 |
| 684 | Accursed / life tower | 3500 | 52 | 13.0 | 3.0 | [{'Class': 11, 'Amount': 8}, {'Class': 16, 'Amount': 12}, {'Class': 3, 'Amount': 8}, {'Class': 30, 'Amount': 1}, {'Class': 34, 'Amount': 12}] | [{'Type': 2, 'Amount': 150, 'Paid': 1}, {'Type': -1, 'Amount': 0, 'Paid': 0}, {'Type': -1, 'Amount': 0, 'Paid': 0}] | 1 | -1 |

### Civilization coverage

| DAT table | Name | Watch / Guard / Keep / Bombard / Accursed HP |
| --- | --- | --- |
| 0 | Gaia | [700, 1500, 2250, 2220, 3500] |
| 1 | British | [700, 1500, 2250, 2220, 3500] |
| 2 | French | [700, 1500, 2250, 2220, 3500] |
| 3 | Goths | [700, 1500, 2250, 2220, 3500] |
| 4 | Teutons | [700, 1500, 2250, 2220, 3500] |
| 5 | Japanese | [700, 1500, 2250, 2220, 3500] |
| 6 | Chinese | [700, 1500, 2250, 2220, 3500] |
| 7 | Byzantine | [700, 1500, 2250, 2220, 3500] |
| 8 | Persians | [700, 1500, 2250, 2220, 3500] |
| 9 | Saracens | [700, 1500, 2250, 2220, 3500] |
| 10 | Turks | [700, 1500, 2250, 2220, 3500] |
| 11 | Vikings | [700, 1500, 2250, 2220, 3500] |
| 12 | Mongols | [700, 1500, 2250, 2220, 3500] |
| 13 | Celts | [700, 1500, 2250, 2220, 3500] |
| 14 | Spanish | [700, 1500, 2250, 2220, 3500] |
| 15 | Aztecs | [700, 1500, 2250, 2220, 3500] |
| 16 | Mayan | [700, 1500, 2250, 2220, 3500] |
| 17 | Huns | [700, 1500, 2250, 2220, 3500] |
| 18 | Koreans | [700, 1500, 2250, 2220, 3500] |
| 19 | Italians | [700, 1500, 2250, 2220, 3500] |
| 20 | Indians | [700, 1500, 2250, 2220, 3500] |
| 21 | Incas | [700, 1500, 2250, 2220, 3500] |
| 22 | Magyars | [700, 1500, 2250, 2220, 3500] |
| 23 | Slavs | [700, 1500, 2250, 2220, 3500] |
| 24 | Portuguese | [700, 1500, 2250, 2220, 3500] |
| 25 | Ethopians | [700, 1500, 2250, 2220, 3500] |
| 26 | Malians | [700, 1500, 2250, 2220, 3500] |
| 27 | Berbers | [700, 1500, 2250, 2220, 3500] |
| 28 | Khmer | [700, 1500, 2250, 2220, 3500] |
| 29 | Malay | [700, 1500, 2250, 2220, 3500] |
| 30 | Burmese | [700, 1500, 2250, 2220, 3500] |
| 31 | Vietnamese | [700, 1500, 2250, 2220, 3500] |
| 32 | Bulgarians | [700, 1500, 2250, 2220, 3500] |
| 33 | Tatars | [700, 1500, 2250, 2220, 3500] |
| 34 | Cumans | [700, 1500, 2250, 2220, 3500] |
| 35 | Lithuanians | [700, 1500, 2250, 2220, 3500] |
| 36 | Burgundians | [700, 1500, 2250, 2220, 3500] |
| 37 | Sicilians | [700, 1500, 2250, 2220, 3500] |
| 38 | Poles | [700, 1500, 2250, 2220, 3500] |
| 39 | Bohemians | [700, 1500, 2250, 2220, 3500] |

### Relevant DAT technologies and effects

| Tech ID | Name | Civilization restriction | Required technologies | Effect ID |
| --- | --- | --- | --- | --- |
| 63 | Keep | -1 | [103, 140, -1, -1, -1, -1] | 63 |
| 64 | Bombard Tower | -1 | [103, 47, 285, -1, -1, -1] | 64 |
| 140 | Guard Tower | -1 | [102, 127, -1, -1, -1, -1] | 139 |
| 194 | Fortified Wall | -1 | [102, -1, -1, -1, -1, -1] | 187 |
| 203 | Bow Saw | -1 | [102, 202, 762, -1, -1, -1] | 196 |
| 442 | Free Guard Tower | 18 | [102, -1, -1, -1, -1, -1] | 139 |
| 443 | Free Keep | 18 | [103, -1, -1, -1, -1, -1] | 63 |
| 444 | Free Bombard Tower | 18 | [103, 47, -1, -1, -1, -1] | 64 |
| 608 | Arrowslits | -1 | [103, -1, -1, -1, -1, -1] | 633 |
| 610 | Arrowslits (Guard tower) | -1 | [608, 140, 442, 775, -1, -1] | 635 |
| 611 | Arrowslits (Keep) | -1 | [608, 63, 443, 775, -1, -1] | 636 |

### Scenario operations

| Trigger | Name | Observed operation |
| --- | --- | --- |
| 49 | Tower Attack +4 | {'armour_attack_quantity': 4, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 56 | Tower Attack +10 | {'armour_attack_quantity': 10, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 63 | Tower Attack +25 | {'armour_attack_quantity': 25, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 70 | Tower Attack +50 | {'armour_attack_quantity': 50, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 77 | Tower Attack +100 | {'armour_attack_quantity': 100, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 84 | Tower Attack +170 | {'armour_attack_quantity': 170, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 91 | Tower Attack +255 | {'armour_attack_quantity': 255, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 98 | Tower Attack +750 | {'armour_attack_quantity': 250, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []}; {'armour_attack_quantity': 250, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []}; {'armour_attack_quantity': 250, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 105 | Bombard Attack +400 | {'armour_attack_quantity': 144, 'armour_attack_class': 1, 'object_list_unit_id': 236, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': 2, 'operation': 2, 'selected_object_ids': []} |
| 112 | Tower Attack +3 Every 1 Minute | {'armour_attack_quantity': 3, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 119 | Tower Attack +1 Every 30 Seconds | {'armour_attack_quantity': 1, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 238 | Activate +1 Atttack Every 30 Seconds |  |
| 245 | Activate +3 Attack Every Minute |  |
| 259 | Castle Age | {'source_player': 1, 'technology': 102, 'force_research_technology': -1}; {'source_player': 1, 'technology': 140, 'force_research_technology': -1} |
| 266 | Imperial Age | {'source_player': 1, 'technology': 103, 'force_research_technology': -1}; {'source_player': 1, 'technology': 63, 'force_research_technology': -1} |
| 273 | Left Accursed Tower | {'armour_attack_quantity': 232, 'armour_attack_class': 3, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': 33, 'area_y1': 12, 'area_x2': 33, 'area_y2': 12, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': []} |
| 280 | Right Accursed Tower | {'armour_attack_quantity': 232, 'armour_attack_class': 3, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': 33, 'area_y1': 18, 'area_x2': 33, 'area_y2': 18, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': []} |
| 720 | +1 AP every 5 seconds | {'armour_attack_quantity': 1, 'armour_attack_class': 0, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': 27, 'object_type': -1, 'operation': 2, 'selected_object_ids': []} |
| 792 | Repair villie |  |
| 816 | Tower Hp | {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': 2, 'selected_object_ids': [20332]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 2, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20330]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 3, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20329]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 4, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20328]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 5, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20327]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 6, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20326]}; {'quantity': 11500, 'object_list_unit_id': -1, 'source_player': 7, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': -1, 'selected_object_ids': [20325]} |
| 826 | Byz | {'quantity': 5000, 'object_list_unit_id': -1, 'source_player': 1, 'area_x1': -1, 'area_y1': -1, 'area_x2': -1, 'area_y2': -1, 'object_group': -1, 'object_type': -1, 'operation': 2, 'selected_object_ids': [20332]} |

The packed attack fields are retained both as parser-decoded class/quantity and
raw integer payload in `scenario.json`. For example, Bombard Attack +400 uses
raw payload 65,680 (decoded class 1 / quantity 144), and the advertised +750
purchase uses three +250 effects. Never reinterpret packed values from the name
alone. The +3 recurring attack trigger is named "Every 1 Minute" but has a
30-second timer. The historical hints say +700 for the +750 purchase and 250
stone for the 375-stone investment. Exact decoding semantics, new construction
and age-upgrade persistence require focused in-game probes.

General tower attack operations select object group 27 and can reach every
legacy wall-class object, including genuine walls and unused proxy units. Stock
towers have ordinary construction behavior; dragging tower walls is dropped.
`content/migration/objects.json` explicitly replaces the legacy tower class and
construction behavior while preserving family identities as candidates. Life
meters and bought special towers both use legacy ID 684; map anchors and
modern state name them separately.

## Mod dependencies

Every supplied graphics file is dropped from the generated game; retained semantics
use stock appearances, generated text and scenario-local logic. Each audited object's
original assets, DAT graphics and linked objects are in the audit's `dat.json`, and
its replacement decision is in `content/migration/objects.json`.

Gaia 1738 is a gold deposit and Gaia 1739 is a stone deposit; these numeric IDs
represent unrelated units in modern DE. Candidates are gold mine 66 and stone
mine 102. The same legacy IDs in human/enemy DAT tables are empty definitions
and are explicitly dropped in those contexts. Gaia 1740–1776 are price and
instruction signs with custom bitmaps; corresponding human definitions are
empty. Bosses 1777–1786 are custom living units whose modern IDs include
decorative or unrelated stock objects, so they are replaced with explicit stock
boss carriers (Champion as an initial prototype candidate). Special towers and
life meters both use 684, and require separate named instance roles.

The current parser dataset supplies stock candidate names; it does not prove
behavior or rendering in a current game build. Legacy map terrain IDs also
require in-game verification. The legacy scenario remains unchanged, and
all selected object definitions and graphic chains are available in `dat.json`.
