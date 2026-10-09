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
the game clears computer-filled lanes at the start and gives them no resources, enemies or
say in victory. Civilization choices stay unlocked, and a solo player may use any defense
lane. The lobby's Difficulty sets a solo run's level; run options are selected in game, in
the row of Outposts below the shop.

## Full game

- Solo victory and defeat, and a repeat on the first and last lane. No "has been
  defeated" line appears at the start; when a solo lane falls, the result line and the
  result objective still appear.
- Two nonconsecutive human slots with AI filling the others; AI lanes stay unpaid, show no
  lives line and no defeat line.
- Automatic land/water trade startup and pairs spawning without colliding with barriers.
- An endless tree with 32,000 wood stands behind each lumber tree from the start, and the
  lumberjacks move on to it once their placed tree is gone.
- The resource villagers gather gold, berries, stone and wood from the first second
  without orders; the build-area villagers wait.
- A player-owned mill beside the berries in every human lane. Computer-filled and
  eliminated lanes are cleared completely, mills included; each keeps one King on its spare
  siege islet so DE does not defeat the slot.
- Visible Hay Stack boundaries, blocked expansion rows and reserved tower pads.
- New towers and age upgrades; bonuses persist without duplication.
- Multiple enemies crossing exits together, and simultaneous final losses.
- Each wave ends once its enemies are killed or reach the exit flags.
- Enemies appear in pairs side by side, one row above and one below the lane's center
  (threes fill the three rows), and walk in files to the exit.
- Each of the ten bosses shows at most 32,767 hit points and is refilled from the total the
  chat announces as towers hit it, so it falls only once that total is spent; its lane's
  player is told at three quarters, half and a quarter; a boss reaching the exit costs 5
  lives.
- Enemies never attack towers, villagers or Kings (the enemy is allied to every lane; lanes
  are its enemies), and towers still fire at them; cavalry walks at its stock speed, pausing
  at most briefly every 10 seconds when the lane's enemies are ordered on again, and no sound
  plays when enemies appear.
- No stutter in the first second (the script fills its lookup tables then), in the choice
  window or in preparation, and late waves with 60 or more enemies alive and 30 or more idle
  Kings stay smooth.
- Wave 1 is a little easier than before on Normal and Hard, waves 7–30 press hard, the bosses
  fall only to a strong attack ladder, and Hard is clearly above Normal (the Pressure table in
  `docs/balance.md` shows the model for each level).
- Save/reload in preparation, mid-wave, during elimination and sudden death;
  resource grants, spawn cadence and lives match an uninterrupted run, and purchases, pad
  counts and enemy counts keep working after the load (the script's lookup tables survive or
  are filled again).
- A disconnected or resigned player; its waves, Kings and purchases stop.
- Multiplayer synchronization, spectators and a seven-human stress run.
- A leak lowers the lane's life Outpost health and a chat line reports the lives left.

## Economy and shop

- Kings standing about three seconds on a pad buy it and lose exactly its price; Kings
  walking across or pausing briefly on pads buy nothing; refusals keep the Kings and are
  explained to that player alone, including Bombard Tower attack for civilizations
  without Bombard Towers, and a different refusal is explained at once.
- Every pad shows one flag per King of its price (castle 1, +1 attack/30 s 4, each raider
  3, siege 15, each tower-row half 3). A Hay Stack divider splits the tower-row pad: the left
  half opens the 3rd row, the right half the 4th.
- New Kings, bought units and transferred villagers appear on their spots, where the build
  removed the map's marker flags; a transferred villager keeps its type. A unit on an
  arrival spot in the lane's own areas delays a purchase or a transfer without losing
  anything, and the arrival clears once the unit moves. Kings, traders and raiders appear
  even with another lane's unit on their spot.
- Gold conversions and kill-reward Kings are announced only to their lane's player; wave,
  leak and elimination messages reach everyone.
