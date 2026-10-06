"""The probe suite, its shared test settings and its written instructions."""

from ancienttdde.probes import payments, raiders, scripts_enemy, siege, towers, trade
from ancienttdde.probes.models import ProbeDefinition

# The scenario format stores no Reveal Map, Allow Cheats or game-speed setting, so testers
# select them in DE. Modify Resource 203/204 no longer reveals the map, and Set Player
# Visibility only shares another player's line of sight.
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


PROBES: tuple[ProbeDefinition, ...] = (
    payments.DEFINITION,
    towers.DEFINITION,
    trade.DEFINITION,
    trade.GAIA_DEFINITION,
    raiders.DEFINITION,
    siege.DEFINITION,
    scripts_enemy.DEFINITION,
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
