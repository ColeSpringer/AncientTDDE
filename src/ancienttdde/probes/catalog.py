"""Solo test actions and expected observations for each generated arena."""

from ancienttdde.probes.models import ProbeCase, ProbeDefinition, ProbeId

TEST_SETTINGS = (
    "Test as P1 with the standard data set. In DE's test/lobby dialog select "
    "Reveal Map: All Visible; Lock Teams: on; "
    "Allow Cheats: off; Game Speed: Normal; Lock Speed: on; Resources: Standard; "
    "Starting/Ending Age: Standard; Population: 200; Treaty Length: None; Turbo Mode: off; "
    "Full Tech Tree: off; Handicap: 100%; AI Difficulty: Standard. "
    "Use the scenario victory rules and embedded passive AI. "
    "Britons is the default civilization; change it deliberately for civilization comparisons. "
    "Unused computer slots keep one protected King along the eastern edge so the "
    "engine does not defeat them at start; towers and Outposts do not keep a player in the game. "
    "Initialization sets experiment resources. "
    "Reveal Map and Allow Cheats must be selected in DE; the scenario file does not set them. "
    "Before testing, confirm the whole arena is visible and the game stays running."
)


def case(key: str, action: str, expected: str) -> ProbeCase:
    return ProbeCase(key, action, expected)


