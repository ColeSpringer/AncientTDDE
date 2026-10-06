# Solo retest: Militia wave stalled at the exit

The user retested the build that followed the [first solo trial](solo-with-ai-fillers.md).
The installed scenario had SHA-256
`0cda361ba09822125209fc508462869f8c0b6233f405700b29748976a799ed59`
(normalized gameplay SHA-256
`d946199f8f5e7117601e71c6ef217f93fa10030a2ac4fff68646bc4a49bc3047`).
DE reported version 101.103.54800.0 (185872). One human lane, P1, participated.

The user reported that only the Militia wave ran, that it lasted longer than
expected and that it started a little earlier than expected.

## Evidence

DE's autosave at 590.7 game seconds stored these scenario variables:

| Variable | Value |
| --- | --- |
| Phase | Wave |
| Wave | Militia, the first wave |
| Seconds elapsed in the wave | 464 of 240 |
| Batches spawned | 30 of 30 |
| Participants and survivors | 1 and 1 |
| P1 lives | 26 |
| P1 enemies counted alive | 1 |

The only P8 Militia in the save stood at (55.97, 15.0) with 82 hit points. The
recorded game ends with a resignation at 625.6 game seconds; no victory occurred.

## Diagnosis and response

| Observation | Diagnosis and response |
| --- | --- |
| Only the Militia wave ran; it lasted longer than expected | Enemies are ordered to exit tile (56, 15). DE stopped the last Militia short of the tile's edge, at x = 55.97, but the runtime counted a leak only from x = 56. The enemy stood beyond the reach of every tower, so the wave could not finish and no later wave started. The first trial used the same target and threshold. A leak now counts from x = 55, the tile holding the three exit flags in every lane. A runtime case reproduces the saved stop position. |
| The first wave started a little earlier than expected | The runtime advanced once per game second: 590 steps at 590.7 game seconds. The first batch spawns 121 game seconds after the "Prepare your towers" message, about one real minute at Fast. The original map's first wave began at 650 game seconds. Preparation length is a balance setting in `content/balance/game.json`. |
| Wave length | The Militia wave spawns a pair every 8 game seconds for 240 game seconds; the stall extended it to the end of the session. The original map's waves spawned every 3 seconds for 45 seconds. Wave lengths are balance settings in `content/balance/game.json`. |

The victory during Men-at-Arms from the first trial did not recur: the save shows a
single participant and the session ended by resignation.

## Follow-up run

The user installed build
`ed423cbe74f7f5ca888810dca8a357adbf60b767b359d0be7cfdfbbeefabd337`, which counts the
exit-flag tile as the exit and runs 15 waves of 120 game seconds. The user reported
that the Militia wave ended and Spearmen followed. The autosave agrees: the second
wave, Spearmen, had spawned its first batch, with one participant and no enemies
left in P1's lane. P1 had lost 18 of 30 lives to the Militia wave; the user judged
the opening too hard and proposed a Villager first wave. The recording ends at 558.8
game seconds without a result.

The user also found that the trees beside the lumber camps ran out of wood. No
original trigger re-creates trees: the original data gave Tree A 10,000,000,000 wood,
while a stock tree holds 100. The game now raises Gaia's Tree A wood at the start
and replaces each lane's four lumber trees on their own tiles. In the next run the
trees, raised to 1,000,000, topped out a little under 17,000: DE applies the value as
a 16-bit number, and 1,000,000 wraps to 16,960. The game now uses 32,000, the
largest round amount below the signed 16-bit limit. The original gold, stone and
berry bonus pads remain outside this ruleset.

With Villagers opening the schedule and the first enemies 90 real seconds into a
Fast game, the user was defeated as the Romans without notable mistakes. The first
enemies now arrive two real minutes in again (240 game seconds), with 600 starting
resources. The user also reported that a lane's life Outpost does not change when
enemies escape and that no message reports an escape; the game tracks lives in a
scenario variable and lists them only in its objectives.

Retest solo in the first and last defense slots with all other slots computer
controlled. Confirm that each wave ends once its last enemy is killed or reaches the
exit flags, that the next wave follows the 30-second interval, and that no victory
occurs before the finale is cleared.
