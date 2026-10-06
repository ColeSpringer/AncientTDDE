"""Checks a reloaded scenario passes before a pipeline records or trusts it."""

from AoE2ScenarioParser.datasets.trigger_lists.victory_condition import VictoryCondition

from ancienttdde.scenario.snapshot import ScenarioSnapshot

SCENARIO_VERSION = "1.59"


def require_version(snapshot: ScenarioSnapshot) -> None:
    if snapshot["scenario_version"] != SCENARIO_VERSION:
        raise ValueError(f"Scenario must use format version {SCENARIO_VERSION}")


def require_custom_victory(snapshot: ScenarioSnapshot, *, conditions_required: bool) -> None:
    """Require custom victory and the expected "all custom conditions required" setting.

    Scenarios that end through Declare Victory triggers require no custom condition and
    must clear every built-in one. The map template keeps the format seed's victory
    settings, Conquest included, with every custom condition required.
    """
    if snapshot["victory_condition"] != VictoryCondition.CUSTOM:
        raise ValueError("Scenario must not end through automatic standard victory")
    if snapshot["options"]["victory_custom_conditions_required"] != conditions_required:
        requirement = "require" if conditions_required else "not require"
        raise ValueError(f"Scenario must {requirement} every custom victory condition")
    if not conditions_required and any(snapshot["global_victory"].values()):
        raise ValueError("Scenario must disable all automatic victory conditions")


def require_no_dependencies(snapshot: ScenarioSnapshot, *, allow_embedded_xs: bool) -> None:
    dependencies = snapshot["dependencies"]
    if (
        dependencies["external_xs"]
        or dependencies["ai_files"]
        or any(dependencies["cinematics"])
        or dependencies["background_image"]
    ):
        raise ValueError("Scenario must not depend on external XS, AI, cinematic or image files")
    if dependencies["embedded_xs"] and not allow_embedded_xs:
        raise ValueError("Scenario must not contain embedded XS")


def require_unique_placements(snapshot: ScenarioSnapshot) -> None:
    identifiers = [unit["reference_id"] for unit in snapshot["units"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Placed instances must have unique reference IDs")
    if snapshot["next_unit_id"] <= max(identifiers, default=-1):
        raise ValueError("The unit ID allocator would collide with existing placements")
