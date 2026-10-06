# In-game checks

Automated validation shows that builds are reproducible, reload consistently and match
the current definitions. Engine behavior, pathing, saved games and multiplayer need DE.
For every check, record the DE build, civilization, lane, player count and what happened.

## Hosting the game

Build with `uv run ancienttdde build` and copy `.build/game/ancient-td-de.aoe2scenario`
into DE's scenario directory. The scenario embeds its XS and the passive AI for every
computer slot, so no other file needs installing.

Use the standard DE data set, fixed starts, locked teams and All Visible for Reveal Map.
The host selects Fast, the highest lobby game speed, in the lobby: the scenario format
cannot set it. DE also offers a default under Options → Game → Game Speed.

Keep all eight slots occupied. Put humans in any of slots 1–7 and computers in the
others; slot 8 must be the computer enemy. Only human-controlled defense lanes take part:
the game clears computer-filled lanes at the start, apart from their berry mills, and
gives them no resources, enemies or say in victory. Civilization choices stay unlocked,
and a solo player may use any defense lane.

## Full game

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

A solo run reported that a lane's life Outpost does not change when enemies escape and
that no message reports an escape. The game keeps lives in a scenario variable and
lists them only in its objectives.

## Map template

Open `content/maps/stock-de-template.aoe2scenario` in the DE scenario editor with the
standard data set. The template has no purchases or waves; use editor-placed units to
exercise routes.

| Check | Expected result |
| --- | --- |
| Open and save with stock DE | 200×200 map opens without mod, missing assets or external scripts. |
| Native blockers and expansion rows | Boundaries stop units and construction; removable row blockers retain the intended build space. |
| Every lane, including first and last | Representative infantry and cavalry can reach the exit and cannot escape the lane. |
| Every purchase pad | A King can reach each pad; captions display the corresponding legacy purchase. |
| Land trade, every endpoint pair | Stock carts can reach both markets and complete a trade trip. |
| Water trade, every endpoint pair | Stock cogs can reach both docks and complete a trade trip. |
| Economy and life displays | Stock resources, buildings and life Outposts appear correctly without overlap or unwanted attacks. |
| Every siege islet | A placed trebuchet fits, remains isolated and can target the intended tower rows; reserve position can be tested separately. |
| Editor test and save/reload | Map stays available for route inspection and retains placements after save/reload. |

## Mechanic probes

`uv run ancienttdde probe` writes one scenario per probe and an `instructions.md` with
each case's action, expected observation and test settings. Record each observation with
`uv run ancienttdde probe record`; rebuilding keeps recorded results.
`content/probes/observations.json` archives earlier results together with their schema-1
probe manifests; nothing reads it.
