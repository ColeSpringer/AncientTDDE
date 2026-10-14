"""The run options and practice controls players select in the row below the shop."""

from dataclasses import dataclass
from typing import Literal

from ancienttdde.game.config import Balance

# Run modes in code order; only solo runs choose a mode other than Standard.
MODES = ("standard", "endless", "practice")
type ControlGroup = Literal["run", "practice"]
# The kinds of lobby: one human lane, or rivals.
type Lobby = Literal["solo", "competitive"]
LOBBIES: tuple[Lobby, ...] = ("solo", "competitive")


@dataclass(frozen=True)
class Control:
    key: str
    group: ControlGroup
    # The one kind of lobby the control applies to, or None for both.
    lobby: Lobby | None = None

    def applies(self, lobby: Lobby) -> bool:
        return self.lobby in (None, lobby)


# In code order: selecting a control tells the XS its code, one more than its position here.
CONTROLS = (
    Control("standard", "run"),
    Control("endless", "run", "solo"),
    Control("practice", "run", "solo"),
    Control("pvp_on", "run", "competitive"),
    Control("next_wave", "practice", "solo"),
    Control("kings", "practice", "solo"),
    Control("resources", "practice", "solo"),
    Control("lives", "practice", "solo"),
)


def control_code(key: str) -> int:
    return [control.key for control in CONTROLS].index(key) + 1


def controls(group: ControlGroup, lobby: Lobby | None = None) -> tuple[Control, ...]:
    """A group's controls, or only those that apply in a kind of lobby."""
    return tuple(
        control
        for control in CONTROLS
        if control.group == group and (lobby is None or control.applies(lobby))
    )


def ruled_out(lobby: Lobby) -> tuple[Control, ...]:
    """The controls that cannot apply in a kind of lobby."""
    return tuple(control for control in CONTROLS if not control.applies(lobby))


def control_texts(balance: Balance) -> dict[str, tuple[str, str]]:
    """Each control's short label, which it carries as a caption, and the name it shows when
    selected."""
    practice = balance.practice
    return {
        "standard": ("Standard", "Run option: Standard (solo) - the scheduled waves, then victory"),
        "endless": (
            "Endless",
            "Run option: Endless (solo) - the waves keep coming after the finale",
        ),
        "practice": (
            "Practice",
            "Run option: Practice (solo) - practice controls, assisted result",
        ),
        "pvp_on": ("PvP on", "Run option: PvP on (competitive) - raiders and siege for sale"),
        "next_wave": ("Next wave", "Practice: start the next wave now"),
        "kings": (f"+{practice.kings} Kings", f"Practice: {practice.kings} more Kings"),
        "resources": (
            f"+{practice.resources} resources",
            f"Practice: {practice.resources} more food, wood, stone and gold",
        ),
        "lives": ("Lives back", "Practice: all lives back"),
    }


def control_labels(balance: Balance) -> dict[str, str]:
    return {key: label for key, (label, _) in control_texts(balance).items()}


def control_captions(balance: Balance) -> dict[str, str]:
    return {key: caption for key, (_, caption) in control_texts(balance).items()}