PROBES: tuple[ProbeDefinition, ...] = (
    ProbeDefinition(
        ProbeId.PAYMENTS,
        "Exact King payments",
        "Move Kings onto the marked shop pad (10,10). Price: 3 Kings; reward: 100 gold. "
        "The pad at (22,10) is closed. Spare Kings wait south of the pads. "
        "Restart the scenario for each payment comparison; wait two game-seconds after moving.",
        (
            case(
                "payments.exact",
                "Move exactly 3 Kings onto the open pad.",
                "3 Kings disappear and gold increases by exactly 100.",
            ),
            case(
                "payments.excess",
                "Move 5 Kings onto the open pad.",
                "Exactly 3 disappear, 2 remain, and gold increases by 100.",
            ),
            case(
                "payments.repeat",
                "Move 6 Kings onto the open pad and wait 3 seconds.",
                "Two separate purchases consume 6 Kings and grant 200 gold.",
            ),
            case(
                "payments.insufficient",
                "Move only 2 Kings onto the open pad.",
                "Both remain and no gold is awarded.",
            ),
            case(
                "payments.rejected",
                "Move 3 Kings onto the closed pad.",
                "All 3 remain, no gold is awarded, and rejection feedback appears.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.TOWERS,
        "Tower bonus persistence",
        "Use a standard civilization with Guard Tower and Keep (Britons recommended). "
        "The game starts in Feudal Age. Move the control King to the bonus pad (8,8), "
        "then build towers with the villagers. The pads at (16,8) and (24,8) force "
        "Castle/Guard Tower and Imperial/Keep respectively. Keep the control King alive. "
        "The Town Center at (24,28), two builders and scout are deliberate test fixtures.",
        (
            case(
                "towers.existing",
                "Inspect the existing Watch Tower before/after the bonus pad.",
                "Its pierce attack increases by 4, exactly once.",
            ),
            case(
                "towers.construction",
                "Build a new Watch Tower after buying the bonus.",
                "It has the same +4 attack adjustment as the existing tower.",
            ),
            case(
                "towers.upgrades",
                "Use both age/upgrade pads, then build another tower.",
                "Existing and newly built Guard Towers/Keeps retain exactly +4 attack.",
            ),
            case(
                "towers.scope",
                "Inspect the scout and Bombard Tower before/after the bonus.",
                "They receive no arrow-tower bonus; no unrelated class is modified.",
            ),
            case(
                "towers.save-load",
                "Save after applying the bonus, reload and build another tower.",
                "The bonus persists without being added a second time.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.TRADE,
        "Allied stock trade and protected endpoints",
        "P1 has one home market at (8,12) and one home dock at (8,44). "
        "Their allied P2 partners are at (54,12)/(54,44). One cart and one cog start "
        "trading after two seconds; gold starts at zero. Observe at least two full return "
        "trips before moving the control King from (8,22) to (8,4) to start P8's attacks. "
        "Use trade-gaia.aoe2scenario for the separate Gaia comparison.",
        (
            case(
                "trade.ally",
                "Watch both traders at P2; inspect their carried gold and home deposits.",
                "Both repeatedly pick up at P2 and return to their sole P1 home; gold rises.",
            ),
            case(
                "trade.protection",
                "After checking income, move the King to (8,4); watch P8 attack the endpoints.",
                "Endpoints survive combat, remain usable, and traders can still be killed.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.TRADE_GAIA,
        "Gaia stock trade compatibility",
        "The layout matches trade.aoe2scenario: one P1 market/dock at (8,12)/(8,44) "
        "and Gaia partners at (54,12)/(54,44). Gaia endpoints have capture disabled. "
        "Inspect their owner before and after traders approach. Observe two full return "
        "trips if possible. A stopped trader with a Gaia-owned endpoint is a compatibility "
        "failure; an endpoint changing owner invalidates the ownership setup. "
        "Keep the King away from (8,4) until the trade observations are complete.",
        (
            case(
                "trade.gaia-land",
                "Watch the cart at y=12 and confirm its partner remains Gaia-owned.",
                "It completes repeat trips and deposits gold while the partner remains Gaia-owned; "
                "record a failure if Gaia stock trade is unsupported.",
            ),
            case(
                "trade.gaia-water",
                "Watch the cog at y=44 and confirm its partner remains Gaia-owned.",
                "It completes repeat trips and deposits gold while the partner remains Gaia-owned; "
                "record a failure if Gaia stock trade is unsupported.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.RAIDERS,
        "Raider combat and containment",
        "Move Kings to (8,27) for a land scout or (18,27) for a naval galley. "
        "Each costs 3 Kings and has a living cap of 2. Land raiders appear inside "
        "the blocker enclosure at (18,16); ships appear at (18,50) in the southern basin. "
        "A blocked spawn keeps your Kings: move the previous raider away to retry. "
        "Hostile traders and raiders belong to player 8. Your market/dock can train "
        "replacement stock traders with the supplied resources.",
        (
            case(
                "raiders.control",
                "Buy both raiders and attack hostile traders and raiders.",
                "Units belong to you, accept normal commands, and damage vulnerable units.",
            ),
            case(
                "raiders.containment",
                "Order raiders toward shop Kings and across arena boundaries.",
                "Scouts stay inside the land enclosure; galleys stay in the water basin.",
            ),
            case(
                "raiders.cap",
                "For each type, buy one and leave it on its spawn. Put 3 more Kings on "
                "its pad, wait, then move the first raider away. After the second appears, "
                "move it away and put 3 more Kings on the pad.",
                "The blocked second purchase keeps all 3 Kings until the spawn clears. "
                "Then exactly 3 are consumed for the second raider. With both alive, "
                "no third raider appears and all 3 payment Kings remain.",
            ),
            case(
                "raiders.replacement",
                "Lose a raider, buy another, then replace a killed trader.",
                "A freed living-cap slot permits one purchase; new cart/cog can trade normally.",
            ),
            case(
                "raiders.protection",
                "Order attacks on hostile markets and docks.",
                "Protected endpoints survive while traders remain vulnerable.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.SIEGE,
        "Exclusive temporary siege",
        "P1 and P8 each start with Kings on their purchase pads (8,8)/(48,8). "
        "One surviving rival makes the price 25 Kings. P1 claims first; P8 retries "
        "automatically, and P8's Kings are held in place because the engine would "
        "otherwise walk computer-owned Kings into the Keep. Warning: 10 seconds, "
        "activity: 60 seconds, shared cooldown: 60 seconds, buyer cooldown: 120 "
        "seconds after cleanup; both cooldowns are displayed, and a purchase needs "
        "both at zero. Two deployed trebuchets appear on islets within range of the "
        "rival's Keep and can fire at once; they cannot move, so packing one leaves "
        "it packed in place. "
        "Spare P1 Kings wait at (28,1); move at least 25 onto your purchase pad to "
        "exercise buyer cooldown and no-rival rejection with sufficient payment. "
        "Move the separate control King to (8,14) to remove P1's life marker and "
        "simulate owner elimination, or (16,14) to remove P8's life marker. "
        "Restart for expiry and elimination comparisons.",
        (
            case(
                "siege.exclusive",
                "Observe both requests immediately after start.",
                "Only P1 pays 25 Kings; P8's 25 Kings remain during ownership/cooldown.",
            ),
            case(
                "siege.targeting",
                "After the warning, target the rival towers with both trebuchets.",
                "Exactly two deployed trebuchets appear on rival islets, hit chosen towers "
                "and cannot leave.",
            ),
            case(
                "siege.expiry",
                "Pack one trebuchet and leave the other unpacked until expiry.",
                "Both forms disappear 60 game-seconds after activation.",
            ),
            case(
                "siege.cooldown",
                "Wait through expiry and the shared cooldown.",
                "P8 can claim after shared cooldown; P1 cannot bypass its longer buyer cooldown.",
            ),
            case(
                "siege.repeat",
                "Once both displayed cooldowns read zero, move 25 spare Kings onto P1's pad.",
                "A second purchase consumes 25 Kings, runs a full 10-second warning and "
                "two trebuchets stay for 60 seconds.",
            ),
            case(
                "siege.elimination",
                "During warning/activity, remove the current owner's life marker.",
                "All owner siege disappears, pending spawn is canceled and cooldown starts.",
            ),
            case(
                "siege.no-rival",
                "Remove P8's life marker before requesting another P1 purchase.",
                "A purchase without a surviving rival does not consume Kings.",
            ),
            case(
                "siege.save-load",
                "Save during warning and activity, reload and wait for expiry.",
                "Ownership, timers and payment persist without duplicate siege or reset duration.",
            ),
        ),
    ),
    ProbeDefinition(
        ProbeId.SCRIPTS_ENEMY,
        "Embedded XS and passive enemy",
        "Observe the heartbeat objective/chat and the enemy arena. Player 8 uses "
        "embedded passive AI. At 10 seconds triggers create two enemy spearmen and "
        "task them toward your guard. No AI or XS files need to be installed.",
        (
            case(
                "scripts-enemy.heartbeat",
                "Run for 30 game-seconds with only the scenario installed.",
                "Embedded XS reports increasing heartbeat values without external-file errors.",
            ),
            case(
                "scripts-enemy.passive",
                "Watch player 8 before and after the triggered spawn.",
                "It builds/trains nothing autonomously; triggered enemies follow the given task.",
            ),
            case(
                "scripts-enemy.save-load",
                "Save at 20 seconds, reload and watch the counter/enemies.",
                "Heartbeat continues; initialization and the enemy spawn do not run twice.",
            ),
        ),
    ),
)


def select_probes(only: list[str] | None) -> tuple[ProbeDefinition, ...]:
    selected = set(only) if only else {p.id.value for p in PROBES}
    unknown = selected - {p.id.value for p in PROBES}
    if unknown:
        raise ValueError(f"Unknown probe: {', '.join(sorted(unknown))}")
    if only and len(only) != len(selected):
        raise ValueError("Duplicate probe selection")
    return tuple(p for p in PROBES if p.id.value in selected)


def instructions(probes: tuple[ProbeDefinition, ...]) -> str:
    lines = [
        "# Stock-DE mechanic probes",
        "",
        "Open each scenario in the DE editor. " + TEST_SETTINGS + " Game-seconds govern timers. "
        "Other active slots are computers using embedded passive AI. "
        "These are manual experiments; generated/reloaded files do not establish engine behavior.",
        "",
        "Record the game build, tester, observations and pass/fail for every case. "
        "`results.json` starts without observations; rebuilding preserves recorded runs.",
        "",
        "```bash",
        "uv run ancienttdde probe record --suite .build/probes --case payments.excess "
        "--status pass --game-build 'DE build number' --tester 'Your name' "
        "--notes '3 consumed, 2 remained, +100 gold'",
        "```",
        "",
    ]
    for probe in probes:
        lines += [
            f"## {probe.title}",
            "",
            f"Scenario: `{probe.id}.aoe2scenario`",
            "",
            probe.setup,
            "",
            "| Case | Action | Expected observation |",
            "| --- | --- | --- |",
        ]
        lines += [f"| {c.id} | {c.action} | {c.expected} |" for c in probe.cases]
        lines.append("")
    return "\n".join(lines)
