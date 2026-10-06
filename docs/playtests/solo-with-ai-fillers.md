# Solo trial with AI-filled slots

The user reported one human with AI in every other slot. Game speed was Casual
in the lobby. The DE build, civilization and human slot were not recorded.

The local build supplied before the report had scenario SHA-256
`5decada4de1c23a6df731e3e36afa6a9fe39f9547c211710447c4ea8970aa7bc`
and normalized gameplay SHA-256
`8924cc1889a657bf01076ab4d082dba1edcb312c62734057f1824bb4a805e45d`.
The installed file's checksum was not independently confirmed by the user.

| Observation | Diagnosis and response |
| --- | --- |
| Victory during Men-at-Arms | The engine counted AI fillers as competitors. Participation now requires a human controller; AI-filled defense lanes are cleared and excluded from victory calculations. The exact reported game was not instrumented, so this is a reproduced code defect consistent with the report. |
| Carts and cogs idle; apparently extra traders | The original map supplies eight carts and four cogs per defense player after gallery ownership is applied. The generated game had omitted the original startup orders. Initialization now tasks those traders to their own partner market and dock. |
| Missing mill beside the berries | No starting mill was present in the generated defense economies. Each of P1–P7 now has a mill placed beside its berries, owned by that player whether a human or a computer fills the slot. Clearing a computer-filled or eliminated lane keeps it. Its full footprint and the berry gatherers' access routes are checked. |
| One enemy per spawn | All ten wave definitions now spawn two enemies per batch, including bosses. |
| Missing decorative barriers, exposing ice | The migration replaced 5,550 visible Hay Stacks with invisible Blockers. It now retains stock Hay Stacks at the original positions with their original one-tile footprints. The underlying ice terrain was already in the source map. |
| Speed defaults to Casual | The builder does not control the lobby's speed setting. Hosting instructions now require the host to select Fast, the highest lobby option. |
| Instructions assume slots can be closed | Instructions now require all eight slots, with computers filling unused defense positions and the enemy slot. All computer slots receive embedded passive AI. |
| King purchases and generation unavailable | These mechanics are not implemented in the generated full-map ruleset. The focused King-payment probe is separate and does not provide full-map shop logic. |
| Missing strong towers and blocked tower positions | The ruleset supplies two boosted Watch Towers. Original special-tower purchases are unavailable; their two central reserved pads still contain barriers. Instructions now call out these reserved positions. |

Automated checks cover human detection among AI fillers, AI departures during
Men-at-Arms, native trade orders, paired batches, visible barrier identities,
berry mill placement and its survival through lane cleanup, serialized references
and map connectivity. They do not execute DE's pathfinder, trade engine, graphics
renderer, trigger scheduler or multiplayer controller.

Retest solo in the first and last defense slots with all other slots computer
controlled. Confirm no early victory, no AI defense income or waves, automatic
trade startup, visible barriers, pairs of enemies, and a mill beside the berries
in every defense lane, including computer-filled lanes. Then test two
nonconsecutive human slots, the complete finale, resignation and save/reload.
