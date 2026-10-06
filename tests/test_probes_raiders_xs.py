"""Execute serialized purchase effects with a small substitute for the DE XS APIs."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from conftest import ProbeSuite, attr_text, compile_harness, snapshot, triggers_by_name

from ancienttdde.scenario.snapshot import ScenarioSnapshot


def purchase_effects(raiders: ScenarioSnapshot, name: str) -> tuple[str, str]:
    purchase = triggers_by_name(raiders)[name]
    statements: list[str] = []
    functions: list[str] = []
    for component in purchase["effects"]:
        attributes = component["attributes"]
        match component["type"]:
            case "script_call":
                message = attr_text(attributes, "message")
                declaration = re.fullmatch(r"\s*void\s+(\w+)\(\)\s*\{[\s\S]*\}\s*", message)
                assert declaration is not None, (
                    "DE script effects need a function without arguments"
                )
                functions.append(message)
                statements.append(f"{declaration[1]}();")
            case "remove_object":
                # Preserve the serialized ordering when exercising the old native purchase.
                fields = (
                    "source_player",
                    "object_list_unit_id",
                    "max_units_affected",
                    "area_x1",
                    "area_y1",
                    "area_x2",
                    "area_y2",
                )
                statements.append(
                    "removeNativePayment(" + ", ".join(str(attributes[k]) for k in fields) + ");"
                )
            case "create_object":
                statements.append(
                    f"xsCreateUnit({attributes['object_list_unit_id']}, "
                    f"{attributes['source_player']}, "
                    f"xsVectorSet({attributes['location_x']} + 0.5, "
                    f"{attributes['location_y']} + 0.5, 0), false, true, true);"
                )
            case "send_chat":
                statements.append(f"xsChatData({json.dumps(attributes['message'])});")
            case _:
                pytest.fail(f"Unsupported purchase effect: {component['type']}")
    return "\n".join(functions), "\n".join(statements)


@pytest.fixture(scope="module")
def raider_transactions(tmp_path_factory: pytest.TempPathFactory, probe_suite: ProbeSuite) -> Path:
    suite, _ = probe_suite
    raiders = snapshot(suite / "raiders.aoe2scenario")
    scripts = [
        attr_text(component["attributes"], "message")
        for trigger in raiders["triggers"]
        if trigger["name"] == "XS SCRIPT"
        for component in trigger["effects"]
    ]
    land_functions, land_purchase = purchase_effects(raiders, "raider.land.purchase")
    naval_functions, naval_purchase = purchase_effects(raiders, "raider.naval.purchase")
    return compile_harness(
        tmp_path_factory.mktemp("raider-transactions"),
        "raider_xs_harness.cpp",
        {
            "// EMBEDDED_XS": "\n".join(scripts),
            "// PURCHASE_FUNCTIONS": land_functions + "\n" + naval_functions,
            "// LAND_PURCHASE": land_purchase,
            "// NAVAL_PURCHASE": naval_purchase,
        },
        warnings=True,
    )


@pytest.mark.parametrize("kind", ["land", "naval"])
@pytest.mark.parametrize("case", ["blocked", "cap", "payment", "excess", "replacement", "scope"])
def test_raider_purchase_transaction(raider_transactions: Path, case: str, kind: str) -> None:
    result = subprocess.run(
        [str(raider_transactions), case, kind],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
