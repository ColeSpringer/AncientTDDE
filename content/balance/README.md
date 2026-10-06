# Modern balance definitions

`game.json` defines the finite wave schedule, lives, starting resources, income,
arrow-tower bonus, enemy cap and sudden-death pressure. Both the game and its
instructions are generated from these values. The loader rejects invalid types,
unsupported wave objects and schedules that cannot emit all their batches.

The schedule has fifteen waves in three tiers of five; each tier ends with an
elephant boss wave. Villagers open the schedule as its weakest wave. Every wave
spawns for 120 game seconds, and every batch contains two enemies: regular waves
send 60 enemies per lane and boss waves send eight. The first enemies arrive 240
game seconds in, two real minutes at Fast (twice real time). The 600 starting
resources plus preparation income give each lane about 1,540 of each resource when
the first wave arrives. The scheduled duration is about 41 game minutes; cleanup of
surviving enemies extends this. Tests require Villagers as the weakest opening wave,
waves of at most 120 game seconds, at least 60 enemies per regular wave and 8 per
boss wave, and no more than 1,600 of each resource at the first wave.

These values support a complete run and require playtesting for difficulty and
civilization balance. Legacy observations remain under `content/legacy/`.