- Selecting the unit beside a pad, a transfer label relic, a life Outpost or the hero by
  the shop shows its purchase, destination, lives or credit text from the start; the shop
  has no signs (DE cannot rename them) and the row-end signs are plain markers.
- The dock offers no Fishing Lines, Gillnets or Galleon, the blacksmith no infantry or
  archer armor, and a bought castle no unique technology that touches only units no lane
  has; Celts see none of them.
- Lanes start with 750 food, 1500 wood, 1500 stone and 400 gold, and with Ballistics,
  Murder Holes, Caravan, Wheelbarrow, Hand Cart and Spies and Treason researched: towers
  hit moving targets and shoot adjacent enemies; a King buys 2000 wood or 1500 stone.
- 2,000 gold, each cleared wave and every 100 wave kills bring a King to the lane's stall;
  every 25 wave kills pay 125 stone and 25 wood (kills count with the enemy allied to the
  lanes). Raiders killing rival traders and raiders earn nothing.
- Investments pay on their period; the repair crew restores lives for stone.
- A starting trade cart's return adds about 100 gold on the game's routes (the balance
  tables' assumption); record the real amount for a cart and a cog.
- Tower attack reaches existing, new and upgraded towers only and keeps rising past +255
  (+750 shows as +750, and the periodic +1 and +3 keep climbing); Accursed Towers appear on
  the reserved pads with 240 pierce attack.
- Castle Age and Imperial Age add Guard Tower and Keep only for civilizations that have
  them, and the preparation message lists each lane's unavailable towers correctly.
- Preparation also announces each lane's civilization line, with the lane's own King price
  when its profile changes it; a civilization the content does not list (one newer than the
  build) plays the default profile and is announced as such.
- Achaemenids, Athenians, Thracians and Puru keep the Keep: their tech-tree screens omit it
  but the data leaves it researchable, so Imperial Age should bring Keeps and the preparation
  line should not list the Keep as unavailable.
- A profile's adjustments arrive once the lane is set up and never again after a save during
  preparation: starting Kings at the stall, resources, population, technologies researched,
  tower attack and hit points on existing and new towers, cheaper tower stone, relics inside
  the first monastery, and starting traders that trade at once.
- A lane with a King price discount converts gold at its own price while the opening chat
  names the base price; scaled kill rewards pay the scaled stone and wood.
- A purchase a profile grants from the start is owned before the first second ends: its
  units stand on the shop's spots (villagers walk clear, traders trade, a castle stands on
  its site, relics wait for the monks), Castle Age arrives with Guard Towers, an investment
  pays from the first period, and the pad refuses the Kings as already owned.
- Transfer pads: the flag at each walkway's dead end shows its caption (if DE draws none,
  the relic two tiles away names the flag), and a villager sent onto that tile reappears at
  the arrival, one at a time.
- Reaching the end of each resource row pays its bonus once and adds endless deposits;
  starting mines and bushes keep their normal amounts.
- Starting relics produce gold; bought relics, monks, traders, villagers and the castle
  appear and work; a lane starts with no population headroom of its own, the Huns
  included, so only +80 population, the castle and a profile's own population raise it.
- An Armenian lane finds a free relic in one of its monasteries, and a Saxon lane's towers
  and Accursed Towers fire one arrow of their own after Castle Age.
- The trade-income probe's routes are short; on the game map, time a cart and a cog on
  their real routes and set `trade_gold_per_trip` from that. The civilization bands are
  tuned to the 100-gold estimate, so trade-heavy profiles may need retuning afterwards.

## Modes and competition

