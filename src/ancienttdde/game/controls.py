"""The run options and practice controls players select in the row below the shop."""

from dataclasses import dataclass
from typing import Literal

from ancienttdde.game.config import Balance

# Run modes in code order; only solo runs choose a mode other than Standard.
MODES = ("standard", "endless", "practice")
type ControlGroup = Literal["run", "practice"]


@dataclass(frozen=True)
class Control:
    key: str
    group: ControlGroup


# In code order: selecting a control tells the XS its code, one more than its position here.
CONTROLS = (
    Control("standard", "run"),
    Control("endless", "run"),
    Control("practice", "run"),
    Control("pvp_on", "run"),
    Control("pvp_off", "run"),
    Control("next_wave", "practice"),
    Control("kings", "practice"),
    Control("resources", "practice"),
    Control("lives", "practice"),
)


def control_code(key: str) -> int:
    return [control.key for control in CONTROLS].index(key) + 1


def controls(group: ControlGroup) -> tuple[Control, ...]:
    return tuple(control for control in CONTROLS if control.group == group)


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
        "pvp_off": ("PvP off", "Run option: PvP off (competitive) - no raiders or siege"),
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
