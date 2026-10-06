# Shared game engine

Build and validate the playable scenario:

```bash
uv run ancienttdde build
uv run ancienttdde validate --build .build/game
```

Copy `.build/game/ancient-td-de.aoe2scenario` into DE's scenario directory. The
scenario embeds its XS and passive AI for every computer slot; no other file needs installing.
The generated `instructions.md` contains resource values and the wave schedule.
`build --map-only` retains the logic-free editor template under `.build/map/`.

## Hosting and play

Use the standard DE data set, Fast (the highest lobby game speed), fixed starts
and locked teams. The host must select Fast in the lobby: the scenario format
does not supply that lobby control. DE also offers a default under Options →
Game → Game Speed, as described in the
[official settings guide](https://support.ageofempires.com/hc/en-us/articles/360049024131-Tips-for-Optimizing-Age-of-Empires-II-Definitive-Edition).
Use All Visible for Reveal Map.

Keep all eight slots occupied. Put humans in any of slots 1–7 and computers in
the remaining slots; slot 8 must be the computer enemy. Each computer uses the
embedded passive AI. Only human-controlled defense lanes participate. The engine
clears computer-filled defense lanes at startup, apart from their berry mills,
without granting them resources, spawning enemies there or counting them toward
competitive victory. Civilization choices remain unlocked. A solo player may use
any defense lane, including slot 7.

All seven defense players, P1–P7, start with a mill beside their berries. Each mill
is placed in the scenario and owned by its player, whether a human or a computer
fills the slot. Clearing a computer-filled or eliminated lane keeps that mill.
Each active player receives 30 lives, two Watch Towers and 600 of each resource.
The original villagers, gathering areas and trade placements remain available.
The four trees beside each lane's lumber camps hold far more wood than a run uses,
standing in for the original data's 10,000,000,000 wood per tree. At the start, the
game raises Gaia's Tree A wood to 32,000 and replaces those trees on their own tiles,
so they carry that amount; no tree needs re-creating during play, where a unit or
building could block it. DE applies this effect value as a 16-bit number, so larger
amounts wrap around: 1,000,000 arrived as 16,960.
Each human lane's eight carts and four cogs are ordered to its assigned Gaia
market and dock once during initialization; these traders are original placements.
Build more Watch Towers with the villagers beside the lane. Arrow tower types
receive +4 pierce attack once, including future towers. A surviving lane receives
20 of each resource every five game seconds. Preparation lasts 233 game seconds;
the first enemies arrive 240 game seconds in, two real minutes at Fast, when
preparation income has brought each lane to about 1,540 of each resource.

Fifteen waves spawn enemies in pairs with the same composition and timing for all
surviving lanes. They form three tiers of five, and each tier ends with an elephant
boss wave. Villagers open the schedule as its weakest wave, followed by Militia.
Every wave spawns for 120 game seconds: a regular wave sends a pair
every four seconds, 60 enemies per lane, and a boss wave sends a pair every 30
seconds, eight elephants per lane. Each enemy that reaches the exit flags at the
right-hand end costs one life. Enemies are sent to the tile beyond the flags, and DE
stops a unit sent there just short of that tile's edge, so the flag tile counts as
the exit. A new wave waits for the preceding wave's spawn schedule and remaining
enemies to finish, followed by a 30-second break. The schedule lasts about 41 game
minutes, plus any time needed to clear enemies.

Solo victory requires resolving the entire finale. In competition, the last
surviving lane wins. Multiple survivors after the finale enter sudden death:
every ten seconds all survivors lose an increasing number of lives, beginning
at one and capped at ten per pulse. This guarantees bounded pressure without
creating additional units. If all remaining lanes lose together, all humans
lose; no player wins because its slot was checked first.

The King shop is closed and its signs say so. King purchases and generation,
special tower purchases, raiders, siege, Practice and Endless controls are
unavailable in this ruleset. The two central Hay Stack pads in each lane remain
reserved for special towers; ordinary towers cannot be built there. The supplied
starter defenses are two boosted Watch Towers, not the original special towers.
Civilization balance is provisional. These limits also appear in the scenario instructions.

## State and saved progress

The explicit states are initialization, setup, preparation, wave, boss,
elimination, victory, sudden death and defeat. One looping one-second native
clock calls the shared XS state machine. Native triggers initialize each lane,
create and route enemies, grant resources and declare results. A lane's cleanup
trigger calls XS to remove that player's objects except the berry mill, which it
identifies by reference ID, and removes enemies from the lane path. XS queries each
documented object class rather than an undocumented all-objects wildcard. XS scans
live wave units, charges leaks once, and removes resolved units. It collects all
lanes' losses before entering elimination; the next clock resolves the survivor
set before issuing a result.

Scenario variables hold the authoritative state, countdowns, spawn progress,
participants, lives and requests for native actions. Native consumers acknowledge
their requests once. Initialization checks its saved per-lane flag before applying
resources, tower bonuses or starter towers. No stage activates/deactivates a timer
trigger, and no gameplay trigger executes automatically on load. The only mutable
XS global is a reusable unit-query array; it contains no authoritative progress.

The game uses `xsGetPlayerType` with `cPlayerTypeHuman` to select human lanes,
and `xsGetPlayerInGame` to exclude defeated players and detect subsequent departures.
The [developer's XS API reference](https://www.forgottenempires.net/age-of-empires-ii-definitive-edition/xs-scripting-in-age-of-empires-ii-definitive-edition)
documents that this query returns false for defeated, resigned or dropped players.
The passive enemy retains a protected King on an isolated islet so that gaps
between waves cannot eliminate it. Built-in conquest, relic and other automatic
victory conditions are disabled. Human civilization choices remain unlocked.

Every wave uses a reviewed stock dataset identity. The configurable enemy cap is
80 per lane. If a lane has insufficient capacity for the next batch, all lanes
wait for that batch, preserving the shared schedule. Initialization and subsequent
income/spawn effects are guarded by the live-lane flag. Enemy hit-point and speed
modifications apply once per wave, so repeated batches do not repeatedly change
units already walking the lane.

## Automated checks and DE verification

Builds reload the saved scenario and validate native references and embedded XS.
The manifest hashes all recorded content and generator inputs. Validation rebuilds
the expected game and compares normalized gameplay as well as sidecars; updating
hashes cannot make an altered trigger pass. Protected output paths and staged
construction prevent failed builds from replacing source content.

Behavioral tests execute the generated XS in a C++ harness with substituted DE
queries. Only counted-loop syntax is adapted. Unit queries accept only documented
object and class IDs. They use all eight occupied slots with AI filling unused
human positions. They cover nonconsecutive human lanes, AI departures during the
second wave, an AI-only lobby, berry mills surviving lane cleanup, the first wave's
arrival time, shared spawning, initialization, solo completion, defeat,
simultaneous loss, resignation, sudden death, enemy capacity, leak accounting, an
enemy stopped at the position DE left one short of the exit, and restoration of
saved variables. Separate tests reload
native requests, flags, player settings, embedded AI, victory effects, each berry
mill's owner, position and gatherer access, and the start-of-game replacement of
every lumber tree. These checks do not execute DE's
pathfinder, trigger scheduler or save serializer.

**DE status: retest required.** A user trial with one human and AI in all other
slots ended incorrectly during Men-at-Arms and exposed missing trade orders and
invisible barriers. The [trial record](playtests/solo-with-ai-fillers.md) separates
reported behavior from code changes and remaining checks. A solo retest of the
corrected build stayed in the Militia wave because one enemy stopped just short of
the counted exit; the [retest record](playtests/solo-militia-exit-stall.md) has the
saved-game evidence. A follow-up run of the exit change in DE ended the Militia
wave and started Spearmen.
Record the game build, civilization, lane, player count and observations for:

- Solo victory and defeat, and a repeat on the first and last lane.
- Two nonconsecutive human slots with AI filling the others; AI lanes keep only their
  mills and stay unpaid.
- Automatic land/water trade startup and pairs spawning without colliding with barriers.
- Lumber-camp trees start with 32,000 wood each and keep supplying it.
- A player-owned mill beside the berries in all seven defense lanes, including after
  a computer-filled or eliminated lane is cleared.
- Visible Hay Stack boundaries, blocked expansion rows and reserved tower pads.
- New towers and age upgrades; bonuses persist without duplication.
- Multiple enemies crossing exits together, and simultaneous final losses.
- Each wave ends once its enemies are killed or reach the exit flags.
- Save/reload in preparation, mid-wave, during elimination and sudden death;
  resource grants, spawn cadence and lives match an uninterrupted run.
- A disconnected or resigned player; its waves and income stop.
- Multiplayer synchronization, spectators and a seven-human stress run.

The focused mechanic observations remain in `content/probes/observations.json`.
They validate those tested arenas and do not certify this full-map integration.
