"""Execute serialized purchase effects with a small substitute for the DE XS APIs."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ancienttdde.probes.build import build_probes
from ancienttdde.probes.serialization import read_object, rows, text_field

ROOT = Path(__file__).resolve().parents[1]


def purchase_effects(snapshot: dict[str, object], name: str) -> tuple[str, str]:
    purchase = next(row for row in rows(snapshot["triggers"], "triggers") if row["name"] == name)
    statements: list[str] = []
    functions: list[str] = []
    for component in rows(purchase["effects"], "effects"):
        attributes = component["attributes"]
        assert isinstance(attributes, dict)
        match component["type"]:
            case "script_call":
                message = text_field(attributes, "message")
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
def raider_transactions(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("Executing the embedded XS subset requires a C++ compiler")
    directory = tmp_path_factory.mktemp("raider-transactions")
    build_probes(ROOT, directory / "suite", only=["raiders"])
    snapshot = read_object(directory / "suite/raiders.json")
    scripts: list[str] = []
    for row in rows(snapshot["triggers"], "triggers"):
        if row["name"] == "XS SCRIPT":
            for component in rows(row["effects"], "effects"):
                attributes = component["attributes"]
                assert isinstance(attributes, dict)
                scripts.append(text_field(attributes, "message"))
    script = "\n".join(scripts)
    harness = (ROOT / "tests/support/raider_xs_harness.cpp").read_text(encoding="utf-8")
    land_functions, land_purchase = purchase_effects(snapshot, "raider.land.purchase")
    naval_functions, naval_purchase = purchase_effects(snapshot, "raider.naval.purchase")
    source = directory / "transactions.cpp"
    source.write_text(
        harness.replace("// EMBEDDED_XS", script)
        .replace("// PURCHASE_FUNCTIONS", land_functions + "\n" + naval_functions)
        .replace("// LAND_PURCHASE", land_purchase)
        .replace("// NAVAL_PURCHASE", naval_purchase),
        encoding="utf-8",
    )
    executable = directory / "transactions"
    result = subprocess.run(
        [compiler, "-std=c++17", "-Wall", "-Wextra", str(source), "-o", str(executable)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return executable


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
