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
- A disconnected or resigned player; its waves, Kings and purchases stop.
- Multiplayer synchronization, spectators and a seven-human stress run.
- A leak lowers the lane's life Outpost health and a chat line reports the lives left.

## Economy and shop

- Kings standing about three seconds on a pad buy it and lose exactly its price; Kings
  walking across or pausing briefly on pads buy nothing; refusals keep the Kings and are
  explained to that player alone, including Bombard Tower attack for civilizations
  without Bombard Towers, and a different refusal is explained at once.
- New Kings, bought units and transferred villagers appear on their spots, where the build
  removed the map's marker flags; a transferred villager keeps its type. A unit on an
  arrival spot delays a purchase, a new King or a transfer without losing anything; the
  arrival clears once the unit moves.
- Gold conversions and kill-reward Kings are announced only to their lane's player; wave,
  leak and elimination messages reach everyone.
- Selecting the unit beside a pad, a transfer label relic, a life Outpost or the hero by
  the shop shows its purchase, destination, lives or credit text from the start; the shop
  has no signs (DE cannot rename them) and the row-end signs are plain markers.
- Lanes start with 750 food, 1500 wood, 1500 stone and 400 gold, and with Ballistics,
  Murder Holes, Caravan, Wheelbarrow, Hand Cart and Spies and Treason researched: towers
  hit moving targets and shoot adjacent enemies; a King buys 2000 wood or 1500 stone.
- 3,500 gold, each cleared wave and every 100 kills bring a King to the lane's stall;
  every 25 kills pay 125 stone and 25 wood.
- Investments pay on their period; the repair crew restores lives for stone.
- Tower attack reaches existing, new and upgraded towers only; Accursed Towers appear on
  the reserved pads with 240 pierce attack.
- Castle Age and Imperial Age add Guard Tower and Keep only for civilizations that have
  them, and the preparation message lists each lane's unavailable towers correctly.
- Transfer pads move one villager at a time between the build and resource areas.
- Reaching the end of each resource row pays its bonus once and adds endless deposits;
  starting mines and bushes keep their normal amounts.
- Starting relics produce gold; bought relics, monks, traders, villagers and the castle
  appear and work; houses, +80 population and the castle set the population limit.

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
