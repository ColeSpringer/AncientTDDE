# Stock-DE mechanic probes

Generate seven self-contained, 64×64 scenarios from the empty version-1.59 format
seed. The original package and legacy DAT exports are unnecessary.

```bash
uv run ancienttdde probe
uv run ancienttdde validate --probes .build/probes
uv run ancienttdde probe --only payments --only siege --output .build/transactions
```

Only copy the `.aoe2scenario` files into DE's scenario directory. Open them in the
scenario editor, use the standard data set, and run a test as player 1. Read the
generated `instructions.md` and scenario instructions for the settings, control-pad
locations, steps and expected observations.

Use these settings for each experiment. The scenarios save the settings below
except Reveal Map, which must be selected in DE before starting:

| Setting | Default | Purpose |
| --- | --- | --- |
| Reveal Map | All Visible, selected in DE's test/lobby dialog | Observe the entire arena without scouting. |
| Lock Teams | On | Preserve the intended alliances and opponents. |
| Players choose teams / random start points | Off | Preserve scripted owners and fixed placements. |
| Civilization | Britons, with civilization choice unlocked | Provide a repeatable baseline while allowing deliberate civilization comparisons. |
| Starting age | Dark Age | Let the experiment research its own required ages and upgrades. |
| Population cap | 200 | Allow the supplied units and trader replacement tests. |
| Resources | Zero in the file; triggers supply each experiment's resources | Keep payment and trade measurements comparable. |
| Full Tech Tree / secondary game modes | Off | Preserve stock technology access and avoid unrelated game rules. |
| Victory | Custom, with all built-in conditions disabled and allied victory off | Keep the experiment running until the tester exits. |
| Computer personalities | Locked to embedded passive AI | Keep enemy behavior under scenario control. |
| Unused computer slots | One protected King on the eastern edge | Keep every active player in the game without adding combat units, production or an economy. |

The tower probe deliberately places one P1 Town Center, two builders and a scout.
Other probes supply only their experiment units. The common enemy placeholder is
one protected King when that player has no experiment units: it counts as a unit
for the engine's defeat check but cannot attack, build, gather or be converted,
so it needs no enclosure, and the embedded passive AI never moves it. Every King
payment condition is scoped to its pad region, so a marker on the map edge is
never counted or consumed. Validation rejects active slots that the engine would
defeat at game start. Whether the engine adds any unexpected starting units
still needs to be checked during the DE run.

Each scenario lists its setup text as an open objective and shows the probe title
on screen. The objective trigger stays enabled, because DE hides objectives of
disabled triggers, and waits on a variable that no trigger changes, because a
trigger without conditions fires at once and marks its objective complete.
Buildings are stored at the center of their footprint: 4×4 Markets and Town
Centers sit on tile corners (whole coordinates) and odd footprints on tile
centers. Validation rejects buildings placed off that grid.

In DE's test/lobby dialog, select **Reveal Map: All Visible**, **Allow Cheats off**, Normal game speed, Lock
Speed on, Standard resources, Standard starting/ending age, population 200, no
treaty, Turbo Mode off, Full Tech Tree off, handicap 100%, and Standard AI
difficulty, where those controls are available. Use the scenario's victory rules.
The pinned parser's [scenario format fields](https://raw.githubusercontent.com/KSneijders/AoE2ScenarioParser/master/AoE2ScenarioParser/versions/DE/v1.59/structure.json)
do not expose persisted Reveal Map, Allow Cheats or game-speed settings. The
generator therefore cannot select those dialog options through the supported
scenario fields. Leaving Reveal Map on Normal still leaves the arena fogged.