- The chooser's view opens on the run options, with "Run options close in" counting down
  60 game seconds and two on-screen lines naming the options and practice controls left to
  right. DE draws each Outpost's one-word caption and each pad exhibit's short tag above it
  (never a Sign's); every exhibit stands where the original placed it. Selecting an Outpost
  shows its full option, and an exhibit its full purchase.
- The first human lane's first selection fixes the options and begins preparation at once,
  even when it is the default (Standard in a competitive game keeps PvP off); a later
  selection, or one by another lane, changes nothing
  and is explained to that player. Without a selection, Standard or PvP off stands when
  the countdown ends. The run options then disappear, and the practice controls too unless
  the run is Practice; their two lines leave the objectives box (not struck through) while
  the wave and lives lines stay.
- Solo: Easiest plays Easy and Hard plays Hard (the opening chat names the level and gold
  per King); competitive games play Normal whatever the lobby says.
- Practice: start next wave, Kings, resources and lives each work once per selection, and
  again after selecting something else; the Practice objective appears and the result says
  the run was assisted.
- The Endless, sudden death, siege and result objectives stay hidden until they apply.
- Endless continues past the finale with the announced hit points and armor (the armor keeps
  rising past +255), counts down each wave, and ends with a result when the lane falls.
- Sudden death keeps the waves coming for every survivor, announced as sudden death waves,
  and costs lives every 30 seconds.
- Competitive games start with PvP off and say so; PvP on makes the defense lanes enemies at
  the first wave; PvP off keeps them neutral and raider and siege purchases keep their Kings.
- The raider and siege pads are road blocks with Hay Stack borders on the shop's east side,
  the land raider's in the old 4th-row block; each one's King stands centred in its
  beach-side Hay Stack line.
- Raiders arrive below their market or dock, walk clear, fight rival traders and raiders,
  and cannot leave their trade area; the third raider of a kind is refused (a fourth for
  the listed civilizations) and upgraded fire ships still count.
- Kings, markets, docks, life Outposts and yurts cannot be attacked, including from the
  channel edge by fire galleys.
- Siege: 15 Kings plus 3 per surviving rival (2 players pay 18, 7 pay 33); after the
  countdown two trebuchets stand on each rival's islets, attack chosen towers and cannot
  move, packed or not; expiry removes both forms; competing or cooling-down purchases keep
  their Kings, and the holder buying again is told it holds the siege already; the holder's
  elimination ends it; save/load during the warning and the siege keeps both.
- Villagers build only towers, mills, camps and farms: no houses, walls, gates, outposts,
  markets, blacksmiths, universities, barracks, docks, castles, monasteries or town
  centers; docks train only trade cogs; a bought castle trains nothing and fires no arrows;
  monks cannot convert. All of this still holds after buying Castle Age and Imperial Age,
  and the castle stays silent after Fletching, Bodkin Arrow and Bracer. Crenellations,
  Greek Fire, Yasama and Stronghold cannot be researched; in competitive games neither can
  Eupseong or Artillery.
- A tower or tower foundation in the resource area disappears, and its player is told why.
- Bought monks, castles, fire galleys and siege trebuchets still appear although their
  owners cannot train or build them.
- The enemy's protected King stands alone on the islet below the life Outposts.

## Map template

Open `content/maps/stock-de-template.aoe2scenario` in the DE scenario editor with the
standard data set. The template has no purchases or waves; use editor-placed units to
exercise routes.

| Check | Expected result |
| --- | --- |
| Open and save with stock DE | 200×200 map opens without mod, missing assets or external scripts. |
| Native blockers and expansion rows | Boundaries stop units and construction; removable row blockers retain the intended build space. |
| Every lane, including first and last | Representative infantry and cavalry can reach the exit and cannot escape the lane. |
| Every purchase pad | A King can reach each pad; the signs' captions name the legacy purchase. |
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

The `trade-income` and `tower-damage` probes measure what `docs/balance.md` assumes: how
trade gold grows with route length, raider kill times, tower kill times per enemy kind and
siege damage. The gold per trip on the game's own routes comes from the game (see Economy
and shop); put it into `Assumptions` in `src/ancienttdde/game/balance.py` and regenerate.

```bash
uv run ancienttdde probe --only trade-income --only tower-damage --output .build/balance-probes
```

The `towers` probe's script pads show whether the script's tower attack passes 255 and how
DE packs the attack class (cases `towers.beyond-255` and `towers.encoding`).
