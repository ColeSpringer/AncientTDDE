import os
import re
import shutil
from pathlib import Path

import pytest
from conftest import new_scenario

from ancienttdde.common.data import asset_text
from ancienttdde.common.layers import ASSETS
from ancienttdde.scenario.xs import check_xs

# DE's XS does not promote an int argument to float, and the parser's XS check does not
# report it, so packaged scripts write a float literal wherever XS expects a float.
INT_FOR_FLOAT = re.compile(r"\bfloat\s+\w+\s*=\s*-?\d+(?![\d.])")
VECTOR_SET = re.compile(r"xsVectorSet\(([^()]*)\)")
# The AoE2 XS Scripting editor extension (1.2.7) reports a counted loop that reuses an
# earlier loop's variable in the same function. DE and the parser's XS check accept it, but
# packaged scripts give each loop its own variable so the editor shows only real errors.
COUNTED_LOOP = re.compile(r"\bfor\s*\(\s*(\w+)\s*=")
# Strings and comments, which may hold braces or text that looks like a loop.
NON_CODE = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.S)
NAME = re.compile(r"\brule\s+(\w+)|(\w+)\s*\(")
SCRIPTS = sorted(name for names in ASSETS.values() for name in names if name.endswith(".xs"))


def definitions(code: str) -> list[tuple[str, str]]:
    """Split code without strings or comments into its functions and rules: (name, body)."""
    found: list[tuple[str, str]] = []
    depth = header = body = 0
    for match in re.finditer(r"[{};]", code):
        if match[0] == "{":
            depth += 1
            if depth == 1:
                body = match.end()
        elif match[0] == "}":
            depth -= 1
            if depth == 0:
                named = NAME.search(code, header, body)
                found.append((named[1] or named[2] if named else "", code[body : match.start()]))
                header = match.end()
        elif depth == 0:
            header = match.end()
    assert depth == 0, "unbalanced braces"
    return found


def make_scenario():
    return new_scenario("1.59")


def test_xs_errors_fail_validation() -> None:
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string="void broken() { unknownFunction(); }")
    with pytest.raises(Exception, match="Xs-Check failed validation"):
        check_xs(scenario)


def test_xs_validation_needs_the_parser_xs_check() -> None:
    scenario = make_scenario()
    scenario.xs_manager.xs_check.enabled = False
    with pytest.raises(ValueError, match="^The parser's xs-check must be enabled to check XS$"):
        check_xs(scenario)


@pytest.mark.skipif(os.name != "posix", reason="Executable permissions are a POSIX concern")
def test_xs_checker_handles_a_bundled_binary_without_execute_permission(tmp_path: Path) -> None:
    scenario = make_scenario()
    scenario.xs_manager.add_script(xs_string='void valid() { xsChatData("ok"); }')
    binary = tmp_path / "xs-check"
    bundled = scenario.xs_manager.xs_check.path
    assert bundled is not None
    shutil.copyfile(bundled, binary)
    binary.chmod(0o700)
    scenario.xs_manager.xs_check.path = binary
    binary.chmod(0o600)
    check_xs(scenario)
    assert binary.stat().st_mode & 0o111 == 0


@pytest.mark.parametrize("name", SCRIPTS)
def test_packaged_scripts_write_floats_where_xs_expects_them(name: str) -> None:
    text = asset_text(name)
    assert INT_FOR_FLOAT.findall(text) == []
    components = [part for found in VECTOR_SET.findall(text) for part in found.split(",")]
    assert [part for part in components if re.fullmatch(r"\s*-?\d+\s*", part)] == []


@pytest.mark.parametrize("name", SCRIPTS)
def test_packaged_scripts_give_each_counted_loop_in_a_function_its_own_variable(
    name: str,
) -> None:
    code = NON_CODE.sub(" ", asset_text(name))
    loops = [(function, COUNTED_LOOP.findall(body)) for function, body in definitions(code)]
    assert sum(len(names) for _, names in loops) == len(COUNTED_LOOP.findall(code))
    assert [(f, names) for f, names in loops if len(names) != len(set(names))] == []
