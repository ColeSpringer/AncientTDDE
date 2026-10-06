"""Checks every pipeline applies to a reloaded scenario."""

import copy
from pathlib import Path

import pytest
from conftest import snapshot

from ancienttdde.scenario.checks import (
    require_custom_victory,
    require_no_dependencies,
    require_unique_placements,
    require_version,
)
from ancienttdde.scenario.snapshot import ScenarioSnapshot


@pytest.fixture
def payments(payments_suite: Path) -> ScenarioSnapshot:
    return snapshot(payments_suite / "payments.aoe2scenario")


def test_reloaded_scenarios_must_use_the_supported_format(payments: ScenarioSnapshot) -> None:
    require_version(payments)
    changed = copy.deepcopy(payments)
    changed["scenario_version"] = "1.49"
    with pytest.raises(ValueError, match="1.59"):
        require_version(changed)


def test_custom_victory_must_match_whether_conditions_are_required(
    payments: ScenarioSnapshot,
) -> None:
    require_custom_victory(payments, conditions_required=False)
    with pytest.raises(ValueError, match="victory"):
        require_custom_victory(payments, conditions_required=True)
    standard = copy.deepcopy(payments)
    standard["victory_condition"] = 0
    with pytest.raises(ValueError, match="victory"):
        require_custom_victory(standard, conditions_required=False)
    conquest = copy.deepcopy(payments)
    conquest["global_victory"]["conquest_required"] = 1
    with pytest.raises(ValueError, match="victory"):
        require_custom_victory(conquest, conditions_required=False)
    # The map template keeps the seed's Conquest setting with every condition required.
    conquest["options"]["victory_custom_conditions_required"] = True
    require_custom_victory(conquest, conditions_required=True)


def test_scenarios_must_not_depend_on_external_files(payments: ScenarioSnapshot) -> None:
    require_no_dependencies(payments, allow_embedded_xs=False)
    embedded = copy.deepcopy(payments)
    embedded["dependencies"]["embedded_xs"] = "void main() {}"
    require_no_dependencies(embedded, allow_embedded_xs=True)
    with pytest.raises(ValueError, match="embedded"):
        require_no_dependencies(embedded, allow_embedded_xs=False)
    external_xs, ai_files, image = (copy.deepcopy(payments) for _ in range(3))
    external_xs["dependencies"]["external_xs"] = "script.xs"
    ai_files["dependencies"]["ai_files"] = 1
    image["dependencies"]["background_image"] = "loading.bmp"
    for scenario in (external_xs, ai_files, image):
        with pytest.raises(ValueError, match="external"):
            require_no_dependencies(scenario, allow_embedded_xs=True)


def test_placements_need_unique_ids_below_the_allocator(payments: ScenarioSnapshot) -> None:
    require_unique_placements(payments)
    duplicate = copy.deepcopy(payments)
    duplicate["units"].append(duplicate["units"][0])
    with pytest.raises(ValueError, match="unique"):
        require_unique_placements(duplicate)
    allocator = copy.deepcopy(payments)
    allocator["next_unit_id"] = 0
    with pytest.raises(ValueError, match="allocator"):
        require_unique_placements(allocator)