The earlier Modify Resource 203 attempt did not reveal the map during testing;
[other testers also report that resources 203 and 204 stopped working](https://forums.ageofempires.com/t/how-to-reveal-map-with-xs-sxript/283032).
The current [XS function reference](https://ugc.aoe2.rocks/general/xs/functions/functions/)
lists no replacement for selecting the map reveal mode. Set Player Visibility
shares another player's line of sight rather than selecting All Visible. The
probes use the dialog setting and contain no map revealer objects or sight-range
overrides. Before each experiment, confirm that the whole arena is visible and
that the game remains running after loading.

## Keeping the game running

The first probe files awarded P1 victory as soon as they loaded. Two engine
rules combined to cause this:

- The engine marks a player defeated when they own nothing but towers (Outposts
  included), walls, gates, farms, fish traps, trade carts, trade cogs, fishing
  ships or transport ships. The original Age of Kings manual lists these
  exceptions for conquest, and DE scenario designers still report players losing
  at launch without a counted unit or production building. The placeholder
  Outposts therefore left every computer player defeated at game start.
- Choosing Custom victory does not clear the seed's Conquest checkbox, so the
  files were effectively Conquest games whose enemies were all defeated at
  tick zero.

The generator now addresses both halves. Victory is Custom with every built-in
condition cleared and "all custom conditions required" off, so only a Declare
Victory trigger effect could end a probe, and none exists. Every active player
also keeps at least one object the engine counts: experiment units or production
buildings where the probe supplies them, otherwise one King that is protected
from attacks and deletion. Validation checks the victory fields and the counted
objects after reloading every scenario. The same two rules apply to the complete
map: each player needs a permanent counted object, since towers, life Outposts
and spent Kings do not keep them in the game, and eliminations and the final
victory must be declared by triggers rather than left to conquest. The protected
home Market and Dock already fill that role for players who trade; a slot with
no production building needs a protected King or an equivalent counted object.

The embedded AI name and text are paired with the custom AI selector in each
computer slot; the selector values are described in the
[AOKTS scenario format reference](https://raw.githubusercontent.com/mwhiter/aokts/master/scx_format.txt).
Native effects use the explicit owner of their selected instances, including
Gaia/allied endpoints and enemy life markers. Display countdowns use the parser's
seconds setting, matching the game-second timer conditions.

| Scenario | Experiment |
| --- | --- |
| `payments` | A 3-King purchase grants 100 gold; exact, excess, repeat, insufficient and closed-pad requests. Native removal is limited to the price and the purchase region. |
| `towers` | One +4 pierce-attack modification to explicit Watch Tower, Guard Tower and Keep definitions; new construction, forced age/upgrades, unrelated objects and save/load. |
| `trade` | Stock cart/cog trading with allied P2, one home market/dock per medium; protected endpoints with attacks requested through a control pad. Gold starts at zero. |
| `trade-gaia` | Matching land/water layout with Gaia-owned partners and capture disabled; a separate compatibility comparison. |
| `raiders` | Player-owned scout and galley purchases, 3-King payments charged only after successful creation, living caps of 2, native combat, a stock-blocker enclosure, an isolated water basin and replacement traders. |
| `siege` | Competing P1/P8 requests, two stationary deployed trebuchets, a 10-second warning, 60-second activity, both-form cleanup and 60/120-second shared/buyer cooldowns counted in variables. |
| `scripts-enemy` | Embedded XS heartbeat and a passive P8 whose units are created and tasked by triggers; save/load continuity. |

Both trade files have one P1 market at `(8,12)` and one P1 dock at `(8,44)`,
with partners at `(54,12)` and `(54,44)`. There is one cart and one cog, so there
is no competing owned home endpoint. Test `trade` first and observe at least two
complete return trips. Moving the control King from `(8,22)` to the pad at `(8,4)`
starts the endpoint attack test; attackers remain idle until then.

Test Gaia separately in `trade-gaia`. Check the partner's owner before and after
the trader approaches. The partners use the parser's `CaptureFlag.NEVER` setting;
DE documents this control for preventing automatic conversion in its
[scenario editor update notes](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/).
A trader stopping at a partner that remains Gaia-owned is a failed compatibility
case. A partner changing owner invalidates that run's ownership setup. Compare
against the allied file and record what actually occurs; Gaia trade is not
assumed to work.

Raider purchases use an embedded XS transaction that checks the buyer's live
unit count during execution. It also rechecks ownership, health, garrison state
and pad position for the three payment Kings. The transaction calls
[`xsCreateUnit`](https://ugc.aoe2.rocks/general/xs/functions/functions/#91-xscreateunit)
with collision checking enabled and removes those three Kings only after the
engine returns a valid unit ID. A blocked spawn keeps the payment and retries
while three Kings remain on the pad. Move the previous raider away from `(18,16)`
for land or `(18,50)` for naval purchases. Two living raiders of that type prevent
further purchases, and a death frees a slot. Opposing raiders do not count toward
the buyer's cap.

During manual testing of the earlier mixed layout, the tester reported that the
Gaia partners became P1-owned and their traders stopped, while the allied traders
returned to another P1 home endpoint. Those observations exposed two setup
confounds; they do not establish Gaia compatibility with capture disabled.

The siege arena has one surviving rival, so the provisional `20 + 5 per rival`
price is 25 Kings. Requests check both life markers and both cooldown counters
before claiming the global owner variable and consuming payment. Life
markers are protected Barracks: a production building the engine counts, so P8
stays in the game after spending its Kings, while its Keep alone would not keep
it there. Nobody receives stockpile resources in this arena, so the Barracks
cannot train anything, and a building cannot be walked onto a pad or confused
with the King payments. Removing a marker with a control pad simulates
elimination without ending the solo experiment; separate triggers also handle
the game reporting an actual player defeat. Cleanup removes both packed and
unpacked trebuchets. Spare Kings allow rejection checks with sufficient payment.
This arena measures the mechanic with one rival; it does not establish
full-game player-count behavior.

Three engine behaviors shape the siege triggers:

- **Own Fewer Objects is inclusive.** The condition holds when the player owns
  *at most* the quantity ([UGC condition reference](https://ugc.aoe2.rocks/scenarios/triggers/conditions/conditions/),
  [AoKH trigger laws](https://aok.heavengames.com/cgi-bin/aokcgi/display.cgi?action=ct&f=4,31318,,all)).
  A quantity of 1 therefore held while the single Barracks still stood, so the
  elimination cleanup fired the moment a purchase claimed ownership, cancelled the
  pending spawn and started both cooldowns. Elimination now checks for a quantity
  of 0. The same reading applies to any living-cap condition: a cap of `n` needs
  quantity `n - 1`.
- **Timer conditions resume rather than restart.** A trigger's elapsed count is
  kept while it is disabled, and a one-shot trigger that fired keeps its full
  count, so a warning, expiry or cooldown trigger activated a second time fires at
  once ([classic design FAQ](https://gamefaqs.gamespot.com/pc/914421-age-of-empires-ii-the-conquerors-expansion/faqs/24505),
  [DE bug report](https://forums.ageofempires.com/t/editor-timer-condition-doesnt-reset-itself-upon-trigger-deactivation/251204)).
  Stage triggers therefore stay enabled and looping, and nothing activates or
  deactivates triggers. A purchase sets `siege.phase` to warning and
  `siege.elapsed` to 0; a looping one-second clock adds to `siege.elapsed` while a
  phase is active; the spawn fires at 10 elapsed seconds and expiry at 60. The
  shared and per-buyer cooldowns are variables holding remaining seconds, set to
  60 and 120 on cleanup and counted down by their own one-second clocks, and a
  purchase requires both relevant counters to read 0. Display timers show the
  warning, activity, shared cooldown and buyer cooldown; they are visual only and
  may differ from the counters by up to a second.
- **Computer-owned Kings walk to garrisonable buildings.** The engine sends a
  computer player's Kings to any building it owns that can garrison them,
  regardless of the AI script; the
  [Immobile Units AI notes](https://forums.ageofempires.com/uploads/short-url/2ZBRhQuDS1zzliM1ON2SNoKENj7.txt)
  record the same observation. P8 owns a Keep, so its payment Kings would leave the pad. The
  initialization trigger sets the movement speed of P8's King type to 0 so the
  payment stays where the pad condition counts it; P1's Kings keep their speed.
  A computer slot in the complete map that owns Kings and towers needs the same
  treatment or ungarrisonable towers.

The spawned units are unit 42, the deployed Trebuchet that can fire at once;
unit 331 is the packed form. Both forms have movement speed 0, so ordering a
target outside range is expected to leave a packed trebuchet in place that must
be unpacked by hand. Both rival Keeps lie within the 16-tile range of both islets.

Tower bonuses use native type modifications once, including each upgrade type,
so the experiment can reveal whether the engine preserves or duplicates them on
technology upgrades. A parser reload cannot answer that question. Use the default
Britons civilization for comparison, then repeat for civilizations with different
access or native bonuses.

## Recording observations

All 30 cases initially have empty observation histories. Nothing is marked as an
in-game pass by building or validating the files. After performing a case, append
an observation with the tested game build, tester and concrete evidence:

```bash
uv run ancienttdde probe record --suite .build/probes \
  --case payments.excess --status pass --game-build 'DE build number' \
  --tester 'Your name' --notes '5 Kings entered; 3 removed, 2 remained; +100 gold'
```

`pass`, `fail` and `blocked` are available. Keep earlier failures and append
subsequent observations instead of deleting history. Each observation includes a
UTC timestamp and the scenario's normalized SHA-256 digest. Results are mutable
and separate from the hash-checked generated artifacts. A repeat build preserves
the results file; a content change that conflicts with recorded results requires
a new output directory. Automated validation checks that recorded observations
refer to the current scenario, but does not certify the reporter's observations.
Outputs cannot replace source trees, source-directory symlink targets, their
ancestors, or unrelated colliding artifacts. Existing generated files are replaced
only when their manifest identifies a compatible probe suite. Recording replaces
the results file atomically and rejects links outside the suite.

## Automated evidence and remaining checks

Builds use modern-only parser subprocesses, reload every scenario, check native
references, stock placements, player setup, scenario options, embedded AI and the
placement allocator, and validate XS with errors treated as failures. Manifests record source and artifact
hashes and normalized gameplay content. Validation regenerates the current expected
scenario, preventing edited hashes and sidecars from masking a logic change.

The automated tests inspect payment thresholds and removal limits, explicit tower
types, endpoint protection without trader protection, siege
locking, both-form cleanup, variable-driven stage timing and cooldown clocks
without trigger activation, elimination counts of zero, immobile rival Kings,
deployed trebuchets and isolated islet geometry.
They also check rebuild/result preservation, source-directory protection, CLI
errors, disabled built-in victory conditions, persisted scenario settings, active
slots that survive game start, open setup objectives, footprint-aligned
buildings, unambiguous trade homes, Gaia capture flags, optional endpoint
attacks, and rejection of edited scenario options, misplaced buildings or
invalid XS.

The raider regression tests compile the actual serialized XS transaction and
purchase functions against a small substitute for the DE unit and array APIs.
They exercise both media with blocked spawns, repeated purchases at the living
cap, insufficient and excess payment, owner and pad filtering, and replacement
after death. This checks transaction behavior and serialized arguments; it does
not execute the DE engine or establish its collision and pathing behavior.

**Recorded DE results:** Cole recorded all 30 cases on 2026-10-05 using game build
25464371 in `.build/probes/results.json`: 29 passed and `raiders.cap` failed.
That failure reported purchases above the cap in both media and Kings consumed
when the previous raider blocked the spawn. All eight siege cases passed.

The revised raider scenario is generated separately so those observations remain
attached to the files that were tested:

```bash
uv run ancienttdde probe --only raiders --output .build/probes-raider-fix
uv run ancienttdde validate --probes .build/probes-raider-fix
```

Cole subsequently confirmed that living caps, blocked-spawn payment preservation
and replacement after death passed for both land and naval raiders in the revised
file. These follow-up passes are recorded as `raiders.cap` and
`raiders.replacement` in `.build/probes-raider-fix/results.json`; the original
failure remains in its own history. The other three raider cases retain their
passes from the original suite and have no additional observations of the revised
file. Together, the original checks and focused retest cover all 30 cases, with
no unresolved reported gameplay failure.

The [archived observations](../content/probes/observations.json) preserve both
manifests and observation ledgers in version control. They retain the tested
content hashes, game build, tester, timestamps and notes while generated scenarios
and inspection sidecars remain under `.build/`. This archive is evidence from
those testing sessions, not a generated suite accepted by `validate --probes`.
Record further runs against their generated suite using `probe record`.
Multiplayer synchronization and full-capacity performance require separate real
multiplayer testing.
